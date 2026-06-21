import type { ReactNode } from 'react'
import Markdown from 'react-markdown'

// ---------------------------------------------------------------------------
// ChatBubble — role-based message bubble for coach, user, adaptation, and
// capability-gap messages. Never uses dangerouslySetInnerHTML (T-04-19).
// react-markdown renders to React elements, satisfying T-04-19.
// ---------------------------------------------------------------------------

export type BubbleRole = 'coach' | 'user' | 'adaptation' | 'capability-gap'

export interface ChatBubbleProps {
  role: BubbleRole
  children?: ReactNode
  timestamp?: string
  /** When true, renders an animated streaming ellipsis instead of children */
  isStreaming?: boolean
}

function StreamingEllipsis() {
  return (
    <span
      className="inline-flex items-center gap-0.5"
      aria-label="Coach is typing"
    >
      <span
        className="w-1.5 h-1.5 rounded-full animate-bounce"
        style={{
          backgroundColor: 'var(--color-ink-3)',
          animationDelay: '0ms',
          animationDuration: '900ms',
        }}
      />
      <span
        className="w-1.5 h-1.5 rounded-full animate-bounce"
        style={{
          backgroundColor: 'var(--color-ink-3)',
          animationDelay: '150ms',
          animationDuration: '900ms',
        }}
      />
      <span
        className="w-1.5 h-1.5 rounded-full animate-bounce"
        style={{
          backgroundColor: 'var(--color-ink-3)',
          animationDelay: '300ms',
          animationDuration: '900ms',
        }}
      />
    </span>
  )
}

export function ChatBubble({
  role,
  children,
  timestamp,
  isStreaming = false,
}: ChatBubbleProps) {
  const isUser = role === 'user'

  // Bubble background and radius styles
  const bubbleBg = isUser
    ? 'var(--color-blue-1)'
    : 'var(--color-bg-2)'

  const borderRadius = isUser
    ? '12px 12px 4px 12px'
    : '12px 12px 12px 4px'

  // Left border accent for adaptation and capability-gap
  const leftBorderStyle: React.CSSProperties =
    role === 'adaptation'
      ? { borderLeft: '4px solid var(--color-blue-6)' }
      : role === 'capability-gap'
        ? { borderLeft: '4px solid var(--color-amber)' }
        : {}

  return (
    <div
      className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} mb-3`}
    >
      <div
        style={{
          backgroundColor: bubbleBg,
          borderRadius,
          padding: '8px 16px',
          color: 'var(--color-ink)',
          maxWidth: '80%',
          wordBreak: 'break-word',
          ...leftBorderStyle,
        }}
      >
        {isStreaming ? (
          <StreamingEllipsis />
        ) : isUser ? (
          <span
            style={{
              fontSize: '16px',
              lineHeight: '1.5',
              whiteSpace: 'pre-wrap',
            }}
          >
            {children}
          </span>
        ) : (
          <div
            style={{ fontSize: '16px', lineHeight: '1.5' }}
            className="markdown-body"
          >
            <Markdown>{typeof children === 'string' ? children : undefined}</Markdown>
          </div>
        )}
      </div>
      {timestamp && (
        <span
          className="mt-1 px-1"
          style={{
            fontSize: '12px',
            color: 'var(--color-ink-3)',
            lineHeight: '1.3',
          }}
        >
          {timestamp}
        </span>
      )}
    </div>
  )
}
