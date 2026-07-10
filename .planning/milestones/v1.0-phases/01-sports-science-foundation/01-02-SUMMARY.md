---
phase: 01-sports-science-foundation
plan: 02
subsystem: sports-science
tags: [python, pydantic, zones, coggan, tdd]

requires:
  - 01-01 (ToolResult contract, constants.py, test scaffold)

provides:
  - calculate_power_zones(ftp) -> ToolResult (TOOL-01)
  - calculate_hr_zones(lthr) -> ToolResult (TOOL-02)
  - HR_ZONE_BOUNDARIES in constants.py (5-zone LTHR model)
  - 7 passing zone tests (boundary, ToolResult contract, parametrized overlap check)

affects:
  - 01-03, 01-04 (same ToolResult pattern applies)
  - Phase 2 agent tool registry (wraps calculate_power_zones and calculate_hr_zones)
  - Phase 4 UI (zone colour display consumes these boundaries)

tech-stack:
  added: []
  patterns:
    - "Exclusive upper bound zone membership (>= lower AND < upper); top zone >= lower only"
    - "HR_ZONE_BOUNDARIES in constants.py mirrors POWER_ZONE_BOUNDARIES structure"
    - "TDD RED/GREEN cycle: failing import test committed before implementation"

key-files:
  created:
    - sports_science/zones.py
  modified:
    - sports_science/constants.py (added HR_ZONE_BOUNDARIES)
    - tests/sports_science/test_zones.py (replaced stub with 4 real tests)

decisions:
  - "150W at 75% FTP (Z2 upper boundary) correctly maps to Z3: exclusive upper bound means 150 < 150 is false; plan comment was incorrect but must_have truth (exclusive upper) is the authority"
  - "HR zones use 5-zone Coggan/Allen LTHR model; boundaries stored in HR_ZONE_BOUNDARIES constant"
  - "HR multipliers defined as HR_ZONE_BOUNDARIES in constants.py (no inline magic numbers)"

metrics:
  duration: 2min
  completed: 2026-06-19
  tasks: 1 (TDD: RED commit + GREEN commit)
  files_modified: 3

status: complete
---

# Phase 1 Plan 02: Power and HR Training Zones Summary

**calculate_power_zones and calculate_hr_zones implemented test-first via TDD; Coggan/Allen 7-zone power model and 5-zone LTHR HR model; exclusive upper bounds prevent dual zone membership; both return ToolResult; TRUST-01 clean**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-19T13:24:09Z
- **Completed:** 2026-06-19T13:26:21Z
- **Tasks:** 1 (TDD task: RED + GREEN)
- **Files modified:** 3

## Accomplishments

- `sports_science/zones.py` created with `calculate_power_zones(ftp)` (TOOL-01) and `calculate_hr_zones(max_hr_or_lthr)` (TOOL-02)
- Both functions iterate over boundary tables from `constants.py` (no inline multipliers)
- Both return `ToolResult(value, unit, methodology, inputs)` with proper units (watts / bpm)
- `HR_ZONE_BOUNDARIES` added to `constants.py` for the 5-zone LTHR model
- Exclusive upper bound rule enforced: `>= lower AND < upper` for all zones except top zone (`>= lower` only)
- 7 tests passing: test_power_zones_ftp200, 4 parametrized boundary cases, test_hr_zones_lthr155, test_returns_tool_result
- TRUST-01 import boundary confirmed clean (no anthropic imports in sports_science/)

## TDD Gate Compliance

- RED commit: `966f803` - `test(01-02): add failing tests for power/HR zone functions (RED)`
- GREEN commit: `a272e17` - `feat(01-02): implement calculate_power_zones and calculate_hr_zones (GREEN)`

## Task Commits

1. **RED: Failing zone tests** - `966f803` (test)
2. **GREEN: zones.py implementation + constants + test fix** - `a272e17` (feat)

## Files Created/Modified

- `sports_science/zones.py` (new): `calculate_power_zones`, `calculate_hr_zones`
- `sports_science/constants.py` (modified): added `HR_ZONE_BOUNDARIES` (5-zone LTHR model)
- `tests/sports_science/test_zones.py` (modified): replaced 3 skip-stubbed tests with 4 real tests (7 total parametrized cases)

## Decisions Made

- Exclusive upper bound (`>= lower AND < upper`) is the canonical zone membership rule; top zone uses `>= lower` only. This matches the Coggan model intent and prevents dual membership at exact boundaries (Pitfall 4).
- At 75% FTP (150W with FTP=200), the value belongs to Z3 (not Z2): Z2 upper=150 is exclusive (150 < 150 is false); Z3 lower=150 is inclusive (150 >= 150 is true). The plan's behavior description contained a contradictory comment ("150W to Z2") but the must_have truth ("upper bound exclusive") is authoritative.
- HR zones use the 5-zone Coggan/Allen LTHR model: Z1 (<81%), Z2 (81-90%), Z3 (90-94%), Z4 (94-100%), Z5 (>=100%).
- HR_ZONE_BOUNDARIES defined in constants.py alongside POWER_ZONE_BOUNDARIES; no magic numbers inline.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed incorrect test parametrize expected value for 150W**
- **Found during:** GREEN phase - tests failed with 150W matching Z3 instead of expected Z2
- **Issue:** PATTERNS.md parametrize example showed `(200, 150, 2)` with comment "boundary: upper is exclusive", but with exclusive upper bound Z2 covers [110, 150), so 150W is in Z3 not Z2. The plan behavior description contradicted the must_have truth.
- **Fix:** Changed `(200, 150, 2)` to `(200, 150, 3)` in parametrize; added correct boundary analysis comment. The must_have truth ("upper bound exclusive") is the authority.
- **Files modified:** `tests/sports_science/test_zones.py`
- **Commit:** `a272e17`

## Known Stubs

None - all functions fully implemented and returning real data.

## Threat Flags

None - no new network endpoints, auth paths, file access, or schema changes introduced. TRUST-01 confirmed by test.

## Self-Check: PASSED

- `sports_science/zones.py` exists: FOUND
- `tests/sports_science/test_zones.py` exists with 7 passing tests: FOUND
- Commit 966f803 (RED): FOUND
- Commit a272e17 (GREEN): FOUND
- TRUST-01: zero anthropic imports in sports_science/: PASS

---
*Phase: 01-sports-science-foundation*
*Completed: 2026-06-19*
