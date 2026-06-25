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

  it('sets error from data.message on error event before done', () => {
    const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
    const es = MockEventSource.lastInstance!

    act(() => {
      es.dispatch('error', { code: 'upstream_error', message: 'Internal server error' })
    })

    expect(result.current.error).toBe('Internal server error')
  })

  it('falls back to "Stream error" when error event has no parseable data', () => {
    const { result } = renderHook(() => useSSEStream('http://localhost/stream'))
    const es = MockEventSource.lastInstance!

    act(() => {
      // Plain Event has no .data; JSON.parse(undefined) throws, triggering fallback
      es.dispatch('error')
    })

    expect(result.current.error).toBe('Stream error')
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
