---
phase: 13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad
reviewed: 2026-07-10T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - frontend/src/components/AppLayout.tsx
  - frontend/src/components/history/RideRow.tsx
  - frontend/src/hooks/useAdaptationCheck.ts
  - frontend/src/lib/api.ts
  - frontend/src/lib/format.ts
  - frontend/src/screens/ProgressScreen.tsx
  - frontend/src/tests/AppLayout.test.tsx
  - frontend/src/tests/format.test.ts
  - frontend/src/tests/progress.test.tsx
  - frontend/src/tests/useAdaptationCheck.test.ts
findings:
  critical: 1
  warning: 3
  info: 2
  total: 6
status: issues_found
---

# Phase 13: Code Review Report

**Reviewed:** 2026-07-10T00:00:00Z
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Reviewed the ADAPT-04/TRANSP-03 gap-closure changes: the mount-once weekly
adaptation-check hook, its wiring into `AppLayout`, the new Adaptations log
section on `ProgressScreen`, the shared `formatDate`/`triggerLabel` helpers,
and the associated tests. The throttle logic itself (7-day window, fail-only-
on-success timestamp advance per D-05) is implemented correctly and is well
covered by `useAdaptationCheck.test.ts`.

However, the hook has no guard against concurrent invocations, which — traced
against the backend's `detect_signals`/`apply_micro_adjustment`/
`apply_macro_replan` implementation in `backend/routes/adaptations.py` — can
produce duplicate plan mutations under normal (not just contrived) navigation
patterns, because the backend's "already consumed" check is a read-then-write
query with no atomicity or unique constraint backing it. This is the one
Critical finding below. The remaining findings are smaller correctness/
robustness gaps (a stale-cache issue that partially undercuts the TRANSP-03
transparency goal, an off-by-zero display bug, and a missing clamp).

## Critical Issues

### CR-01: No concurrency/in-flight guard in useAdaptationCheck — duplicate POST /adaptations/check calls can duplicate-apply an adaptation

**File:** `frontend/src/hooks/useAdaptationCheck.ts:39-53`
**Issue:**
The hook only writes the throttle timestamp *after* `checkAdaptations()`
resolves successfully (`setLastChecked` inside `.then()`, line 47). Between
the moment the effect fires the request and the moment it resolves,
`localStorage` still shows no recent timestamp (or a stale one), so any
second mount of the same effect during that window will read the same
"check needed" state and fire a second, fully independent
`POST /adaptations/check`.

This is not a purely theoretical race:
- `AppLayout` (where the hook is mounted) sits alongside `session` as a
  sibling route under `FirstRunGate` (`frontend/src/router.tsx:163-175`).
  Navigating `/` → `/session` → back to `/` unmounts and remounts
  `AppLayout`, re-running the effect. If the first check is still in flight
  (a macro replan touches multiple tables and is not instant), this ordinary
  navigation pattern fires two concurrent checks.
- React `StrictMode` is enabled in `frontend/src/main.tsx:12`, which
  double-invokes effects on mount in dev, hitting the exact same window.
- Two tabs of the same PWA opened at the same time will both read the same
  (expired/absent) `localStorage` timestamp and both fire, since there is no
  synchronous "claim" written before the async call starts.

Traced into the backend (`backend/routes/adaptations.py`), `detect_signals`
de-dupes only via a *read* of `trigger_session_ids` from previously
`applied`/`proposed` adaptations (`_get_consumed_session_ids`, lines 96-114)
performed *before* the new adaptation row is inserted by
`apply_micro_adjustment`/`apply_macro_replan`. There is no unique constraint
or transaction serializing this read-then-write. Two concurrent requests can
both read the same "not yet consumed" session ids, both decide the same
scope, and both apply an adjustment/replan for the same underlying signal —
i.e., the user's training plan gets adjusted or replanned twice for one
missed/underperformed session. This directly threatens plan integrity, which
is the project's core value proposition.

**Fix:** Add a synchronous in-flight guard before the async call, e.g.:
```ts
const INFLIGHT_KEY = 'pacerai_adaptation_check_inflight'
const INFLIGHT_TTL_MS = 60_000 // generous upper bound for one check to resolve

export function useAdaptationCheck(): void {
  useEffect(() => {
    const lastChecked = getLastChecked()
    const now = Date.now()
    if (lastChecked !== null && now - lastChecked < THROTTLE_MS) return

    // Claim synchronously (shared across tabs via localStorage) before the
    // async call starts, so a concurrent mount/tab sees the claim and skips.
    const inflightAt = Number(localStorage.getItem(INFLIGHT_KEY) ?? 0)
    if (now - inflightAt < INFLIGHT_TTL_MS) return
    localStorage.setItem(INFLIGHT_KEY, String(now))

    checkAdaptations()
      .then(() => setLastChecked(new Date().toISOString()))
      .catch(() => { /* D-05: fail silently, do not advance timestamp */ })
      .finally(() => localStorage.removeItem(INFLIGHT_KEY))
  }, [])
}
```
An equivalent server-side fix (add a unique constraint / advisory lock on
consumed session ids, or make the check-then-insert transactional) would
close the root cause more durably, but is out of scope for this file set —
flagging here since the frontend fix is the cheapest mitigation available in
these files.

## Warnings

### WR-01: Successful adaptation check does not invalidate React Query caches — new adaptations may not appear without a manual refetch trigger

**File:** `frontend/src/hooks/useAdaptationCheck.ts:39-53`, `frontend/src/screens/ProgressScreen.tsx:96-104`
**Issue:** When `checkAdaptations()` resolves and actually applies a
micro/macro adjustment, that mutates `adaptations`, `sessions`, and
potentially `rides`-derived compliance server-side. The hook never calls
`queryClient.invalidateQueries(...)` for `['adaptations']`, `['rides']`,
`['pmc-history']`, etc. If the user is already sitting on `ProgressScreen`
(or `TodayScreen`/`AgendaScreen`) when the background check resolves, the
Adaptations log and session views will keep showing stale data until a
`refetchOnWindowFocus`/remount trigger happens to fire. This is mitigated in
the common case by React Query's default `refetchOnWindowFocus: true` (no
override is configured on the shared `QueryClient` in `main.tsx`), but a user
who never blurs/refocuses the tab after the background check completes will
not see the new adaptation — undercutting the TRANSP-03 goal of transparently
surfacing why the plan changed.
**Fix:** In the hook's success branch, invalidate the affected query keys:
```ts
checkAdaptations()
  .then(() => {
    setLastChecked(new Date().toISOString())
    queryClient.invalidateQueries({ queryKey: ['adaptations'] })
    queryClient.invalidateQueries({ queryKey: ['sessions'] })
  })
```
(requires importing `useQueryClient` from `@tanstack/react-query` inside the
hook).

### WR-02: `formatDuration` treats a zero-second ride as "no data"

**File:** `frontend/src/components/history/RideRow.tsx:49-55`
**Issue:** `if (!seconds) return '--'` treats `0` the same as `null`/`undefined`.
A ride record with `duration_secs: 0` (e.g. a malformed/edge-case upload)
renders `'--'` instead of `'0m'`, silently conflating "no duration data" with
"zero-length ride."
**Fix:**
```ts
function formatDuration(seconds: number | null): string {
  if (seconds == null) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}
```

### WR-03: Compliance bar width is not lower-bound clamped

**File:** `frontend/src/components/history/RideRow.tsx:265`
**Issue:** `width: ${Math.min(100, ride.compliance_pct)}%` clamps the upper
bound but not the lower bound. If `compliance_pct` is ever negative (e.g. a
future signed-TSS-delta variant of the compliance calc, or bad upstream data),
this renders an invalid negative CSS width. Browsers generally coerce negative
`width` to `0`, but this depends on non-guaranteed CSS-engine behavior rather
than an explicit invariant in the code.
**Fix:** `width: \`${Math.max(0, Math.min(100, ride.compliance_pct))}%\``

## Info

### IN-01: No test for the exact 7-day throttle boundary

**File:** `frontend/src/tests/useAdaptationCheck.test.ts`
**Issue:** Tests cover "< 7 days" (skips) and "8 days ago" (fires), but not
the boundary itself (`now - lastChecked === THROTTLE_MS`, which the
implementation's strict `<` comparison treats as "check due"). Not a bug, but
a coverage gap on a boundary condition that's easy to get wrong on a future
refactor.
**Fix:** Add a case with `lastChecked` set to exactly `Date.now() - THROTTLE_MS`
and assert `checkAdaptations` is called.

### IN-02: Repeated structured-error-detail parsing block duplicated four times in api.ts

**File:** `frontend/src/lib/api.ts:255-264, 276-286, 296-306, 396-409`
**Issue:** `markSessionMissed`, `markSessionDone`, `getConversationMessages`,
and `uploadRide` each reimplement a near-identical
`try { const body = await res.json(); ... } catch { /* fallback */ }` block
to extract `{detail: {error, detail}}` / `{detail: string}` shapes. Not a
functional bug (each call site's `!res.ok` guard is correct), but the
duplication makes future error-shape changes error-prone (a future backend
change would need to be mirrored in four places).
**Fix:** Extract a shared helper, e.g.
`async function extractErrorDetail(res: Response, fallback: string): Promise<string>`,
and call it from each of the four sites.

---

_Reviewed: 2026-07-10T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
