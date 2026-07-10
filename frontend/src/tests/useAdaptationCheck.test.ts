import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useAdaptationCheck } from '@/hooks/useAdaptationCheck'
import * as api from '@/lib/api'

// ---------------------------------------------------------------------------
// ADAPT-04: weekly adaptation check trigger.
// Covers throttle window (D-03) and the D-05 silent-failure invariant --
// a rejected checkAdaptations() must NOT advance the throttle timestamp, so
// the next mount retries instead of being silently suppressed for 7 days.
// ---------------------------------------------------------------------------

const THROTTLE_KEY = 'pacerai_adaptation_checked_at'

vi.mock('@/lib/api', () => ({
  checkAdaptations: vi.fn(),
}))

describe('useAdaptationCheck (ADAPT-04)', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.mocked(api.checkAdaptations).mockReset()
  })

  it('calls checkAdaptations exactly once when no stored timestamp exists', async () => {
    vi.mocked(api.checkAdaptations).mockResolvedValue({})

    renderHook(() => useAdaptationCheck())

    await waitFor(() => expect(api.checkAdaptations).toHaveBeenCalledTimes(1))
  })

  it('does not call checkAdaptations when the last check was < 7 days ago', async () => {
    localStorage.setItem(THROTTLE_KEY, new Date().toISOString())

    renderHook(() => useAdaptationCheck())

    // Give any stray microtask a chance to run before asserting the negative.
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(api.checkAdaptations).not.toHaveBeenCalled()
  })

  it('calls checkAdaptations when the last check was 8 days ago (window elapsed)', async () => {
    vi.mocked(api.checkAdaptations).mockResolvedValue({})
    const eightDaysAgo = new Date(Date.now() - 8 * 24 * 60 * 60 * 1000)
    localStorage.setItem(THROTTLE_KEY, eightDaysAgo.toISOString())

    renderHook(() => useAdaptationCheck())

    await waitFor(() => expect(api.checkAdaptations).toHaveBeenCalledTimes(1))
  })

  it('writes a fresh ISO timestamp to localStorage on successful check', async () => {
    vi.mocked(api.checkAdaptations).mockResolvedValue({})

    renderHook(() => useAdaptationCheck())

    await waitFor(() => expect(api.checkAdaptations).toHaveBeenCalledTimes(1))
    await waitFor(() => {
      const stored = localStorage.getItem(THROTTLE_KEY)
      expect(stored).not.toBeNull()
      expect(Number.isNaN(new Date(stored as string).getTime())).toBe(false)
    })
  })

  it('does not update the localStorage timestamp on checkAdaptations failure (D-05)', async () => {
    vi.mocked(api.checkAdaptations).mockRejectedValue(new Error('network'))

    renderHook(() => useAdaptationCheck())

    await waitFor(() => expect(api.checkAdaptations).toHaveBeenCalledTimes(1))
    // Allow the .catch() microtask to settle before asserting the negative.
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(localStorage.getItem(THROTTLE_KEY)).toBeNull()
  })
})
