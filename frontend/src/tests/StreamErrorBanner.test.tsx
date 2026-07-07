import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { StreamErrorBanner } from '@/components/chat/StreamErrorBanner'

// ---------------------------------------------------------------------------
// StreamErrorBanner: shared terminal-error banner (chat + onboarding, 09-06).
// ---------------------------------------------------------------------------

describe('StreamErrorBanner', () => {
  it('renders the passed message text', () => {
    render(<StreamErrorBanner message="Connection failed." onRetry={vi.fn()} />)
    expect(screen.getByText('Connection failed.')).toBeInTheDocument()
  })

  it('renders a Retry button', () => {
    render(<StreamErrorBanner message="Connection failed." onRetry={vi.fn()} />)
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('calls onRetry when the Retry button is clicked', () => {
    const onRetry = vi.fn()
    render(<StreamErrorBanner message="Connection failed." onRetry={onRetry} />)
    fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it('defaults to the chat variant (borderTop, no full border)', () => {
    const { container } = render(
      <StreamErrorBanner message="Connection failed." onRetry={vi.fn()} />,
    )
    const banner = container.firstChild as HTMLElement
    expect(banner.style.borderTop).toContain('var(--color-bad)')
  })

  it('onboarding variant renders a full border with borderRadius', () => {
    const { container } = render(
      <StreamErrorBanner
        message="Couldn't save your profile."
        onRetry={vi.fn()}
        variant="onboarding"
      />,
    )
    const banner = container.firstChild as HTMLElement
    expect(banner.style.border).toContain('var(--color-bad)')
    expect(banner.style.borderRadius).toBe('8px')
  })
})
