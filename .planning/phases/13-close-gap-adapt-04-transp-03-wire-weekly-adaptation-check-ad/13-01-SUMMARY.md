---
phase: 13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad
plan: 01
subsystem: api
tags: [typescript, vitest, react, contract-fix]

requires: []
provides:
  - "Corrected Adaptation interface in frontend/src/lib/api.ts matching the real adaptations table (trigger, signal_count?, scope, explanation_text, status?, trigger_session_ids?, created_at)"
  - "checkAdaptations() POST /api/adaptations/check wrapper in api.ts (ADAPT-04 caller half)"
  - "triggerLabel + formatDate exported from frontend/src/lib/format.ts"
  - "RideRow.tsx consumes the shared formatDate (local duplicate removed)"
affects: [13-02, 13-03, 13-04]

tech-stack:
  added: []
  patterns:
    - "Record<string,string> lookup + titleCase fallback (triggerLabel mirrors sessionTypeLabel)"
    - "Shared date formatter in lib/format.ts consumed by multiple screens/components"

key-files:
  created:
    - frontend/src/tests/format.test.ts
  modified:
    - frontend/src/lib/format.ts
    - frontend/src/lib/api.ts
    - frontend/src/components/history/RideRow.tsx

key-decisions:
  - "formatDate adds an explicit isNaN(date.getTime()) guard so an unparseable date returns the raw input string, not the literal 'Invalid Date' -- the RideRow original try/catch alone never threw on an Invalid Date object, so it could not satisfy the plan's own behavior spec without this addition (Rule 1 bug fix)"
  - "checkAdaptations() returns Promise<unknown> per plan discretion -- the fire-and-forget caller in 13-02 ignores the response body"

requirements-completed: [ADAPT-04, TRANSP-03]

coverage:
  - id: D1
    description: "triggerLabel humanizes DB trigger values (missed/underperformance/overreaching) with titleCase fallback for unknown values and 'Adaptation' default for null/undefined"
    requirement: "TRANSP-03"
    verification:
      - kind: unit
        ref: "frontend/src/tests/format.test.ts#lib/format — triggerLabel"
        status: pass
    human_judgment: false
  - id: D2
    description: "formatDate returns a locale-formatted short weekday/month/day string, and returns the raw input on an unparseable date instead of throwing or returning 'Invalid Date'"
    requirement: "TRANSP-03"
    verification:
      - kind: unit
        ref: "frontend/src/tests/format.test.ts#lib/format — formatDate"
        status: pass
    human_judgment: false
  - id: D3
    description: "RideRow renders identical date output after switching to the shared formatDate export (no visual regression)"
    requirement: "TRANSP-03"
    verification:
      - kind: unit
        ref: "frontend/src/tests/history.test.tsx"
        status: pass
    human_judgment: false
  - id: D4
    description: "Adaptation interface corrected to match the real adaptations table columns; checkAdaptations() POSTs to /api/adaptations/check via apiFetch and throws on a non-ok response"
    requirement: "ADAPT-04"
    verification:
      - kind: unit
        ref: "cd frontend && npx tsc --noEmit"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-07-10
status: complete
---

# Phase 13 Plan 01: Format Helpers + Adaptation Contract Fix Summary

**Fixed the stale `Adaptation` TypeScript interface to match the real `adaptations` table schema, added `checkAdaptations()` POST wrapper, and extracted `triggerLabel`/`formatDate` display helpers into `lib/format.ts` for the upcoming Adaptations log UI.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-10T20:23:00Z
- **Completed:** 2026-07-10T20:29:00Z
- **Tasks:** 2
- **Files modified:** 4 (1 new test file, 3 modified)

## Accomplishments
- `triggerLabel()` and `formatDate()` added to `frontend/src/lib/format.ts`, following the existing `sessionTypeLabel` Record-lookup + titleCase-fallback pattern
- `RideRow.tsx` re-pointed to the shared `formatDate` import; its private duplicate deleted
- `Adaptation` interface in `api.ts` corrected from a stale, non-existent-field shape (`session_id`, `adaptation_type`, `description`) to the real schema (`trigger`, `signal_count?`, `scope`, `explanation_text`, `status?`, `trigger_session_ids?`, `created_at`) — this was the Contract Mismatch blocking 13-03's Adaptations UI from rendering real data
- `checkAdaptations()` POST wrapper added to `api.ts`, the caller half of ADAPT-04 that 13-02's `useAdaptationCheck` hook will consume

## Task Commits

Each task was committed atomically (TDD RED/GREEN for Task 1):

1. **Task 1 RED: format.test.ts** - `b55cc62` (test)
2. **Task 1 GREEN: triggerLabel + formatDate + RideRow re-point** - `bdf1eb4` (feat)
3. **Task 2: corrected Adaptation interface + checkAdaptations()** - `27030ab` (fix)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `frontend/src/tests/format.test.ts` - new unit tests for triggerLabel + formatDate (7 cases)
- `frontend/src/lib/format.ts` - added TRIGGER_LABELS map + triggerLabel(), added formatDate() with invalid-date guard
- `frontend/src/lib/api.ts` - corrected Adaptation interface, added checkAdaptations()
- `frontend/src/components/history/RideRow.tsx` - imports shared formatDate, deleted local duplicate

## Decisions Made
- Added an explicit `isNaN(date.getTime())` check inside `formatDate` before calling `toLocaleDateString`. The plan's `<action>` said to move the RideRow formatDate "verbatim", but its own `<behavior>` spec requires `formatDate('not-a-date')` to return the raw input string. `toLocaleDateString` never throws on an `Invalid Date` object — it silently returns the literal string `"Invalid Date"` — so a verbatim try/catch-only copy could not satisfy the stated behavior. This is a Rule 1 (auto-fix bug) deviation: verified via `zwift-ride` style unit test (`format.test.ts`'s "returns the raw input on an unparseable date" case).
- Relaxed the weekday assertion in `format.test.ts` from an exact `'Mon, Jul 6'` comma-separated shape to a locale-agnostic substring match, since the sandbox's system locale renders `toLocaleDateString(undefined, ...)` as `"Mon 6 Jul"` (no comma, day-before-month order) rather than the US-style example in the plan. The underlying contract (weekday short + month short + numeric day, byte-identical between RideRow and the new Adaptations UI) is unaffected since both consumers call the same function with the same options object.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] formatDate needed an explicit invalid-date guard to satisfy its own behavior spec**
- **Found during:** Task 1 (GREEN phase, writing formatDate)
- **Issue:** Plan's `<action>` instructed moving RideRow's `formatDate` verbatim (try/catch only), but its `<behavior>` bullet requires `formatDate('not-a-date')` to return the raw input. `new Date('not-a-date').toLocaleDateString(...)` does not throw — it returns `"Invalid Date"` — so the verbatim implementation would have failed its own acceptance test.
- **Fix:** Added `if (isNaN(date.getTime())) return isoDate` before the `toLocaleDateString` call, inside the existing try/catch.
- **Files modified:** `frontend/src/lib/format.ts`
- **Verification:** `format.test.ts`'s "returns the raw input on an unparseable date, without throwing" case passes.
- **Committed in:** `bdf1eb4` (Task 1 GREEN commit)

---

**Total deviations:** 1 auto-fixed (1 Rule 1 bug fix)
**Impact on plan:** Necessary for correctness — the plan's own acceptance criteria required this behavior. No scope creep; RideRow's rendered output for all valid dates (its only real input) is unchanged.

## Issues Encountered
- The worktree had no `node_modules` installed (git worktrees don't carry install state). Symlinked `frontend/node_modules` to the main checkout's `frontend/node_modules` (same commit, same lockfile) to run `vitest`/`tsc` for verification. The symlink is gitignored and was not committed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `frontend/src/lib/api.ts`'s corrected `Adaptation` interface and `checkAdaptations()` are ready for 13-02 (`useAdaptationCheck` hook) and 13-03 (Adaptations UI in ProgressScreen) to import
- `triggerLabel` + `formatDate` are ready for 13-03 to consume directly
- No blockers for downstream plans in this phase

---
*Phase: 13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad*
*Completed: 2026-07-10*
