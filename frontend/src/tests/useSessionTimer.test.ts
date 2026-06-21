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
    const startEpoch = Date.now()
    const { result } = renderHook(() => useSessionTimer(60, startEpoch))
    expect(result.current.secondsLeft).toBe(60)
  })

  it('counts down from totalSeconds using Date.now deltas', () => {
    const startEpoch = Date.now()
    const { result } = renderHook(() => useSessionTimer(60, startEpoch))

    act(() => {
      vi.advanceTimersByTime(10_000)
    })

    expect(result.current.secondsLeft).toBe(50)
  })

  it('resyncs on visibilitychange instead of resetting or freezing', () => {
    const startEpoch = Date.now()
    const { result } = renderHook(() => useSessionTimer(60, startEpoch))

    // Advance 5 seconds while visible
    act(() => {
      vi.advanceTimersByTime(5_000)
    })

    // Go hidden
    act(() => {
      Object.defineProperty(document, 'hidden', { value: true, configurable: true })
      document.dispatchEvent(new Event('visibilitychange'))
    })

    // Advance 20 seconds while hidden
    act(() => {
      vi.advanceTimersByTime(20_000)
    })

    // Come back visible
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
    const startEpoch = Date.now()
    const { result } = renderHook(() => useSessionTimer(5, startEpoch))

    act(() => {
      vi.advanceTimersByTime(30_000)
    })

    expect(result.current.secondsLeft).toBe(0)
  })
})
