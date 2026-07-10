---
phase: 13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad
plan: 02
subsystem: ui
tags: [react, hooks, testing-library, vitest, localStorage]

# Dependency graph
requires:
  - phase: 13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad
    provides: "13-01's checkAdaptations() export in frontend/src/lib/api.ts"
provides:
  - "useAdaptationCheck hook: mount-once, 7-day-throttled, fire-and-forget ADAPT-04 trigger"
  - "AppLayout wiring that makes the previously-uncalled POST /adaptations/check endpoint reachable from every authenticated entry point"
affects: [13-03, 13-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "localStorage try/catch safety wrapper (mirrors sessionPersistence.ts) applied to a bare ISO-string throttle timestamp, not JSON"
    - "Fire-and-forget useEffect with success-only side effect (.then() writes state, .catch() is silent) to guarantee a failure never advances a throttle window"

key-files:
  created:
    - frontend/src/hooks/useAdaptationCheck.ts
    - frontend/src/tests/useAdaptationCheck.test.ts
  modified:
    - frontend/src/components/AppLayout.tsx
    - frontend/src/tests/AppLayout.test.tsx

key-decisions:
  - "D-05 (highest-risk): throttle timestamp is written only inside the checkAdaptations().then() success branch, never in .finally() or unconditionally, so a rejected call always retries on next mount"
  - "AppLayout (the mount-once layout route) is the sole integration point per D-01/D-02, not any single leaf screen, so Today/Agenda/Progress/Coach are all covered by one hook call"

patterns-established:
  - "Weekly/periodic client-triggered background check pattern: hook owns throttle state in localStorage as a raw string, layout-level component owns the single mount call, no UI surface"

requirements-completed: [ADAPT-04]

coverage:
  - id: D1
    description: "useAdaptationCheck fires checkAdaptations() once on mount when no throttle timestamp exists or the stored timestamp is >= 7 days old"
    requirement: ADAPT-04
    verification:
      - kind: unit
        ref: "frontend/src/tests/useAdaptationCheck.test.ts#calls checkAdaptations exactly once when no stored timestamp exists"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/useAdaptationCheck.test.ts#calls checkAdaptations when the last check was 8 days ago (window elapsed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "useAdaptationCheck does NOT call checkAdaptations() when the last check was < 7 days ago (throttle honored)"
    requirement: ADAPT-04
    verification:
      - kind: unit
        ref: "frontend/src/tests/useAdaptationCheck.test.ts#does not call checkAdaptations when the last check was < 7 days ago"
        status: pass
    human_judgment: false
  - id: D3
    description: "On success, the throttle timestamp is written as a fresh ISO string; on failure (rejection), the timestamp is left unadvanced so the next mount retries (D-05)"
    requirement: ADAPT-04
    verification:
      - kind: unit
        ref: "frontend/src/tests/useAdaptationCheck.test.ts#writes a fresh ISO timestamp to localStorage on successful check"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/useAdaptationCheck.test.ts#does not update the localStorage timestamp on checkAdaptations failure (D-05)"
        status: pass
    human_judgment: false
  - id: D4
    description: "AppLayout calls useAdaptationCheck() exactly once in its body (mount-once layout route, covers every authenticated entry point); existing height-chain regression test still passes; tsc --noEmit clean"
    requirement: ADAPT-04
    verification:
      - kind: unit
        ref: "frontend/src/tests/AppLayout.test.tsx#both wrapping containers use h-dvh and neither uses min-h-screen"
        status: pass
      - kind: other
        ref: "cd frontend && npx tsc --noEmit"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-10
status: complete
---

# Phase 13 Plan 02: Wire useAdaptationCheck into AppLayout Summary

**New `useAdaptationCheck` hook fires the previously-uncalled `POST /adaptations/check` (ADAPT-04) once per 7-day window from AppLayout, fire-and-forget, with D-05's failure-never-advances-the-throttle invariant proven by test.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-10T16:20:00Z
- **Completed:** 2026-07-10T16:32:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- ADAPT-04 now has a real caller: `useAdaptationCheck()` fires `checkAdaptations()` on an elapsed/absent 7-day window
- D-05 (highest-risk decision) is proven by test: a rejected check leaves the throttle timestamp unadvanced, so the next mount retries instead of being silently suppressed for a week
- Wired into `AppLayout`, the mount-once layout route, so every authenticated entry point (Today, Agenda, Progress, Coach) is covered by a single hook call
- Fire-and-forget: no loading UI, no toast, no retry loop (D-04)

## Task Commits

Each task was committed atomically:

1. **Task 1: TDD useAdaptationCheck hook (throttle + D-05 silent-failure)**
   - `c770641` (test) - add failing test for useAdaptationCheck
   - `5635881` (feat) - implement useAdaptationCheck hook
2. **Task 2: Call useAdaptationCheck() from AppLayout** - `b57e96a` (feat)

_No refactor commit needed — the GREEN implementation matched the verified 13-PATTERNS.md reference exactly, nothing to clean up._

## Files Created/Modified
- `frontend/src/hooks/useAdaptationCheck.ts` - mount-once, 7-day-throttled, fire-and-forget ADAPT-04 trigger; localStorage key `pacerai_adaptation_checked_at`
- `frontend/src/tests/useAdaptationCheck.test.ts` - 5 tests covering fresh-mount, throttle-skip, elapsed-window, success-write, and D-05 failure-no-write
- `frontend/src/components/AppLayout.tsx` - imports and calls `useAdaptationCheck()` as a bare statement before the JSX return
- `frontend/src/tests/AppLayout.test.tsx` - added `vi.mock('../lib/api', ...)` stub so the existing height-chain test's render doesn't hit the network via the newly-mounted hook

## Decisions Made
- Timestamp write placed strictly inside `.then()`, never `.finally()` — this is the D-05 correctness constraint from 13-RESEARCH.md Pitfall 3, verified by a dedicated failing-path test
- Followed 13-PATTERNS.md's verified implementation verbatim (no deviation) since it was already validated against the real `api.ts`/`sessionPersistence.ts` conventions

## Deviations from Plan

None - plan executed exactly as written. `frontend/node_modules` was not present in this fresh worktree checkout; ran `npm install` (reinstall from existing `package-lock.json`, no new/altered dependency) to restore the existing toolchain before running tests — this is environment setup, not a plan deviation, and is excluded from Rule 3's package-install restriction since no new package name was introduced.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `useAdaptationCheck` and its throttle key (`pacerai_adaptation_checked_at`) are available for any future plan needing to inspect/reset the check state
- Full frontend suite (161 tests, 21 files) passes with this change in place — no regressions
- Plan 13-03/13-04 (Adaptations UI in ProgressScreen, per 13-PATTERNS.md) are unaffected by this plan's scope

---
*Phase: 13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad*
*Completed: 2026-07-10*

## Self-Check: PASSED

All created/modified files verified present on disk; all 4 task/summary commit hashes (c770641, 5635881, b57e96a, 5945d3f) verified present in git log.
