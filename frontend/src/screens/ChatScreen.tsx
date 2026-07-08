import { useState, useRef, useEffect, useCallback } from 'react'
import { MessageCircle } from 'lucide-react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createConversation, getConversationMessages, sseUrl } from '../lib/api'
import { useSSEStream } from '../hooks/useSSEStream'
import { ChatBubble, type BubbleRole } from '../components/chat/ChatBubble'
import { ChatInput } from '../components/chat/ChatInput'
import { StreamErrorBanner } from '../components/chat/StreamErrorBanner'

// ---------------------------------------------------------------------------
// ChatScreen: persistent coaching conversation with SSE streaming.
//
// Flow:
//   1. On mount: if a conversation id is persisted (localStorage), reload
//      the EXISTING conversation's messages via getConversationMessages;
//      otherwise call createConversation (POST /conversations/) and persist
//      its id. This is item 4 (D-04): after the ['active-conversation']
//      query cache is GC'd (5min gcTime, unchanged), a reload must resume
//      the same conversation instead of silently creating a new empty one
//      -- continuity comes from the persisted id, not from bumping gcTime.
//   2. User sends a message: open useSSEStream with sseUrl('/chat/stream?conversation_id=...')
//   3. Render coach/user/adaptation/capability-gap bubbles from message history
//   4. Show streaming ellipsis while tokens arrive
//   5. Transient SSE errors retry silently inside useSSEStream (D-02); once
//      retries are exhausted, a terminal error clears activeStreamUrl and
//      renders StreamErrorBanner with a manual Retry.
//
// Security: streamed content rendered via React safe text (no dangerouslySetInnerHTML).
// ---------------------------------------------------------------------------

// D-04: localStorage key used to persist the active conversation id across
// the React Query cache's 5min gcTime window (NOT a gcTime bump — the
// persisted id is what survives, the cache itself is still GC'd normally).
const ACTIVE_CONVERSATION_STORAGE_KEY = 'pacerai:active-conversation-id'

function getPersistedConversationId(): string | null {
  try {
    return localStorage.getItem(ACTIVE_CONVERSATION_STORAGE_KEY)
  } catch {
    return null
  }
}

function persistConversationId(id: string): void {
  try {
    localStorage.setItem(ACTIVE_CONVERSATION_STORAGE_KEY, id)
  } catch {
    // localStorage unavailable (private browsing, quota) — non-fatal; the
    // conversation simply won't survive a cache-GC reload in this context.
  }
}

interface ActiveConversation {
  id: string
  /** Present only when this resolution was a reload of an existing conversation. */
  priorMessages?: { role: string; content: string }[]
}

interface Message {
  id: string
  role: 'coach' | 'user'
  content: string
  bubbleRole: BubbleRole
  timestamp: string
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
}

// Heuristic: detect adaptation-style messages (coach initiated plan changes)
function detectBubbleRole(content: string): BubbleRole {
  const lower = content.toLowerCase()
  if (
    lower.includes('adjusted your plan') ||
    lower.includes('updating your plan') ||
    lower.includes('i have updated') ||
    lower.includes('plan has been updated') ||
    lower.includes('rescheduled')
  ) {
    return 'adaptation'
  }
  if (
    lower.includes("can't calculate") ||
    lower.includes('not enough data') ||
    lower.includes('insufficient data') ||
    lower.includes('capability gap')
  ) {
    return 'capability-gap'
  }
  return 'coach'
}

export function ChatScreen() {
  const queryClient = useQueryClient()

  // Whether a conversation id was already persisted when this component
  // mounted -- computed once, used only to decide whether to render the
  // brief "reloading" loading state below (a fresh conversation resolves
  // near-instantly and doesn't need one).
  const [hadPersistedConversation] = useState(() => getPersistedConversationId() !== null)

  // Conversation ID persisted via react-query cache + localStorage (D-04).
  // gcTime is left at its default (5min) deliberately -- cross-GC
  // continuity comes from the persisted id below, not from a longer gcTime.
  const { data: conversation, isLoading: isLoadingConversation } = useQuery<ActiveConversation>({
    queryKey: ['active-conversation'],
    queryFn: async () => {
      const persistedId = getPersistedConversationId()
      if (persistedId) {
        // D-04: cache-miss reload -- refetch the EXISTING conversation's
        // history instead of calling createConversation again (which would
        // silently create a new empty conversation row and drop history).
        const priorMessages = await getConversationMessages(persistedId)
        return { id: persistedId, priorMessages }
      }
      const conv = await createConversation('Coaching session')
      persistConversationId(conv.id)
      return { id: conv.id }
    },
    staleTime: Infinity, // Keep the same conversation for the session
  })

  const [messages, setMessages] = useState<Message[]>([])
  const [activeStreamUrl, setActiveStreamUrl] = useState<string | null>(null)
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Hydrate the visible message list once when a reload resolves with prior
  // messages. Guarded by a ref (not just `messages.length === 0`) so a
  // later refetch of the same conversation never clobbers messages the user
  // has since added.
  const hydratedConversationIdRef = useRef<string | null>(null)
  useEffect(() => {
    if (!conversation?.priorMessages) return
    if (hydratedConversationIdRef.current === conversation.id) return
    hydratedConversationIdRef.current = conversation.id
    setMessages(
      conversation.priorMessages.map((m, i) => ({
        id: `history-${conversation.id}-${i}`,
        role: m.role === 'user' ? 'user' : 'coach',
        content: m.content,
        bubbleRole: m.role === 'user' ? 'user' : detectBubbleRole(m.content),
        timestamp: '',
      })),
    )
  }, [conversation])

  const { content, isDone, error } = useSSEStream(activeStreamUrl)

  // Auto-scroll to bottom when messages or stream content changes
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, content])

  // When stream completes, commit the accumulated content as a coach message.
  // D-03 (item 3): a tool-only turn produces isDone=true with empty content --
  // activeStreamUrl/pendingUserMessage must ALWAYS clear on isDone regardless
  // of content, or handleSend's guard silently bricks every later send. Only
  // push a coach message when content is non-empty.
  useEffect(() => {
    if (!isDone) return
    if (content) {
      setMessages((prev) => [
        ...prev,
        {
          id: `coach-${Date.now()}`,
          role: 'coach',
          content,
          bubbleRole: detectBubbleRole(content),
          timestamp: formatTime(new Date()),
        },
      ])
    }
    setActiveStreamUrl(null)
    setPendingUserMessage(null)
    // WR-008: do NOT invalidate active-conversation here -- the queryFn calls
    // createConversation(), so invalidation would create a new DB row and reset
    // the conversation context on every turn. Only invalidate session/history
    // queries that reflect content changes from the coaching response.
  }, [isDone, content, queryClient])

  // D-02 (item 2): once useSSEStream's silent retries are exhausted and it
  // surfaces a terminal error, clear activeStreamUrl so isStreaming resolves
  // to false and the input re-enables. pendingUserMessage is deliberately
  // NOT cleared here so Retry can re-derive the same request.
  useEffect(() => {
    if (error) {
      setActiveStreamUrl(null)
    }
  }, [error])

  const handleSend = useCallback(
    async (text: string) => {
      if (!conversation?.id || activeStreamUrl) return

      // Add user message immediately
      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: 'user',
        content: text,
        bubbleRole: 'user',
        timestamp: formatTime(new Date()),
      }
      setMessages((prev) => [...prev, userMsg])
      setPendingUserMessage(text)

      // Build SSE stream URL with conversation_id and JWT via sseUrl helper
      const url = await sseUrl(
        `/api/chat/stream?conversation_id=${encodeURIComponent(conversation.id)}&message=${encodeURIComponent(text)}`
      )
      setActiveStreamUrl(url)
    },
    [conversation?.id, activeStreamUrl]
  )

  // Retry re-sends the last user message (no new bubble -- it's already in
  // the message list) and re-derives a fresh stream URL/token.
  const handleRetry = useCallback(async () => {
    if (!conversation?.id || !pendingUserMessage) return
    const url = await sseUrl(
      `/api/chat/stream?conversation_id=${encodeURIComponent(conversation.id)}&message=${encodeURIComponent(pendingUserMessage)}`
    )
    setActiveStreamUrl(url)
  }, [conversation?.id, pendingUserMessage])

  const isStreaming = activeStreamUrl !== null && !isDone

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        backgroundColor: 'var(--color-bg)',
      }}
    >
      {/* Message list */}
      <div
        ref={scrollRef}
        style={{
          flex: 1,
          overflowY: 'auto',
          width: '100%',
          maxWidth: 720,
          margin: '0 auto',
          padding: '16px',
        }}
      >
        {/* D-04: brief loading state while an existing conversation's
            history reloads after a cache-miss, so the empty state doesn't
            flash before the reloaded history renders. */}
        {isLoadingConversation && hadPersistedConversation && (
          <div
            style={{
              textAlign: 'center',
              paddingTop: '60px',
            }}
          >
            <p
              style={{
                fontSize: '15px',
                color: 'var(--color-ink-2)',
                margin: 0,
                lineHeight: '1.5',
              }}
            >
              Loading your conversation...
            </p>
          </div>
        )}

        {messages.length === 0 && !isStreaming && !(isLoadingConversation && hadPersistedConversation) && (
          <div
            style={{
              textAlign: 'center',
              paddingTop: '96px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
            }}
          >
            <div
              style={{
                width: 56,
                height: 56,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: 'var(--color-blue-0)',
                marginBottom: 16,
              }}
            >
              <MessageCircle size={26} style={{ color: 'var(--color-blue-6)' }} />
            </div>
            <h2
              style={{
                fontSize: '18px',
                fontWeight: 600,
                color: 'var(--color-ink)',
                margin: '0 0 6px',
              }}
            >
              Ask your coach anything
            </h2>
            <p
              style={{
                fontSize: '15px',
                color: 'var(--color-ink-2)',
                margin: 0,
                lineHeight: '1.5',
                maxWidth: 300,
              }}
            >
              Start by uploading a ride, or ask about your plan.
            </p>
          </div>
        )}

        {messages.map((msg) => (
          <ChatBubble
            key={msg.id}
            role={msg.bubbleRole}
            timestamp={msg.timestamp}
          >
            {msg.content}
          </ChatBubble>
        ))}

        {/* Streaming coach bubble */}
        {isStreaming && (
          <ChatBubble role="coach">
            {content || undefined}
          </ChatBubble>
        )}

        {/* Streaming ellipsis when no content yet */}
        {isStreaming && !content && (
          <ChatBubble role="coach" isStreaming />
        )}
      </div>

      {/* Terminal stream error (retries exhausted) -- manual Retry */}
      {error && (
        <StreamErrorBanner
          message="Connection failed."
          onRetry={handleRetry}
          variant="chat"
        />
      )}

      {/* Input bar */}
      <div style={{ width: '100%', maxWidth: 720, margin: '0 auto' }}>
        <ChatInput
          onSend={handleSend}
          disabled={isStreaming || !conversation}
        />
      </div>
    </div>
  )
}
