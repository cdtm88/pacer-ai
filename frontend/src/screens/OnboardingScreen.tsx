import { useState, useRef, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { useQueryClient } from '@tanstack/react-query'
import { sseUrl, getProfileMe } from '../lib/api'
import { ChatBubble } from '../components/chat/ChatBubble'
import { ChatInput } from '../components/chat/ChatInput'

// ---------------------------------------------------------------------------
// Confirmation gate detection (exported for Vitest coverage).
//
// The onboarding system prompt mandates the agent begin its confirmation
// summary with exactly "Here is what I have". Keep this as a single exported
// constant so the runtime check and the test share one source of truth.
// A future API-level signal can replace the prefix check here in one place.
// ---------------------------------------------------------------------------

export const ONBOARDING_COMPLETION_MARKER = 'Here is what I have'

/**
 * Returns true when a coach message begins with the onboarding confirmation
 * summary marker. Case-sensitive to match the system prompt exactly.
 */
export function isOnboardingComplete(message: string): boolean {
  return message.trimStart().startsWith(ONBOARDING_COMPLETION_MARKER)
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface Message {
  id: string
  role: 'coach' | 'user'
  content: string
  timestamp: string
}

// ---------------------------------------------------------------------------
// SSE line parser for fetch-based streaming (POST /onboarding/start)
//
// EventSource only supports GET requests, so onboarding uses fetch() with a
// ReadableStream reader to consume the same SSE event format.
// The same five event types apply: token, tool_start, tool_result, done, error.
// ---------------------------------------------------------------------------

interface ParsedSSEEvent {
  type: 'token' | 'tool_start' | 'tool_result' | 'done' | 'error'
  data: Record<string, unknown>
}

function parseSSELine(
  eventName: string,
  dataLine: string
): ParsedSSEEvent | null {
  if (!eventName) return null
  try {
    const data = JSON.parse(dataLine) as Record<string, unknown>
    return {
      type: eventName as ParsedSSEEvent['type'],
      data,
    }
  } catch {
    return null
  }
}

// ---------------------------------------------------------------------------
// Progress estimation: advance 0..90% as more messages arrive, cap at 90
// until the confirmation gate fires (then jump to 100 on save).
// ---------------------------------------------------------------------------

function estimateProgress(messageCount: number): number {
  // 6 fields: each roughly 2 exchanges = 12 messages to 90%
  const pct = Math.min(90, Math.round((messageCount / 14) * 90))
  return pct
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString(undefined, {
    hour: 'numeric',
    minute: '2-digit',
  })
}

// ---------------------------------------------------------------------------
// OnboardingScreen
// ---------------------------------------------------------------------------

export function OnboardingScreen() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [messages, setMessages] = useState<Message[]>([])
  const [streamContent, setStreamContent] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [streamError, setStreamError] = useState<string | null>(null)
  const [showConfirmation, setShowConfirmation] = useState(false)
  const [confirmationText, setConfirmationText] = useState('')
  const [isConfirmed, setIsConfirmed] = useState(false)
  const [progress, setProgress] = useState(0)

  const scrollRef = useRef<HTMLDivElement>(null)
  const abortRef = useRef<AbortController | null>(null)

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streamContent])

  // Update progress as messages accumulate
  useEffect(() => {
    setProgress(estimateProgress(messages.length))
  }, [messages.length])

  // ---------------------------------------------------------------------------
  // Fetch-based SSE reader for POST /onboarding/start
  // ---------------------------------------------------------------------------

  const runStream = useCallback(
    async (userMessage?: string) => {
      // Cancel any in-flight stream
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setIsStreaming(true)
      setStreamContent('')
      setStreamError(null)

      try {
        const url = await sseUrl('/onboarding/start')
        // sseUrl appends ?token=<jwt>; for POST we pass it as a query param
        const res = await fetch(url, {
          method: 'POST',
          signal: controller.signal,
          headers: {
            Accept: 'text/event-stream',
            'Content-Type': 'application/json',
          },
          body: userMessage ? JSON.stringify({ message: userMessage }) : undefined,
        })

        if (!res.ok || !res.body) {
          setStreamError('Could not connect to coach. Try again.')
          setIsStreaming(false)
          return
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder()
        let buffer = ''
        let currentEvent = ''
        let accumulatedContent = ''

        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          buffer += decoder.decode(value, { stream: true })

          // Process complete SSE lines
          const lines = buffer.split('\n')
          buffer = lines.pop() ?? '' // keep incomplete last line

          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEvent = line.slice(7).trim()
            } else if (line.startsWith('data: ')) {
              const dataStr = line.slice(6)
              const event = parseSSELine(currentEvent, dataStr)
              if (!event) continue

              if (event.type === 'token') {
                const text = (event.data.text as string) ?? ''
                accumulatedContent += text
                setStreamContent(accumulatedContent)
              } else if (event.type === 'done') {
                // Commit the accumulated content as a coach message
                const finalContent = accumulatedContent
                setMessages((prev) => [
                  ...prev,
                  {
                    id: `coach-${Date.now()}`,
                    role: 'coach',
                    content: finalContent,
                    timestamp: formatTime(new Date()),
                  },
                ])
                setStreamContent('')
                setIsStreaming(false)

                // D-03 confirmation gate: detect summary prefix
                if (isOnboardingComplete(finalContent)) {
                  setConfirmationText(finalContent)
                  setShowConfirmation(true)
                  setProgress(90)
                }
                currentEvent = ''
                accumulatedContent = ''
              } else if (event.type === 'error') {
                const msg = (event.data.message as string) ?? 'Stream error'
                setStreamError(msg)
                setIsStreaming(false)
              }
              // tool_start / tool_result: no UI needed for onboarding
              currentEvent = ''
            } else if (line === '') {
              // blank line resets event name (SSE spec)
              currentEvent = ''
            }
          }
        }
      } catch (err) {
        if ((err as Error).name === 'AbortError') return
        setStreamError('Connection lost. Please try again.')
        setIsStreaming(false)
      }
    },
    []
  )

  // Start onboarding stream on mount
  useEffect(() => {
    void runStream()
    return () => {
      abortRef.current?.abort()
    }
  }, [runStream])

  // ---------------------------------------------------------------------------
  // User sends a message during the interview
  // ---------------------------------------------------------------------------

  const handleSend = useCallback(
    (text: string) => {
      if (isStreaming || showConfirmation) return

      setMessages((prev) => [
        ...prev,
        {
          id: `user-${Date.now()}`,
          role: 'user',
          content: text,
          timestamp: formatTime(new Date()),
        },
      ])

      void runStream(text)
    },
    [isStreaming, showConfirmation, runStream]
  )

  // ---------------------------------------------------------------------------
  // User confirms the onboarding summary
  // ---------------------------------------------------------------------------

  const handleConfirm = useCallback(async () => {
    setIsConfirmed(true)
    setProgress(95)
    setShowConfirmation(false)

    // Add confirmation user message and trigger final save stream
    setMessages((prev) => [
      ...prev,
      {
        id: `user-confirm-${Date.now()}`,
        role: 'user',
        content: 'This looks right',
        timestamp: formatTime(new Date()),
      },
    ])

    // Run stream with confirmation message to trigger save_profile + generate_plan
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setIsStreaming(true)
    setStreamError(null)

    try {
      const url = await sseUrl('/onboarding/start')
      const res = await fetch(url, {
        method: 'POST',
        signal: controller.signal,
        headers: {
          Accept: 'text/event-stream',
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: 'This looks right. Please save my profile and generate my plan.' }),
      })

      if (!res.ok || !res.body) {
        setIsStreaming(false)
        await pollForProfile()
        return
      }

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let currentEvent = ''
      let accumulatedContent = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim()
          } else if (line.startsWith('data: ')) {
            const dataStr = line.slice(6)
            const event = parseSSELine(currentEvent, dataStr)
            if (!event) { currentEvent = ''; continue }

            if (event.type === 'token') {
              accumulatedContent += (event.data.text as string) ?? ''
              setStreamContent(accumulatedContent)
            } else if (event.type === 'done') {
              setStreamContent('')
              setIsStreaming(false)
              setProgress(100)
              // D-02: poll for profile then navigate to Today
              await pollForProfile()
              return
            }
            currentEvent = ''
          } else if (line === '') {
            currentEvent = ''
          }
        }
      }
    } catch (err) {
      if ((err as Error).name === 'AbortError') return
      setIsStreaming(false)
      await pollForProfile()
    }
  }, [queryClient, navigate])

  async function pollForProfile() {
    // Poll GET /profiles/me; once a profile exists, invalidate and navigate to Today (D-02)
    for (let i = 0; i < 10; i++) {
      try {
        const profile = await getProfileMe()
        if (profile) {
          queryClient.invalidateQueries({ queryKey: ['profile'] })
          navigate('/', { replace: true })
          return
        }
      } catch {
        // continue polling
      }
      await new Promise((r) => setTimeout(r, 1500))
    }
    // Timeout: navigate anyway and let the gate handle it
    navigate('/', { replace: true })
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        minHeight: '100vh',
        backgroundColor: 'var(--color-surface)',
      }}
    >
      {/* Progress bar */}
      <div
        style={{
          height: '4px',
          backgroundColor: 'var(--color-line-2)',
          position: 'sticky',
          top: 0,
          zIndex: 10,
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${progress}%`,
            backgroundColor: 'var(--color-blue-6)',
            transition: 'width 0.5s ease-out',
          }}
        />
      </div>

      {/* Centered column: max 640px on desktop */}
      <div
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          maxWidth: '640px',
          width: '100%',
          margin: '0 auto',
          height: '100%',
        }}
      >
        {/* Message list */}
        <div
          ref={scrollRef}
          style={{
            flex: 1,
            overflowY: 'auto',
            padding: '16px 16px 8px',
          }}
        >
          {messages.map((msg) => (
            <ChatBubble
              key={msg.id}
              role={msg.role === 'user' ? 'user' : 'coach'}
              timestamp={msg.timestamp}
            >
              {msg.content}
            </ChatBubble>
          ))}

          {/* In-flight stream */}
          {isStreaming && streamContent && (
            <ChatBubble role="coach">{streamContent}</ChatBubble>
          )}
          {isStreaming && !streamContent && (
            <ChatBubble role="coach" isStreaming />
          )}

          {/* Confirmation summary card */}
          {showConfirmation && (
            <div
              style={{
                backgroundColor: 'var(--color-bg-2)',
                border: '1px solid var(--color-line)',
                borderRadius: '12px',
                padding: '16px',
                marginTop: '12px',
              }}
            >
              <p
                style={{
                  margin: '0 0 12px',
                  fontSize: '15px',
                  color: 'var(--color-ink)',
                  whiteSpace: 'pre-wrap',
                  lineHeight: '1.6',
                }}
              >
                {confirmationText}
              </p>

              <div
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '8px',
                }}
              >
                <button
                  onClick={() => void handleConfirm()}
                  style={{
                    padding: '12px 20px',
                    borderRadius: '8px',
                    border: 'none',
                    backgroundColor: 'var(--color-blue-6)',
                    color: 'var(--color-surface)',
                    fontSize: '15px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    fontFamily: 'var(--font-family-sans)',
                  }}
                >
                  This looks right
                </button>
                <button
                  onClick={() => {
                    setShowConfirmation(false)
                    handleSend('I need to edit a detail')
                  }}
                  style={{
                    padding: '8px 20px',
                    borderRadius: '8px',
                    border: 'none',
                    background: 'none',
                    color: 'var(--color-blue-7)',
                    fontSize: '14px',
                    cursor: 'pointer',
                    fontFamily: 'var(--font-family-sans)',
                  }}
                >
                  Edit a detail
                </button>
              </div>
            </div>
          )}

          {/* Error state */}
          {streamError && (
            <div
              style={{
                padding: '8px 12px',
                marginTop: '8px',
                backgroundColor: 'var(--color-warm-soft)',
                border: '1px solid var(--color-amber)',
                borderRadius: '8px',
              }}
            >
              <span
                style={{
                  fontSize: '13px',
                  color: 'var(--color-warn)',
                }}
              >
                Connection lost. Reconnecting...
              </span>
            </div>
          )}
        </div>

        {/* Input area: hidden during confirmation */}
        {!showConfirmation && !isConfirmed && (
          <ChatInput
            onSend={handleSend}
            disabled={isStreaming}
            placeholder="Reply to your coach..."
          />
        )}
      </div>
    </div>
  )
}
