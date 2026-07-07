import type { CSSProperties } from 'react'
import { AlertCircle, RotateCw } from 'lucide-react'

// ---------------------------------------------------------------------------
// StreamErrorBanner — shared terminal-error banner for both chat and
// onboarding SSE consumers (09-UI-SPEC.md Component Spec #1). Only rendered
// after the silent 1-2x auto-retry inside useSSEStream / OnboardingScreen has
// already been exhausted -- never on the first transient error.
//
// variant="chat" (default): banner sits above ChatInput -- borderTop only.
// variant="onboarding": banner sits inline in the message column -- full
// border + borderRadius, matching the existing streamError block's container
// treatment (09-06 consumer).
// ---------------------------------------------------------------------------

export interface StreamErrorBannerProps {
  message: string
  onRetry: () => void
  variant?: 'chat' | 'onboarding'
  style?: CSSProperties
}

export function StreamErrorBanner({
  message,
  onRetry,
  variant = 'chat',
  style,
}: StreamErrorBannerProps) {
  const containerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: '8px',
    padding: '8px 16px',
    backgroundColor: 'var(--color-bg-2)',
    ...(variant === 'onboarding'
      ? { border: '1px solid var(--color-bad)', borderRadius: '8px' }
      : { borderTop: '1px solid var(--color-bad)' }),
    ...style,
  }

  return (
    <div style={containerStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
        <AlertCircle size={16} color="var(--color-bad)" />
        <span style={{ fontSize: '13px', fontWeight: 400, color: 'var(--color-bad)' }}>
          {message}
        </span>
      </div>
      <button
        type="button"
        onClick={onRetry}
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '4px',
          padding: '6px 12px',
          borderRadius: '6px',
          border: 'none',
          backgroundColor: 'var(--color-blue-6)',
          color: 'var(--color-surface)',
          fontSize: '14px',
          fontWeight: 600,
          cursor: 'pointer',
        }}
      >
        <RotateCw size={14} />
        Retry
      </button>
    </div>
  )
}
