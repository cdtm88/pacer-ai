import { useRef, useState, type KeyboardEvent } from 'react'
import { Send } from 'lucide-react'

// ---------------------------------------------------------------------------
// ChatInput — textarea + icon send button pinned at the bottom of chat screens.
// Expands up to 4 lines. Disabled while a stream is in flight.
// ---------------------------------------------------------------------------

export interface ChatInputProps {
  onSend: (text: string) => void
  disabled?: boolean
  placeholder?: string
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Message your coach...',
}: ChatInputProps) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  function handleSend() {
    const trimmed = value.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setValue('')
    // Reset textarea height after clearing
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    // Send on Enter (without Shift for newline)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleInput() {
    const el = textareaRef.current
    if (!el) return
    // Auto-resize up to 4 lines (~96px at 24px line-height)
    el.style.height = 'auto'
    el.style.height = `${Math.min(el.scrollHeight, 96)}px`
  }

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'flex-end',
        gap: '8px',
        padding: '8px 16px',
        backgroundColor: 'var(--color-surface)',
        borderTop: '1px solid var(--color-line)',
      }}
    >
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        onInput={handleInput}
        disabled={disabled}
        placeholder={placeholder}
        rows={1}
        style={{
          flex: 1,
          resize: 'none',
          border: '1px solid var(--color-line)',
          borderRadius: '8px',
          padding: '8px 12px',
          fontSize: '16px',
          lineHeight: '1.5',
          color: 'var(--color-ink)',
          backgroundColor: 'var(--color-surface)',
          outline: 'none',
          fontFamily: 'var(--font-family-sans)',
          overflowY: 'auto',
          maxHeight: '96px',
          minHeight: '40px',
          opacity: disabled ? 0.6 : 1,
        }}
        aria-label="Message input"
      />
      <button
        onClick={handleSend}
        disabled={disabled || !value.trim()}
        aria-label="Send message"
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: '40px',
          height: '40px',
          borderRadius: '8px',
          border: 'none',
          backgroundColor:
            disabled || !value.trim()
              ? 'var(--color-line)'
              : 'var(--color-blue-6)',
          color: 'var(--color-surface)',
          cursor: disabled || !value.trim() ? 'not-allowed' : 'pointer',
          flexShrink: 0,
          transition: 'background-color 0.15s',
        }}
      >
        <Send size={18} />
      </button>
    </div>
  )
}
