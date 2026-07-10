---
phase: 10-hygiene-safety-nets
plan: 02
subsystem: testing
tags: [playwright, e2e, fixtures, contract-testing, rides]

requires:
  - phase: 09-frontend-resilience
    provides: "Field-name fix for GET /rides/ response shape landed in backend/routes/rides.py and frontend/src/lib/api.ts (duration_secs, avg_power)"
provides:
  - "Playwright e2e ride fixtures (fixtureRides) that faithfully mirror the real GET /rides/ response shape, including the top-level {rides: [...]} envelope"
affects: [e2e-testing, ride-history, playwright]

tech-stack:
  added: []
  patterns:
    - "e2e route mocks must wrap list-endpoint fixtures in the exact JSON envelope the real endpoint returns (e.g. {rides: [...]}), not just match inner field names"

key-files:
  created: []
  modified:
    - frontend/tests/e2e/full-uat.spec.ts
    - frontend/tests/e2e/phase4.spec.ts

key-decisions:
  - "Renamed duration_seconds -> duration_secs and avg_power_watts -> avg_power in both spec files' fixtureRides, matching frontend/src/lib/api.ts's Ride interface and backend/routes/rides.py's .select() column list"
  - "Removed phantom fields file_name and distance_m from fixtureRides — never part of the real Ride shape"
  - "Added intensity_factor, avg_hr, avg_cadence, ftp_used to fixtureRides so the fixture is a full mirror of the real response, even though the UI does not read them today"

requirements-completed: [ITEM-03]

coverage:
  - id: D1
    description: "fixtureRides in full-uat.spec.ts and phase4.spec.ts use the real backend field names (duration_secs, avg_power) and drop phantom fields (file_name, distance_m)"
    requirement: "ITEM-03"
    verification:
      - kind: other
        ref: "grep -rc 'duration_seconds|avg_power_watts|file_name|distance_m' frontend/tests/e2e/full-uat.spec.ts frontend/tests/e2e/phase4.spec.ts -> 0 for both files"
        status: pass
      - kind: other
        ref: "grep -rc 'duration_secs|avg_power' frontend/tests/e2e/full-uat.spec.ts frontend/tests/e2e/phase4.spec.ts -> non-zero for both files"
        status: pass
    human_judgment: false
  - id: D2
    description: "Playwright suite specs parse with no TypeScript/syntax error introduced"
    verification:
      - kind: other
        ref: "cd frontend && npx playwright test --list -> 102 tests listed across 2 files"
        status: pass
    human_judgment: false
  - id: D3
    description: "Ride-history specs (History Screen suites in both files) pass against the corrected fixtures"
    requirement: "ITEM-03"
    verification:
      - kind: e2e
        ref: "npx playwright test --grep 'History Screen' -> 10 passed, 0 failed"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-08
status: complete
---

# Phase 10 Plan 02: Align E2E Ride Fixtures Summary

**Corrected `fixtureRides` in both Playwright specs to mirror the real `GET /rides/` contract (duration_secs/avg_power, no file_name/distance_m), and fixed a pre-existing response-envelope bug in the same route mock that was silently making every ride-history assertion run against an empty list.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-08T14:38:00Z (approx)
- **Completed:** 2026-07-08T15:03:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Renamed `duration_seconds` -> `duration_secs` and `avg_power_watts` -> `avg_power` in `fixtureRides` in both `full-uat.spec.ts` and `phase4.spec.ts`.
- Removed phantom fields `file_name` and `distance_m` that never existed in the real `Ride` shape.
- Added `intensity_factor`, `avg_hr`, `avg_cadence`, `ftp_used` to each fixture ride so the mock is a full mirror of the real backend response.
- Discovered and fixed a second, pre-existing contract bug in the same `/rides/` route mock: it returned a bare array instead of the real endpoint's `{"rides": [...]}` envelope, which silently caused every ride-history UI assertion (compliance chips, ride rows) to run against an effectively empty list. Wrapped the mock response in `{ rides: ... }` in both spec files.
- Verified via a live Playwright run: all 10 History Screen specs across both files now pass (previously 5 failed on the stale envelope bug alone).

## Task Commits

Each task was committed atomically:

1. **Task 1: Align fixtureRides in both e2e specs with the real Ride shape** - `32e8088` (fix)

**Plan metadata:** (this SUMMARY commit)

## Files Created/Modified
- `frontend/tests/e2e/full-uat.spec.ts` - `fixtureRides` field names corrected; `/rides/` route mock wrapped in `{rides: [...]}`
- `frontend/tests/e2e/phase4.spec.ts` - Same corrections

## Decisions Made
- Field renames and phantom-field removal followed the plan's `<action>` exactly.
- Added the optional extra fields (`intensity_factor`, `avg_hr`, `avg_cadence`, `ftp_used`) per the plan's "optionally ADD" guidance, using realistic values so the fixture stays a faithful full mirror of `GET /rides/`.
- Fixed the `/rides/` route mock's response envelope (bare array -> `{rides: [...]}`) even though it wasn't explicitly named in the plan's `<action>` — see Deviations below.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed `/rides/` route mock response envelope in both spec files**
- **Found during:** Task 1 (running the plan's own human-check verification: `npx playwright test`)
- **Issue:** The real `GET /rides/` endpoint returns `{"rides": [...]}` (confirmed in `backend/routes/rides.py`'s `list_rides`), and `frontend/src/lib/api.ts`'s `getRides()` reads `data.rides ?? []`. Both spec files' `/rides/` route mock returned `overrides.rides ?? fixtureRides` directly — a bare array, not wrapped in a `rides` key. This meant `getRides()` always saw `data.rides === undefined` and fell back to an empty list, so every ride-row/compliance-chip assertion in the History Screen suites was passing (or in this case, newly failing after the field-name fix surfaced it) against effectively no data. This is a pre-existing bug unrelated to the field-name work but directly blocks this plan's own must-have: "The e2e suite passes against fixtures that faithfully mirror the real GET /rides/ response shape" — the response *shape* includes the envelope, not just inner field names.
- **Fix:** Changed `route.fulfill(respond(overrides.rides ?? fixtureRides))` to `route.fulfill(respond({ rides: overrides.rides ?? fixtureRides }))` in both `full-uat.spec.ts` and `phase4.spec.ts`. No call site needed changes since `overrides.rides` is always passed as a plain array throughout both files.
- **Files modified:** frontend/tests/e2e/full-uat.spec.ts, frontend/tests/e2e/phase4.spec.ts
- **Verification:** Before the fix, `npx playwright test --grep "History Screen"` had 5 failures (missing `95% on target` compliance text etc.). After the fix, all 10 History Screen tests across both files passed.
- **Committed in:** 32e8088 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Necessary to satisfy the plan's own must-have that the e2e suite passes against a faithful mirror of the real response shape. No scope creep — no other spec files touched, no backend/frontend/src files touched.

## Issues Encountered
A full `npx playwright test` run (all 102 tests, both files) surfaced 27 pre-existing failures unrelated to ride fixtures or the `/rides/` endpoint (Login Screen, Today Screen zone accent bar, Agenda accordion, Settings connected state, During-Session timer/End-session button, Export-to-Zwift tooltip, Console Health). None of these reference History Screen, rides, or ride fixtures — confirmed by full-text scan of the failure list. These are out of scope for this plan per the deviation-rules scope boundary (not caused by this task's changes) and are logged here rather than fixed. They were present in the repository state prior to this plan's edits; `node_modules` were freshly installed via `npm ci` in this worktree solely to run the verification (Playwright browsers/deps were already cached at `~/Library/Caches/ms-playwright`).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Ride fixture contract alignment (ITEM-03) is complete for this plan's scope.
- The 27 unrelated pre-existing e2e failures noted above remain for a future hygiene pass or triage; they are not blockers for this phase's other plans (D-05: Playwright is out of CI this phase, run pre-merge manually).

---
*Phase: 10-hygiene-safety-nets*
*Completed: 2026-07-08*

## Self-Check: PASSED

- `frontend/tests/e2e/full-uat.spec.ts` exists: FOUND
- `frontend/tests/e2e/phase4.spec.ts` exists: FOUND
- Commit `32e8088` exists in git log: FOUND (`git log --oneline --all | grep 32e8088`)
- Acceptance criteria re-verified: stale-token grep returns 0/0, real-name grep returns 4/2, `playwright test --list` succeeds (102 tests), no `backend/` or `frontend/src/` files modified.
