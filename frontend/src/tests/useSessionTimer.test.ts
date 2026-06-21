import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSessionTimer } from '@/hooks/useSessionTimer'

describe('useSessionTimer (IOS-02)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('starts at totalSeconds', () => {
    const { result } = renderHook(() => useSessionTimer(60))
    expect(result.current.secondsLeft).toBe(60)
  })

  it('counts down from totalSeconds using Date.now deltas', () => {
    const { result } = renderHook(() => useSessionTimer(60))

    act(() => {
      vi.advanceTimersByTime(10_000)
    })

    expect(result.current.secondsLeft).toBe(50)
  })

  it('resyncs on visibilitychange instead of resetting or freezing', () => {
    const { result } = renderHook(() => useSessionTimer(60))

    // Advance 5 seconds while visible
    act(() => {
      vi.advanceTimersByTime(5_000)
    })

    // Go hidden — timer should record paused elapsed
    act(() => {
      Object.defineProperty(document, 'hidden', { value: true, configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })

    // Advance 20 seconds while hidden (background — timer should still accumulate in pausedElapsedRef)
    act(() => {
      vi.advanceTimersByTime(20_000)
    })

    // Come back visible — startRef resets to now
    act(() => {
      Object.defineProperty(document, 'hidden', { value: false, configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })

    // Advance one tick to trigger re-render
    act(() => {
      vi.advanceTimersByTime(250)
    })

    // Total elapsed = 5 + 20 = 25s; secondsLeft should be ~35 (within 1s)
    expect(result.current.secondsLeft).toBeGreaterThanOrEqual(34)
    expect(result.current.secondsLeft).toBeLessThanOrEqual(36)
  })

  it('never goes below zero', () => {
    const { result } = renderHook(() => useSessionTimer(5))

    act(() => {
      vi.advanceTimersByTime(30_000)
    })

    expect(result.current.secondsLeft).toBe(0)
  })

  it('advance() resets to totalSeconds', () => {
    const { result } = renderHook(() => useSessionTimer(60))

    act(() => {
      vi.advanceTimersByTime(10_000)
    })

    expect(result.current.secondsLeft).toBe(50)

    act(() => {
      result.current.advance()
    })

    expect(result.current.secondsLeft).toBe(60)
  })
})
