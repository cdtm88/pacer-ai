---
phase: 13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad
fixed_at: 2026-07-10T16:49:04Z
review_path: .planning/phases/13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad/13-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 13: Code Review Fix Report

**Fixed at:** 2026-07-10T16:49:04Z
**Source review:** .planning/phases/13-close-gap-adapt-04-transp-03-wire-weekly-adaptation-check-ad/13-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (critical_warning scope: CR-01, WR-01, WR-02, WR-03; IN-01/IN-02 out of scope)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: No concurrency/in-flight guard in useAdaptationCheck — duplicate POST /adaptations/check calls can duplicate-apply an adaptation

**Files modified:** `frontend/src/hooks/useAdaptationCheck.ts`, `frontend/src/tests/useAdaptationCheck.test.ts`
**Commit:** `445b5ec`
**Applied fix:** Added a synchronous localStorage-based in-flight claim (`pacerai_adaptation_check_inflight`, 60s TTL) written before `checkAdaptations()` is invoked and cleared in a `.finally()`. A concurrent mount (AppLayout remount from navigation, React StrictMode double-invoke, or a second tab) now observes the claim and skips instead of firing a second concurrent `POST /adaptations/check`. Added a test asserting a second mount during an in-flight request does not increase the call count.

### WR-01: Successful adaptation check does not invalidate React Query caches

**Files modified:** `frontend/src/hooks/useAdaptationCheck.ts`, `frontend/src/tests/useAdaptationCheck.test.ts`, `frontend/src/tests/AppLayout.test.tsx`
**Commit:** `5c7cabc`
**Applied fix:** Added `useQueryClient()` to the hook and, on a successful check, invalidate `['adaptations']`, `['rides']`, `['pmc-history']`, `['pmc','latest']`, `['session','today']`, and `['sessions','upcoming']` — adapted from the review's suggested `['adaptations']`/`['sessions']` keys to the actual query keys used elsewhere in the codebase (e.g. `FitUploadZone.tsx`'s existing invalidation pattern), since a bare `['sessions']` key does not exist in this app. Updated both affected test files to wrap `renderHook`/`render` in a `QueryClientProvider` (now required since the hook calls `useQueryClient()`) and added a test asserting all six keys are invalidated on success.

### WR-02: `formatDuration` treats a zero-second ride as "no data"

**Files modified:** `frontend/src/components/history/RideRow.tsx`
**Commit:** `b6d249d`
**Applied fix:** Changed `if (!seconds) return '--'` to `if (seconds == null) return '--'` so a ride with `duration_secs: 0` renders `0m` instead of being conflated with missing duration data.

### WR-03: Compliance bar width is not lower-bound clamped

**Files modified:** `frontend/src/components/history/RideRow.tsx`
**Commit:** `1854d7f`
**Applied fix:** Changed `width: \`${Math.min(100, ride.compliance_pct)}%\`` to `width: \`${Math.max(0, Math.min(100, ride.compliance_pct))}%\`` so a negative `compliance_pct` cannot produce an invalid CSS width value that depends on non-guaranteed browser coercion.

## Skipped Issues

None — all in-scope findings were fixed.

## Verification

- `cd frontend && npx tsc --noEmit` — passed with no errors after each fix and after the full set of commits.
- `cd frontend && npx vitest run` — 22 test files, 166 tests, all passed after the full set of commits (includes 2 new test cases added for CR-01 and WR-01).
- IN-01 (throttle boundary test coverage gap) and IN-02 (duplicated error-parsing block in `api.ts`) were left unfixed per `fix_scope: critical_warning` — not in scope for this run.

---

_Fixed: 2026-07-10T16:49:04Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
