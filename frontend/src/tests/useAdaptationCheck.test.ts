import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { useAdaptationCheck } from '@/hooks/useAdaptationCheck'
import * as api from '@/lib/api'

// ---------------------------------------------------------------------------
// ADAPT-04: weekly adaptation check trigger.
// Covers throttle window (D-03) and the D-05 silent-failure invariant --
// a rejected checkAdaptations() must NOT advance the throttle timestamp, so
// the next mount retries instead of being silently suppressed for 7 days.
//
// 13-REVIEW.md CR-01: also covers the synchronous in-flight claim -- a
// second concurrent mount/tab must not fire a second POST while the first
// check is still resolving.
// ---------------------------------------------------------------------------

const THROTTLE_KEY = 'pacerai_adaptation_checked_at'
const INFLIGHT_KEY = 'pacerai_adaptation_check_inflight'

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

  it('CR-01: does not fire a second concurrent check while one is already in flight', async () => {
    // A pending (unresolved) mock simulates a check that is still in flight.
    let resolveCheck: (() => void) | undefined
    vi.mocked(api.checkAdaptations).mockReturnValue(
      new Promise((resolve) => {
        resolveCheck = () => resolve({})
      })
    )

    // First mount claims the in-flight lock and fires the request.
    renderHook(() => useAdaptationCheck())
    await waitFor(() => expect(api.checkAdaptations).toHaveBeenCalledTimes(1))
    expect(localStorage.getItem(INFLIGHT_KEY)).not.toBeNull()

    // A second mount (e.g. AppLayout remount from route navigation, or a
    // second tab) while the first check is still pending must see the claim
    // and skip -- call count stays at 1.
    renderHook(() => useAdaptationCheck())
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(api.checkAdaptations).toHaveBeenCalledTimes(1)

    resolveCheck?.()
    await waitFor(() => expect(localStorage.getItem(INFLIGHT_KEY)).toBeNull())
  })
})
