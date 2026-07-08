import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSSEStream } from '@/hooks/useSSEStream'

// ---------------------------------------------------------------------------
// MockEventSource
// ---------------------------------------------------------------------------

class MockEventSource {
  static lastInstance: MockEventSource | null = null
  private _listeners: Map<string, EventListener[]> = new Map()
  close = vi.fn()

  constructor(public url: string) {
    MockEventSource.lastInstance = this
  }

  addEventListener(type: string, listener: EventListener) {
    const list = this._listeners.get(type) ?? []
    list.push(listener)
    this._listeners.set(type, list)
  }

  dispatch(type: string, data?: unknown) {
    const listeners = this._listeners.get(type) ?? []
    const event =
      data !== undefined
        ? new MessageEvent(type, { data: JSON.stringify(data) })
        : new Event(type)
    for (const listener of listeners) {
      listener(event)
    }
  }
}

// ---------------------------------------------------------------------------
// Setup / teardown
// ---------------------------------------------------------------------------

beforeEach(() => {
  MockEventSource.lastInstance = null
  vi.stubGlobal('EventSource', MockEventSource)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useSSEStream', () => {
  it('returns initial state when url is null', () => {
    const { result } = renderHook(() => useSSEStream(null))
    expect(result.current).toEqual({
      content: '',
      isDone: false,
      isThinking: false,
      error: null,
    })
  })

  it('does NOT create an EventSource when url is null', () => {
    renderHook(() => useSSEStream(null))
    expect(MockEventSource.lastInstance).toBeNull()
  })

  it('creates an EventSource with the provided URL', () => {
    const url = 'http://localhost:8000/chat/stream?conversation_id=conv-1&message=hi'
    renderHook(() => useSSEStream(url))
    expect(MockEventSource.lastInstance).not.toBeNull()
    expect(MockEventSource.lastInstance?.url).toBe(url)
  })

  it('accumulates text from multiple token events into content', () => {
    const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
    const es = MockEventSource.lastInstance!

    act(() => {
      es.dispatch('token', { text: 'Hello' })
      es.dispatch('token', { text: ' world' })
    })

    expect(result.current.content).toBe('Hello world')
  })

  it('sets isThinking=true on tool_start event', () => {
    const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
    const es = MockEventSource.lastInstance!

    act(() => {
      es.dispatch('tool_start')
    })

    expect(result.current.isThinking).toBe(true)
  })

  it('sets isThinking=false on tool_result event after tool_start', () => {
    const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
    const es = MockEventSource.lastInstance!

    act(() => {
      es.dispatch('tool_start')
    })
    act(() => {
      es.dispatch('tool_result')
    })

    expect(result.current.isThinking).toBe(false)
  })

  it('sets isDone=true and calls es.close() on done event', () => {
    const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
    const es = MockEventSource.lastInstance!

    act(() => {
      es.dispatch('done')
    })

    expect(result.current.isDone).toBe(true)
    expect(es.close).toHaveBeenCalledTimes(1)
  })

  it('WR-002: does NOT set error when error event fires after done', () => {
    const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
    const es = MockEventSource.lastInstance!

    act(() => {
      es.dispatch('done')
    })
    act(() => {
      es.dispatch('error', { code: 'stream_closed', message: 'Connection reset' })
    })

    expect(result.current.error).toBeNull()
  })

  // -------------------------------------------------------------------------
  // Retry-with-backoff (item 2, D-02): a single error event must NOT
  // immediately surface setError. It silently retries (new EventSource)
  // after a backoff delay; only after MAX_RETRIES (2) consecutive error
  // events is the terminal error state surfaced.
  // -------------------------------------------------------------------------

  it('a single error event does NOT call setError immediately -- it retries after backoff', () => {
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
      const es = MockEventSource.lastInstance!

      act(() => {
        es.dispatch('error', { code: 'upstream_error', message: 'Internal server error' })
      })

      // Still within the silent retry window -- no error surfaced, old ES closed
      expect(result.current.error).toBeNull()
      expect(es.close).toHaveBeenCalledTimes(1)
      expect(MockEventSource.lastInstance).toBe(es) // retry hasn't opened yet

      act(() => {
        vi.advanceTimersByTime(500) // BACKOFF_MS[0]
      })

      // A new EventSource was opened for the retry attempt
      expect(MockEventSource.lastInstance).not.toBe(es)
      expect(result.current.error).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  it('after MAX_RETRIES (2) consecutive error events, setError fires with the terminal message and isThinking is false', () => {
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useSSEStream('http://localhost/stream'))

      act(() => {
        MockEventSource.lastInstance!.dispatch('tool_start')
      })
      expect(result.current.isThinking).toBe(true)

      // Attempt 0 fails -> silent retry after 500ms
      act(() => {
        MockEventSource.lastInstance!.dispatch('error', { message: 'fail 1' })
      })
      expect(result.current.error).toBeNull()
      act(() => {
        vi.advanceTimersByTime(500)
      })

      // Attempt 1 fails -> silent retry after 1500ms
      act(() => {
        MockEventSource.lastInstance!.dispatch('error', { message: 'fail 2' })
      })
      expect(result.current.error).toBeNull()
      act(() => {
        vi.advanceTimersByTime(1500)
      })

      // Attempt 2 (final) fails -> retries exhausted, terminal error surfaces
      act(() => {
        MockEventSource.lastInstance!.dispatch('error', { message: 'fail 3 terminal' })
      })

      expect(result.current.error).toBe('fail 3 terminal')
      expect(result.current.isThinking).toBe(false)
    } finally {
      vi.useRealTimers()
    }
  })

  it('falls back to "Connection failed." when the terminal error event has no parseable data', () => {
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useSSEStream('http://localhost/stream'))

      act(() => {
        // Plain Event has no .data; JSON.parse(undefined) throws each time
        MockEventSource.lastInstance!.dispatch('error')
      })
      act(() => {
        vi.advanceTimersByTime(500)
      })
      act(() => {
        MockEventSource.lastInstance!.dispatch('error')
      })
      act(() => {
        vi.advanceTimersByTime(1500)
      })
      act(() => {
        MockEventSource.lastInstance!.dispatch('error')
      })

      expect(result.current.error).toBe('Connection failed.')
    } finally {
      vi.useRealTimers()
    }
  })

  it('an error event after streamCompleted (post-done) is ignored -- no retry attempt is made', () => {
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
      const es = MockEventSource.lastInstance!

      act(() => {
        es.dispatch('done')
      })
      const instancesBeforeError = MockEventSource.lastInstance
      act(() => {
        es.dispatch('error', { code: 'stream_closed', message: 'Connection reset' })
      })
      act(() => {
        vi.advanceTimersByTime(2000)
      })

      expect(result.current.error).toBeNull()
      // No retry EventSource was opened for the post-done error
      expect(MockEventSource.lastInstance).toBe(instancesBeforeError)
    } finally {
      vi.useRealTimers()
    }
  })

  it('retryCount resets when the url changes -- a fresh single error on the new url retries again rather than going terminal', () => {
    vi.useFakeTimers()
    try {
      const { result, rerender } = renderHook(
        ({ url }: { url: string }) => useSSEStream(url),
        { initialProps: { url: 'http://localhost/stream?msg=1' } },
      )

      // Exhaust retries on the first url (3 consecutive errors -> terminal)
      act(() => {
        MockEventSource.lastInstance!.dispatch('error', { message: 'e1' })
      })
      act(() => {
        vi.advanceTimersByTime(500)
      })
      act(() => {
        MockEventSource.lastInstance!.dispatch('error', { message: 'e2' })
      })
      act(() => {
        vi.advanceTimersByTime(1500)
      })
      act(() => {
        MockEventSource.lastInstance!.dispatch('error', { message: 'e3 terminal' })
      })
      expect(result.current.error).toBe('e3 terminal')

      // New url -- state resets, including retryCount
      rerender({ url: 'http://localhost/stream?msg=2' })
      expect(result.current.error).toBeNull()

      // A single error on the fresh url must retry again, NOT go straight terminal
      act(() => {
        MockEventSource.lastInstance!.dispatch('error', { message: 'fresh fail' })
      })
      expect(result.current.error).toBeNull()
    } finally {
      vi.useRealTimers()
    }
  })

  // -------------------------------------------------------------------------
  // Rate limiting (item 6, D-02/D-03, 10-UI-SPEC interaction rule): a
  // code: "rate_limited" error event must skip the silent retry entirely and
  // go straight to the terminal error state -- retrying immediately against
  // a rate limit compounds the problem it's meant to prevent.
  // -------------------------------------------------------------------------

  it('a rate_limited error event sets the terminal error immediately and does NOT schedule a retry', () => {
    vi.useFakeTimers()
    try {
      const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
      const es = MockEventSource.lastInstance!

      act(() => {
        es.dispatch('tool_start')
      })
      expect(result.current.isThinking).toBe(true)

      act(() => {
        es.dispatch('error', {
          code: 'rate_limited',
          message: "You're sending messages a bit fast. Wait a moment and try again.",
        })
      })

      // Terminal error surfaces immediately -- no silent-retry delay needed.
      expect(result.current.error).toBe(
        "You're sending messages a bit fast. Wait a moment and try again."
      )
      expect(result.current.isThinking).toBe(false)

      // No retry EventSource was opened, even after the normal backoff windows elapse.
      const instanceAfterRateLimit = MockEventSource.lastInstance
      act(() => {
        vi.advanceTimersByTime(2000)
      })
      expect(MockEventSource.lastInstance).toBe(instanceAfterRateLimit)
    } finally {
      vi.useRealTimers()
    }
  })

  it('falls back to the default rate-limit copy when the rate_limited event has no message', () => {
    const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
    const es = MockEventSource.lastInstance!

    act(() => {
      es.dispatch('error', { code: 'rate_limited' })
    })

    expect(result.current.error).toBe(
      "You're sending messages a bit fast. Wait a moment and try again."
    )
  })

  it('closes the EventSource on unmount', () => {
    const { unmount } = renderHook(() => useSSEStream('http://localhost/stream'))
    const es = MockEventSource.lastInstance!

    unmount()

    expect(es.close).toHaveBeenCalled()
  })

  it('resets content, isDone, error and opens a new EventSource when URL prop changes', () => {
    const { result, rerender } = renderHook(
      ({ url }: { url: string | null }) => useSSEStream(url),
      { initialProps: { url: 'http://localhost/stream?msg=1' } },
    )
    const firstEs = MockEventSource.lastInstance!

    act(() => {
      firstEs.dispatch('token', { text: 'First response' })
    })
    expect(result.current.content).toBe('First response')

    rerender({ url: 'http://localhost/stream?msg=2' })

    expect(result.current.content).toBe('')
    expect(result.current.isDone).toBe(false)
    expect(result.current.error).toBeNull()
    expect(MockEventSource.lastInstance).not.toBe(firstEs)
  })
})
