import { useEffect } from 'react'
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
// ---------------------------------------------------------------------------

const THROTTLE_KEY = 'pacerai_adaptation_checked_at'
const THROTTLE_MS = 7 * 24 * 60 * 60 * 1000 // 7 days (D-03)

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

export function useAdaptationCheck(): void {
  useEffect(() => {
    const lastChecked = getLastChecked()
    const now = Date.now()
    if (lastChecked !== null && now - lastChecked < THROTTLE_MS) return

    checkAdaptations()
      .then(() => {
        setLastChecked(new Date().toISOString()) // D-05: only on success
      })
      .catch(() => {
        // D-05: fail silently, do not update timestamp, no retry loop (D-04)
      })
  }, [])
}
