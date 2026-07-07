import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { readFileSync } from 'node:fs'
import path from 'node:path'

// Mock supabase before any module that imports it
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } }),
    },
  },
}))

// Mock the API module: only getProfileMe is used by OnboardingScreen (via
// pollForProfile), which must NOT be called when the confirm-stream fails
// with a terminal error (item 13/D-05 -- the stuck-spinner bug).
vi.mock('../lib/api', () => ({
  getProfileMe: vi.fn(),
}))

import {
  OnboardingScreen,
  isOnboardingComplete,
  ONBOARDING_COMPLETION_MARKER,
} from '../screens/OnboardingScreen'
import { getProfileMe } from '../lib/api'

// ---------------------------------------------------------------------------
// Tests for isOnboardingComplete confirmation-gate detection.
//
// This locks the string-prefix detection so a copy change to the marker
// cannot silently break the post-onboarding redirect (D-02 / D-03).
// Both the runtime check and this test share ONBOARDING_COMPLETION_MARKER
// as a single source of truth.
// ---------------------------------------------------------------------------

describe('isOnboardingComplete', () => {
  it('returns true when message begins with the confirmation marker', () => {
    const msg = `${ONBOARDING_COMPLETION_MARKER} captured about you:\n\nGoals: General fitness...`
    expect(isOnboardingComplete(msg)).toBe(true)
  })

  it('returns true for the exact marker phrase from the system prompt', () => {
    expect(isOnboardingComplete('Here is what I have for you.')).toBe(true)
  })

  it('returns true when message has leading whitespace before the marker', () => {
    expect(isOnboardingComplete('  Here is what I have collected.')).toBe(true)
  })

  it('returns false for an ordinary mid-interview coach message', () => {
    expect(isOnboardingComplete('What days can you ride?')).toBe(false)
  })

  it('returns false for an empty string', () => {
    expect(isOnboardingComplete('')).toBe(false)
  })

  it('returns false when marker appears mid-sentence', () => {
    expect(
      isOnboardingComplete('Great, I will note that. Here is what I have so far.')
    ).toBe(false)
  })

  it('returns false for unrelated coaching messages', () => {
    expect(
      isOnboardingComplete('How many hours per week can you train?')
    ).toBe(false)
  })

  it('ONBOARDING_COMPLETION_MARKER matches the system prompt string exactly', () => {
    // The system prompt uses exactly "Here is what I have" (case-sensitive)
    expect(ONBOARDING_COMPLETION_MARKER).toBe('Here is what I have')
  })
})

// ---------------------------------------------------------------------------
// Item 13 (D-05): OnboardingScreen mirrors the same retry-then-terminal-error
// recovery as chat's useSSEStream, using its own fetch + ReadableStream
// transport (Pitfall 1 -- EventSource cannot POST or set Authorization).
// ---------------------------------------------------------------------------

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

// Builds a fake fetch Response body exposing getReader(), matching the
// subset of the ReadableStream API OnboardingScreen actually consumes,
// without depending on the test environment providing a real ReadableStream.
function makeSSEBody(events: Array<{ event: string; data: unknown }>) {
  let chunk = ''
  for (const { event, data } of events) {
    chunk += `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
  }
  let sent = false
  return {
    getReader() {
      return {
        read: async () => {
          if (!sent) {
            sent = true
            return { done: false, value: new TextEncoder().encode(chunk) }
          }
          return { done: true, value: undefined }
        },
      }
    },
  }
}

function makeSuccessResponse(coachText: string) {
  return {
    ok: true,
    body: makeSSEBody([
      { event: 'token', data: { text: coachText } },
      { event: 'done', data: {} },
    ]),
  } as unknown as Response
}

function makeFailureResponse() {
  return { ok: false, body: null } as unknown as Response
}

describe('OnboardingScreen stream error recovery (item 13, D-05)', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    vi.mocked(getProfileMe).mockReset()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('an initial-message stream error retries silently up to 2 times (500ms/1500ms backoff) before any banner appears; after exhaustion, StreamErrorBanner renders with Retry and isStreaming is false', async () => {
    fetchMock.mockResolvedValue(makeFailureResponse())

    // Fake timers must be installed BEFORE render, so the very first retry's
    // setTimeout (scheduled once the mount-triggered fetch resolves) is
    // captured by the fake clock instead of a real one.
    vi.useFakeTimers()
    try {
      render(<OnboardingScreen />, { wrapper: Wrapper })

      // Flush the mount effect's runStream() through its awaits
      // (supabase.auth.getSession() then fetch()) -- first attempt.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0)
      })
      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(screen.queryByRole('button', { name: /retry/i })).toBeNull()

      // Retry #1 fires after the 500ms backoff -- still silent.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(500)
      })
      expect(fetchMock).toHaveBeenCalledTimes(2)
      expect(screen.queryByRole('button', { name: /retry/i })).toBeNull()

      // Retry #2 fires after the 1500ms backoff -- still silent.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500)
      })
      expect(fetchMock).toHaveBeenCalledTimes(3)

      // Retries exhausted (MAX_RETRIES=2): terminal error + Retry, spinner clears.
      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
      expect(screen.getByText('Could not connect to coach. Try again.')).toBeInTheDocument()
      expect(screen.getByLabelText('Message input')).not.toBeDisabled()
    } finally {
      vi.useRealTimers()
    }
  })

  it('clicking Retry re-invokes the failed initial-stream call and clears the banner optimistically', async () => {
    fetchMock.mockResolvedValue(makeFailureResponse())

    vi.useFakeTimers()
    try {
      render(<OnboardingScreen />, { wrapper: Wrapper })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0)
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(500)
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500)
      })

      expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
      const callsBeforeRetry = fetchMock.mock.calls.length

      const retryButton = screen.getByRole('button', { name: /retry/i })
      // Clicking synchronously clears the banner (runStream's setStreamError(null)
      // runs before its first await), verified before flushing further microtasks.
      act(() => {
        fireEvent.click(retryButton)
      })
      expect(screen.queryByRole('button', { name: /retry/i })).toBeNull()

      // Flush the new attempt's awaits (getSession then fetch) to confirm
      // the failed call was actually re-invoked.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(0)
      })
      expect(fetchMock.mock.calls.length).toBeGreaterThan(callsBeforeRetry)
    } finally {
      vi.useRealTimers()
    }
  })

  it('the confirm-stream (!res.ok) path sets a terminal error instead of falling through to pollForProfile -- the spinner does not stick', async () => {
    let callCount = 0
    fetchMock.mockImplementation(async () => {
      callCount++
      // First call: the initial onboarding stream succeeds and reaches the
      // confirmation gate. Every subsequent call (the confirm-stream) fails.
      if (callCount === 1) {
        return makeSuccessResponse('Here is what I have for you. Ready to confirm?')
      }
      return makeFailureResponse()
    })

    render(<OnboardingScreen />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /this looks right/i })).toBeInTheDocument()
    })

    const confirmButton = screen.getByRole('button', { name: /this looks right/i })

    vi.useFakeTimers()
    try {
      await act(async () => {
        fireEvent.click(confirmButton)
      })
      // Confirm-stream attempt #1 fails -> retry #1 scheduled.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(500)
      })
      // Confirm-stream attempt #2 fails -> retry #2 scheduled.
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500)
      })
    } finally {
      vi.useRealTimers()
    }

    // Confirm-stream attempt #3 fails -> retries exhausted -> terminal error.
    await waitFor(() => {
      expect(screen.getByText("Couldn't save your profile.")).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
    // The stuck-spinner bug: pollForProfile (and therefore getProfileMe) must
    // never be reached on a confirm-stream failure.
    expect(getProfileMe).not.toHaveBeenCalled()
  })

  it('clicking Retry re-invokes the failed confirm-stream call and clears the banner optimistically', async () => {
    let callCount = 0
    fetchMock.mockImplementation(async () => {
      callCount++
      if (callCount === 1) {
        return makeSuccessResponse('Here is what I have for you. Ready to confirm?')
      }
      return makeFailureResponse()
    })

    render(<OnboardingScreen />, { wrapper: Wrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /this looks right/i })).toBeInTheDocument()
    })

    vi.useFakeTimers()
    try {
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /this looks right/i }))
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(500)
      })
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1500)
      })
    } finally {
      vi.useRealTimers()
    }

    await waitFor(() => {
      expect(screen.getByText("Couldn't save your profile.")).toBeInTheDocument()
    })
    const callsBeforeRetry = fetchMock.mock.calls.length

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /retry/i }))
    })

    expect(screen.queryByText("Couldn't save your profile.")).toBeNull()
    expect(fetchMock.mock.calls.length).toBeGreaterThan(callsBeforeRetry)
    expect(getProfileMe).not.toHaveBeenCalled()
  })

  it('does not import useSSEStream (Pitfall 1 guard -- EventSource cannot POST or set Authorization, so the transport is not shared)', () => {
    const filePath = path.resolve(process.cwd(), 'src/screens/OnboardingScreen.tsx')
    const source = readFileSync(filePath, 'utf-8')
    // Comments are allowed (and expected) to cross-reference useSSEStream's
    // policy for sync -- only an actual import statement is disallowed.
    // `.*` (no dotAll flag) is intentionally line-scoped so a same-line
    // import match cannot bleed into unrelated content further down the file.
    expect(source).not.toMatch(/^\s*import\b.*useSSEStream/m)
  })
})
