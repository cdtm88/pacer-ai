---
phase: 06-core-loop-persistence
plan: 03
subsystem: sports-science-pmc
tags: [pmc, ctl, atl, tsb, pytest, supabase, banister]

# Dependency graph
requires:
  - phase: 06-core-loop-persistence
    provides: pmc_history.tss and pmc_history.days_of_data columns (migration 0005, wave 1)
provides:
  - "backend/pmc_recompute.py::recompute_pmc_for_user - full daily PMC series rebuild through pure update_pmc"
  - "tests/test_pmc_recompute.py - gap_days, same_day_sum, days_of_data_calendar coverage"
affects: [06-05 (ride upload pipeline calls recompute_pmc_for_user inline)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Recompute-from-scratch day-series pattern for sparse/retroactive time-series metrics (RESEARCH Pattern 2)"

key-files:
  created:
    - backend/pmc_recompute.py
    - tests/test_pmc_recompute.py
  modified: []

key-decisions:
  - "recompute_pmc_for_user accepts an already-acquired async supabase client as a parameter rather than acquiring its own singleton, so callers control the client and tests can inject a mock"
  - "Read and write failures are logged with logger.error (not warning) but never raised, since the ride-upload caller must not fail the whole upload on a PMC failure"
  - "sports_science/pmc.py (pure update_pmc) is unchanged; this module only orchestrates DB reads/writes around it"

patterns-established:
  - "Pattern 2: PMC day-series recompute-from-scratch (rebuild the whole daily series keyed by ride_date, on every ride event, rather than patching one incremental EWMA step)"

requirements-completed: [FIT-04, TOOL-05]

coverage:
  - id: D1
    description: "recompute_pmc_for_user rebuilds one pmc_history row per calendar day from the user's first ride date to today"
    requirement: "FIT-04"
    verification:
      - kind: unit
        ref: "tests/test_pmc_recompute.py#test_days_of_data_calendar_counts_calendar_days_not_rides"
        status: pass
    human_judgment: false
  - id: D2
    description: "Gap days with no ride get a TSS=0 step so CTL/ATL decay on rest days"
    requirement: "TOOL-05"
    verification:
      - kind: unit
        ref: "tests/test_pmc_recompute.py#test_gap_days_produce_zero_tss_rows_and_ctl_decay"
        status: pass
    human_judgment: false
  - id: D3
    description: "Two rides on the same date have their TSS summed, not overwritten"
    requirement: "FIT-04"
    verification:
      - kind: unit
        ref: "tests/test_pmc_recompute.py#test_same_day_sum_combines_two_rides_into_one_row"
        status: pass
    human_judgment: false
  - id: D4
    description: "The recompute writes all rows in a single bulk upsert on_conflict user_id,date"
    requirement: "FIT-04"
    verification:
      - kind: unit
        ref: "tests/test_pmc_recompute.py#test_gap_days_produce_zero_tss_rows_and_ctl_decay (asserts upsert.call_count == 1)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Live end-to-end correctness of pmc_history writes via the real ride pipeline (not exercised by this plan's unit tests, which mock supabase)"
    verification: []
    human_judgment: true
    rationale: "This plan only builds and unit-tests the recompute module in isolation. Wiring it inline into the upload pipeline and exercising it against a real ride upload happens in plan 06-05; live pmc_history correctness cannot be judged from mocked tests alone."

# Metrics
duration: 12min
completed: 2026-07-03
status: complete
---

# Phase 6 Plan 3: PMC Day-Series Recompute Summary

**Recompute-from-scratch `backend/pmc_recompute.py::recompute_pmc_for_user` rebuilds the full daily CTL/ATL/TSB series through the unchanged pure `update_pmc`, replacing the broken one-EWMA-step-per-upload model.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-03T09:22Z
- **Completed:** 2026-07-03T09:34Z
- **Tasks:** 2 (executed as a single TDD RED/GREEN cycle)
- **Files modified:** 2

## Accomplishments
- New `backend/pmc_recompute.py` groups/sums rides by `ride_date`, walks every calendar day from the earliest ride to today through the pure `update_pmc`, and issues exactly one bulk `upsert(rows, on_conflict="user_id,date")` call
- Gap days with no ride get a `tss=0.0` step so CTL/ATL decay correctly on rest days
- Same-day rides are grouped and summed before the walk, so a second same-day upload no longer overwrites `tss`
- `days_of_data` increments once per calendar day walked, not once per ride/upload
- Every rides read is scoped by `.eq("user_id", user_id)` (T-06-03); read/write failures log via `logger.error` and never raise, so a PMC failure cannot fail the caller's ride upload
- `sports_science/pmc.py::update_pmc` is untouched (pure, locked invariant)

## Task Commits

Each task was committed atomically as a TDD RED/GREEN pair:

1. **Task 2 (RED): Create tests/test_pmc_recompute.py** - `fbc8d18` (test)
2. **Task 1 (GREEN): Create backend/pmc_recompute.py** - `2cda807` (feat)

_Tasks were executed test-first (TDD): the plan's Task 2 tests were written and confirmed failing (`ModuleNotFoundError`) before Task 1's implementation made them pass. No refactor commit was needed._

**Plan metadata:** committed separately as part of this SUMMARY.

## Files Created/Modified
- `backend/pmc_recompute.py` - `recompute_pmc_for_user(user_id, supabase)`: day-series PMC recompute orchestrator
- `tests/test_pmc_recompute.py` - three unit tests: `gap_days`, `same_day_sum`, `days_of_data_calendar`, asserting on the captured bulk-upsert payload

## Decisions Made
- Accept the async supabase client as a parameter instead of acquiring the singleton internally, matching the plan's explicit instruction so 06-05's caller controls the client and tests can inject a mock
- Mirrored the RESEARCH.md Pattern 2 reference implementation closely (same grouping/walk/upsert shape) since it was already reviewed and matches all `must_haves`
- Did not add a manual/admin recompute endpoint, per the plan's explicit orchestrator-decision note and RESEARCH Open Question 2 recommendation (scope discipline)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The worktree has no local `.venv`; ran tests via the main repo's `.venv/bin/pytest` (`/Users/christianmoore/ai/pacer-ai/.venv/bin/pytest`) since `.venv` is gitignored and not present per-worktree. Not a code change, just a local test-invocation note for future executors in this worktree.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `recompute_pmc_for_user` is ready to be imported and inline-awaited from `backend/routes/rides.py` in plan 06-05, replacing the existing single-step PMC block (rides.py lines ~286-381)
- No live/manual verification was performed against a real Supabase instance in this plan; that end-to-end check is deferred to 06-05 where the function is actually wired into the upload pipeline

---
*Phase: 06-core-loop-persistence*
*Completed: 2026-07-03*

## Self-Check: PASSED
- FOUND: backend/pmc_recompute.py
- FOUND: tests/test_pmc_recompute.py
- FOUND: .planning/phases/06-core-loop-persistence/06-03-SUMMARY.md
- FOUND commit: fbc8d18 (test)
- FOUND commit: 2cda807 (feat)
- FOUND commit: 0945362 (docs, this SUMMARY)
