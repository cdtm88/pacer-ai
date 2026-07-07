import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createConversation, sseUrl } from '../lib/api'
import { useSSEStream } from '../hooks/useSSEStream'
import { ChatBubble, type BubbleRole } from '../components/chat/ChatBubble'
import { ChatInput } from '../components/chat/ChatInput'
import { StreamErrorBanner } from '../components/chat/StreamErrorBanner'

// ---------------------------------------------------------------------------
// ChatScreen: persistent coaching conversation with SSE streaming.
//
// Flow:
//   1. On mount: call createConversation (POST /conversations/) if no id cached
//   2. User sends a message: open useSSEStream with sseUrl('/chat/stream?conversation_id=...')
//   3. Render coach/user/adaptation/capability-gap bubbles from message history
//   4. Show streaming ellipsis while tokens arrive
//   5. Transient SSE errors retry silently inside useSSEStream (D-02); once
//      retries are exhausted, a terminal error clears activeStreamUrl and
//      renders StreamErrorBanner with a manual Retry.
//
// Security: streamed content rendered via React safe text (no dangerouslySetInnerHTML).
// ---------------------------------------------------------------------------

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

  // Conversation ID persisted via react-query cache
  const { data: conversation } = useQuery({
    queryKey: ['active-conversation'],
    queryFn: async () => {
      const conv = await createConversation('Coaching session')
      return conv
    },
    staleTime: Infinity, // Keep the same conversation for the session
  })

  const [messages, setMessages] = useState<Message[]>([])
  const [activeStreamUrl, setActiveStreamUrl] = useState<string | null>(null)
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

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
          padding: '16px',
        }}
      >
        {messages.length === 0 && !isStreaming && (
          <div
            style={{
              textAlign: 'center',
              paddingTop: '60px',
            }}
          >
            <h2
              style={{
                fontSize: '18px',
                fontWeight: 600,
                color: 'var(--color-ink)',
                margin: '0 0 8px',
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
      <ChatInput
        onSend={handleSend}
        disabled={isStreaming || !conversation}
      />
    </div>
  )
}
