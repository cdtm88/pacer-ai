---
phase: 01-sports-science-foundation
plan: 04
subsystem: sports-science
tags: [python, scipy, cp-model, ftp, load-progression, compliance, tdd, trust-model]

requires:
  - 01-01 (ToolResult contract, constants.py, test scaffold)
  - 01-03 (compute_tss pattern, ToolResult usage)

provides:
  - estimate_ftp_from_rides(rides) -> ToolResult (TOOL-03)
  - _is_quality_effort(effort, best_ftp_estimate) -> bool (private)
  - _cp_model(t, cp, wprime) -> ndarray (private)
  - progress_load(current_ctl, target_ctl, constraints) -> ToolResult (TOOL-06)
  - validate_session_vs_actual(planned, actual) -> ToolResult (TOOL-07)
  - CTL_RAMP_CEILING_PER_WEEK module constant in load.py
  - 25 passing tests: 9 in test_ftp.py, 6 in test_load.py, 10 in test_compliance.py

affects:
  - 01-05 (same ToolResult pattern; all three functions are downstream dependencies)
  - Phase 2 agent tool registry (wraps estimate_ftp_from_rides, progress_load, validate_session_vs_actual)
  - Phase 2 adaptive loop (compliance feeds re-planning decision)
  - Phase 3 FIT ingestion (feeds effort dicts to estimate_ftp_from_rides)

tech-stack:
  added:
    - scipy.optimize.curve_fit (2-param CP model fitting)
  patterns:
    - "FTP: 2-param CP model P(t)=CP+W'/t; quality filter: >3min and >85% of best estimate (or 150W fallback)"
    - "Sparse-data contract: value=None when <4 quality efforts; never fabricate physiological numbers (D-04)"
    - "Confidence: low=4-6 efforts, medium=7-11, high=12+"
    - "Load ramp: CTL ceiling 8pts/week; back-issues cap = load_ramp_flag_threshold_pct% of current_ctl"
    - "Compliance: actual/planned*100; None on zero planned (T-01-07); under_performed<70, over_performed>130"
    - "TDD RED/GREEN cycle: import-error RED committed before implementation"

key-files:
  created:
    - sports_science/ftp.py
    - sports_science/load.py
    - sports_science/compliance.py
  modified:
    - tests/sports_science/test_ftp.py (replaced 2 skip stubs with 9 real tests)
    - tests/sports_science/test_load.py (replaced 1 skip stub with 6 real tests)
    - tests/sports_science/test_compliance.py (replaced 1 skip stub with 10 real tests)
    - sports_science/__init__.py (added exports for all three new functions)

decisions:
  - "Confidence threshold at 12 maps to 'high' not 'medium': n<12 = medium, n>=12 = high (test-driven clarification of D-03 boundary)"
  - "FTP = CP in the 2-param model: CP is the asymptotic power (Critical Power) which approximates FTP"
  - "quality_effort threshold: fallback 150W used when no FTP estimate exists (prevents circular dependency)"
  - "back_issues=False -> back_constraints_applied=False returned explicitly (not just absent from dict)"
  - "__init__.py updated without capability_gap (Plan 05); import is added when that module ships"

metrics:
  duration: 2min
  completed: 2026-06-19
  tasks: 1 (TDD: RED commit + GREEN commit + chore commit)
  files_modified: 7

status: complete
---

# Phase 1 Plan 04: FTP Estimation, Load Progression, and Session Compliance Summary

**estimate_ftp_from_rides (CP model with 4-effort guard), progress_load (back-protective caps), and validate_session_vs_actual implemented test-first; all return ToolResult; sparse data returns None; zero-division guarded; import boundary clean; 25 tests passing**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-19T13:34:22Z
- **Completed:** 2026-06-19T13:36:30Z
- **Tasks:** 1 (TDD task: RED + GREEN + chore)
- **Files modified:** 7

## Accomplishments

- `sports_science/ftp.py` created with `_is_quality_effort`, `_cp_model`, and `estimate_ftp_from_rides` (TOOL-03)
- `sports_science/load.py` created with `CTL_RAMP_CEILING_PER_WEEK` and `progress_load` (TOOL-06)
- `sports_science/compliance.py` created with `validate_session_vs_actual` (TOOL-07)
- CP model: `scipy.optimize.curve_fit` on P(t) = CP + W'/t; bounds=[50..500W, 1000..100000J]; maxfev=5000
- Sparse-data contract enforced: `estimate_ftp_from_rides` returns `value=None` with `confidence='insufficient_data'` for <4 quality efforts; never fabricates a number (D-04, T-01-05)
- Quality-effort filter: duration >= 180s AND mean_power >= 150W fallback (or 85% of best estimate)
- Confidence levels: low (4-6), medium (7-11), high (12+)
- `progress_load` applies back-protective cap: `min(8.0, current_ctl * ramp_threshold_pct/100)` when `back_issues=True` (D-09)
- `validate_session_vs_actual` guards zero planned_tss with explicit None return (T-01-07)
- `sports_science/__init__.py` updated to export all three new public functions
- 25 new tests passing; full suite 59 passed (2 skipped for Plan 05); TRUST-01 import boundary clean

## TDD Gate Compliance

- RED commit: `25d9d2b` - `test(01-04): add failing tests for estimate_ftp_from_rides, progress_load, validate_session_vs_actual (RED)`
- GREEN commit: `c06c023` - `feat(01-04): implement estimate_ftp_from_rides, progress_load, validate_session_vs_actual (GREEN)`

## Task Commits

1. **RED: Failing FTP, load, compliance tests** - `25d9d2b` (test)
2. **GREEN: ftp.py, load.py, compliance.py implementation** - `c06c023` (feat)
3. **chore: update __init__.py exports** - `40f14a8` (chore)

## Files Created/Modified

- `sports_science/ftp.py` (new): `_is_quality_effort`, `_cp_model`, `estimate_ftp_from_rides` (TOOL-03)
- `sports_science/load.py` (new): `CTL_RAMP_CEILING_PER_WEEK`, `progress_load` (TOOL-06)
- `sports_science/compliance.py` (new): `validate_session_vs_actual` (TOOL-07)
- `tests/sports_science/test_ftp.py` (modified): 9 real tests replacing 2 skip stubs
- `tests/sports_science/test_load.py` (modified): 6 real tests replacing 1 skip stub
- `tests/sports_science/test_compliance.py` (modified): 10 real tests replacing 1 skip stub
- `sports_science/__init__.py` (modified): added 3 new public function exports

## Decisions Made

- Confidence boundary at 12 is `high` (n >= 12 = high, n < 12 = medium): test drove clarification of D-03 which said "7-12 medium, 12+ high" -- the boundary value 12 belongs to "high".
- FTP = CP directly: in the 2-parameter model, CP is the asymptotic power that approximates FTP for longer durations.
- Quality-effort fallback: 150W threshold used when no FTP estimate exists, preventing a circular dependency where the filter depends on the output it's computing.
- back_constraints_applied is explicitly set to `bool(constraints.get("back_issues", False))` to ensure the return value is always a boolean (not the raw JSONB value).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Confidence threshold boundary at 12**
- **Found during:** GREEN implementation + test run
- **Issue:** Plan spec says "medium: 7-12, high: 12+" which is ambiguous at n=12. Test `test_confidence_levels` with 12 efforts expects "high".
- **Fix:** Changed threshold from `n <= 12` to `n < 12` for medium, so n=12 maps to "high".
- **Files modified:** `sports_science/ftp.py`
- **Commit:** `c06c023` (part of GREEN commit)

## Known Stubs

None - all functions fully implemented and returning real data.

## Threat Flags

None - no new network endpoints, auth paths, or file access patterns introduced. TRUST-01 confirmed by import boundary test (no anthropic imports in sports_science/).

## Self-Check: PASSED

- `sports_science/ftp.py` exists: FOUND
- `sports_science/load.py` exists: FOUND
- `sports_science/compliance.py` exists: FOUND
- `tests/sports_science/test_ftp.py` with 9 tests: FOUND
- `tests/sports_science/test_load.py` with 6 tests: FOUND
- `tests/sports_science/test_compliance.py` with 10 tests: FOUND
- Commit 25d9d2b (RED): FOUND
- Commit c06c023 (GREEN): FOUND
- Full test suite: 59 passed, 2 skipped (Plan 05 stubs)
- TRUST-01: zero anthropic imports: PASS

---
*Phase: 01-sports-science-foundation*
*Completed: 2026-06-19*
