import { useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { checkAdaptations } from '../lib/api'

// ---------------------------------------------------------------------------
// ADAPT-04 weekly adaptation check trigger.
//
// POST /adaptations/check exists but (per the v1.0 milestone audit) has no
// caller anywhere. This hook wires it up as a client-initiated lazy trigger:
// mounted once from AppLayout (the mount-once layout route, covering every
// entry point), fires at most once per 7-day window, fire-and-forget (no
// loading state, no toast, no retry loop).
//
// D-05 (highest-risk decision, see 13-RESEARCH.md Pitfall 3): the throttle
// timestamp is written ONLY on a successful resolve. A failed check (network
// blip, transient 401, etc.) must NOT advance the timestamp, otherwise a
// single bad request could silently suppress the check for a full week.
//
// CR-01 (13-REVIEW.md): the throttle timestamp above is only a "don't check
// again for 7 days" gate -- it says nothing about a check already in flight.
// Without a synchronous claim, an AppLayout remount (route navigation), a
// React StrictMode double-invoke, or a second browser tab can all observe
// the same "check needed" state and fire a second, fully independent
// POST /adaptations/check while the first is still resolving, which can
// duplicate-apply an adaptation server-side. INFLIGHT_KEY is written
// synchronously (before the async call starts) so any concurrent
// mount/tab sees the claim and skips.
// ---------------------------------------------------------------------------

const THROTTLE_KEY = 'pacerai_adaptation_checked_at'
const THROTTLE_MS = 7 * 24 * 60 * 60 * 1000 // 7 days (D-03)

const INFLIGHT_KEY = 'pacerai_adaptation_check_inflight'
const INFLIGHT_TTL_MS = 60_000 // generous upper bound for one check to resolve

function getLastChecked(): number | null {
  try {
    const raw = localStorage.getItem(THROTTLE_KEY)
    return raw ? new Date(raw).getTime() : null
  } catch {
    return null
  }
}

function setLastChecked(iso: string): void {
  try {
    localStorage.setItem(THROTTLE_KEY, iso)
  } catch {
    // QuotaExceededError — nothing we can do, mirrors sessionPersistence.ts
  }
}

function getInflightAt(): number {
  try {
    const raw = localStorage.getItem(INFLIGHT_KEY)
    return raw ? Number(raw) : 0
  } catch {
    return 0
  }
}

function claimInflight(now: number): void {
  try {
    localStorage.setItem(INFLIGHT_KEY, String(now))
  } catch {
    // QuotaExceededError — nothing we can do, mirrors sessionPersistence.ts
  }
}

function clearInflight(): void {
  try {
    localStorage.removeItem(INFLIGHT_KEY)
  } catch {
    // ignore
  }
}

export function useAdaptationCheck(): void {
  const queryClient = useQueryClient()

  useEffect(() => {
    const lastChecked = getLastChecked()
    const now = Date.now()
    if (lastChecked !== null && now - lastChecked < THROTTLE_MS) return

    // CR-01: claim synchronously (shared across tabs/remounts via
    // localStorage) before the async call starts, so a concurrent
    // mount/tab sees the claim and skips instead of firing a duplicate
    // POST /adaptations/check.
    const inflightAt = getInflightAt()
    if (now - inflightAt < INFLIGHT_TTL_MS) return
    claimInflight(now)

    checkAdaptations()
      .then(() => {
        setLastChecked(new Date().toISOString()) // D-05: only on success

        // WR-01 (13-REVIEW.md): a successful check may have applied a
        // micro/macro adjustment server-side, mutating adaptations/
        // sessions/rides/pmc data. Invalidate the affected caches so an
        // already-mounted ProgressScreen/TodayScreen/AgendaScreen reflects
        // it without depending on a window refocus to trigger a refetch.
        queryClient.invalidateQueries({ queryKey: ['adaptations'] })
        queryClient.invalidateQueries({ queryKey: ['rides'] })
        queryClient.invalidateQueries({ queryKey: ['pmc-history'] })
        queryClient.invalidateQueries({ queryKey: ['pmc', 'latest'] })
        queryClient.invalidateQueries({ queryKey: ['session', 'today'] })
        queryClient.invalidateQueries({ queryKey: ['sessions', 'upcoming'] })
      })
      .catch(() => {
        // D-05: fail silently, do not update timestamp, no retry loop (D-04)
      })
      .finally(() => {
        clearInflight()
      })
  }, [queryClient])
}
