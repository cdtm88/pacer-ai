---
phase: 11-ride-analysis-dashboard
plan: 02
subsystem: sports-science
tags: [python, pytest, tdd, hr-zones, tool-result]

# Dependency graph
requires:
  - phase: 11-ride-analysis-dashboard
    provides: calculate_hr_zones (existing TOOL-02) and the ToolResult contract this plan reuses
provides:
  - "time_in_hr_zones(hr_array, lthr) sports-science tool returning per-zone seconds/pct as a methodology-tagged ToolResult"
affects: [11-03-ride-detail-route, ride-analysis-dashboard-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Time-in-zone tools reuse the corresponding boundary function's .value rather than re-deriving ratios (D-11-02)"

key-files:
  created: []
  modified:
    - backend/sports_science/zones.py
    - tests/sports_science/test_zones.py

key-decisions:
  - "time_in_hr_zones sources boundaries exclusively from calculate_hr_zones(lthr).value -- no independent zone ratio math -- so there is exactly one definition of an HR zone in the codebase (D-11-02, TRUST-01)."
  - "Zone classification breaks on first match per sample using >= lower AND < upper (top zone >= lower only), mirroring calculate_hr_zones' own membership convention exactly."

patterns-established:
  - "Pattern: time-in-X-zone tools call the paired zone-boundary tool and iterate its .value; never hardcode boundary ratios a second time."

requirements-completed: [RIDE-04, RIDE-12]

coverage:
  - id: D1
    description: "time_in_hr_zones returns a ToolResult of 5 per-zone rows (seconds, pct) sourced from calculate_hr_zones boundaries, verified against a hand-checked 20-sample HR array"
    requirement: RIDE-04
    verification:
      - kind: unit
        ref: "tests/sports_science/test_zones.py#test_time_in_hr_zones_hand_checked"
        status: pass
      - kind: unit
        ref: "tests/sports_science/test_zones.py#test_time_in_hr_zones_boundary_exclusive_upper"
        status: pass
      - kind: unit
        ref: "tests/sports_science/test_zones.py#test_time_in_hr_zones_toolresult_contract"
        status: pass
      - kind: unit
        ref: "tests/sports_science/test_zones.py#test_time_in_hr_zones_empty_array"
        status: pass
    human_judgment: false
  - id: D2
    description: "time_in_hr_zones never re-derives HR zone boundaries independently of calculate_hr_zones (TRUST-01, single source of truth)"
    requirement: RIDE-12
    verification:
      - kind: unit
        ref: "tests/sports_science/test_zones.py#test_time_in_hr_zones_boundaries_match_calculate_hr_zones"
        status: pass
      - kind: unit
        ref: "tests/sports_science/test_import_boundary.py"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-07-09
status: complete
---

# Phase 11 Plan 02: time_in_hr_zones Summary

**Added `time_in_hr_zones(hr_array, lthr)` sports-science tool that computes per-zone seconds/pct entirely from `calculate_hr_zones` boundaries, test-driven with a hand-checked 20-sample HR array.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-09T16:30:00Z (approx)
- **Completed:** 2026-07-09T16:42:46Z
- **Tasks:** 2 (RED, GREEN)
- **Files modified:** 2

## Accomplishments
- `time_in_hr_zones` in `backend/sports_science/zones.py` returns a `ToolResult` with 5 per-zone rows (`zone`, `name`, `seconds`, `pct`), `unit="seconds"`, methodology mentioning "time-in-zone", and `inputs={"lthr", "total_seconds"}`.
- Boundaries are sourced exclusively from `calculate_hr_zones(lthr).value` — zero duplicated zone-ratio math (D-11-02, TRUST-01).
- Exclusive-upper membership convention (`>= lower AND < upper`, top zone `>= lower` only) verified with a dedicated boundary test using values exactly on each zone edge.
- Empty-array input returns all-zero rows without a `ZeroDivisionError`.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing hand-checked tests for time_in_hr_zones** - `b90d925` (test)
2. **Task 2 (GREEN): Implement time_in_hr_zones reusing calculate_hr_zones** - `9cd2142` (feat)

**Plan metadata:** (final metadata commit follows this SUMMARY)

_Note: no REFACTOR commit was needed — the GREEN implementation matched the target shape on first pass._

## Files Created/Modified
- `backend/sports_science/zones.py` - Added `time_in_hr_zones(hr_array, lthr) -> ToolResult`
- `tests/sports_science/test_zones.py` - Added import + 5 new test functions covering hand-checked values, boundary exclusivity, ToolResult contract, empty array, and a boundary sanity-check against `calculate_hr_zones(160)`

## Decisions Made
- Chose a 20-sample hand-checked array (4 samples per zone, one on each zone's exact lower boundary) so every zone lands on an exact 20.0% with no rounding-tie ambiguity, keeping the "hand-checked" assertions unambiguous.
- Added an extra sanity-check test (`test_time_in_hr_zones_boundaries_match_calculate_hr_zones`) that independently confirms the hand-computed lthr=160 boundaries used throughout the test file actually match `calculate_hr_zones(160).value`, guarding against boundary drift if `HR_ZONE_BOUNDARIES` ratios ever change.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. `python` was not on PATH in the worktree shell; used the project's `.venv/bin/python -m pytest` (same interpreter the project's own tooling resolves to) for all verification runs.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `time_in_hr_zones` is ready for 11-03's ride-detail route to call and surface in the API response; no zone maths needs to exist in TypeScript.
- `sports_science` import boundary (no Anthropic/DB imports) remains intact, confirmed by `test_import_boundary.py`.

---
*Phase: 11-ride-analysis-dashboard*
*Completed: 2026-07-09*
