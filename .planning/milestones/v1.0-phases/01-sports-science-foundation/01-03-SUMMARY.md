---
phase: 01-sports-science-foundation
plan: 03
subsystem: sports-science
tags: [python, numpy, tss, pmc, tdd, banister, normalized-power]

requires:
  - 01-01 (ToolResult contract, constants.py, test scaffold)

provides:
  - compute_tss(power_array, duration_secs, ftp) -> ToolResult (TOOL-04)
  - _compute_np(power_array, ftp) -> float | None (private NP helper)
  - update_pmc(prev_ctl, prev_atl, tss, days_of_data) -> ToolResult (TOOL-05)
  - CTL_ALPHA, ATL_ALPHA module-level constants in pmc.py
  - 21 passing tests: 12 in test_metrics.py, 9 in test_pmc.py

affects:
  - 01-04, 01-05 (same ToolResult pattern; metrics/pmc are downstream dependencies)
  - Phase 2 agent tool registry (wraps compute_tss, update_pmc)
  - Phase 3 FIT ingestion (calls compute_tss after parsing power stream)
  - Phase 4 UI (PMC chart consumes CTL/ATL/TSB; tss_display_ready gates chip)

tech-stack:
  added: []
  patterns:
    - "NP: zeros kept in array; spike-clip (ftp*3) before 30s rolling mean; 4th-power EWMA"
    - "TSS: NP/ftp=IF; (duration * NP * IF) / (ftp * 3600) * 100; None for <10 min rides"
    - "PMC: module-level CTL_ALPHA/ATL_ALPHA from 1-exp(-1/TC); TSB = prev_ctl - prev_atl"
    - "Cold-start guard: tss_display_ready False until days_of_data >= 28"
    - "TDD RED/GREEN cycle: failing import test committed before implementation"

key-files:
  created:
    - sports_science/metrics.py
    - sports_science/pmc.py
  modified:
    - tests/sports_science/test_metrics.py (replaced 4 skip stubs with 12 real tests)
    - tests/sports_science/test_pmc.py (replaced 2 skip stubs with 9 real tests)

decisions:
  - "NP zeros are not filtered: coasting segments contribute to rolling windows (Pitfall 1 avoided)"
  - "Spike clip at FTP*NP_SPIKE_MULTIPLIER (3.0) runs BEFORE np.convolve, not after"
  - "All-zero power array returns TSS=0.0 via early exit after np_watts==0 guard (avoids division)"
  - "TSB = prev_ctl - prev_atl (yesterday's values); new_ctl/atl use today's TSS in EWMA step"
  - "CTL_ALPHA and ATL_ALPHA are module-level floats derived at import time from constants.py"

metrics:
  duration: 2min
  completed: 2026-06-19
  tasks: 1 (TDD: RED commit + GREEN commit)
  files_modified: 4

status: complete
---

# Phase 1 Plan 03: TSS/NP/IF Metrics and Banister PMC Summary

**compute_tss and update_pmc implemented test-first using numpy; NP includes zeros and clips spikes; short rides return None; cold-start guard gates tss_display_ready at 28 days; both return ToolResult; 21 tests passing; TRUST-01 import boundary clean**

## Performance

- **Duration:** 2 min
- **Started:** 2026-06-19T13:29:39Z
- **Completed:** 2026-06-19T13:31:56Z
- **Tasks:** 1 (TDD task: RED + GREEN)
- **Files modified:** 4

## Accomplishments

- `sports_science/metrics.py` created with `_compute_np` (private NP helper) and `compute_tss` (TOOL-04)
- `sports_science/pmc.py` created with module-level `CTL_ALPHA`/`ATL_ALPHA` and `update_pmc` (TOOL-05)
- NP algorithm: spike clip (ftp*3.0) -> 30-sample rolling mean via np.convolve -> 4th-power mean -> 4th root
- Zeros are kept in power array: coasting segments weight the 30-second rolling windows down, making NP < peak power
- Short-ride guard: `duration_secs < NP_MIN_DURATION_SECS (600)` returns `ToolResult(value=None)`
- All-zero guard: `np_watts == 0.0` returns `ToolResult(value={"tss": 0.0, ...})` without division error
- `update_pmc` implements one-step Banister EWMA: `new_ctl = prev + alpha * (tss - prev)`
- TSB = `prev_ctl - prev_atl` (yesterday's CTL minus ATL = today's form)
- Cold-start guard: `tss_display_ready = days_of_data >= PMC_MIN_DAYS (28)`
- 21 tests passing; TRUST-01 import boundary test passing (no anthropic imports)

## TDD Gate Compliance

- RED commit: `5db0e03` - `test(01-03): add failing tests for compute_tss and update_pmc (RED)`
- GREEN commit: `2a8271a` - `feat(01-03): implement compute_tss and update_pmc (GREEN)`

## Task Commits

1. **RED: Failing metrics and PMC tests** - `5db0e03` (test)
2. **GREEN: metrics.py and pmc.py implementation** - `2a8271a` (feat)

## Files Created/Modified

- `sports_science/metrics.py` (new): `_compute_np`, `compute_tss` (TOOL-04)
- `sports_science/pmc.py` (new): `CTL_ALPHA`, `ATL_ALPHA`, `update_pmc` (TOOL-05)
- `tests/sports_science/test_metrics.py` (modified): 12 real tests replacing 4 skip stubs
- `tests/sports_science/test_pmc.py` (modified): 9 real tests replacing 2 skip stubs

## Decisions Made

- NP zeros are NOT filtered: coasting (0W) segments contribute to 30s rolling windows. The 4th-power weighting means zeros pull NP well below peak power, which is the correct physiological behavior (Pitfall 1 avoided).
- Spike clip runs BEFORE `np.convolve`: a 5000W spike clipped to 600W (FTP*3) changes the rolling windows that include it; running clip after convolve would let the spike corrupt adjacent windows.
- All-zero array edge case handled with explicit `np_watts == 0.0` guard returning TSS=0.0 -- avoids `0/ftp` division which would yield 0 anyway, but more explicit.
- TSB uses prev_ctl/prev_atl (yesterday), not new_ctl/new_atl: TSB represents form entering today's session, before today's load is accounted for.
- `CTL_ALPHA` and `ATL_ALPHA` are computed once at module import from `CTL_TC`/`ATL_TC` in constants.py -- no inline magic numbers.

## Deviations from Plan

None - plan executed exactly as written.

## Known Stubs

None - all functions fully implemented and returning real data.

## Threat Flags

None - no new network endpoints, auth paths, file access, or schema changes introduced. TRUST-01 confirmed by test (no anthropic imports in sports_science/).

## Self-Check: PASSED

- `sports_science/metrics.py` exists: FOUND
- `sports_science/pmc.py` exists: FOUND
- `tests/sports_science/test_metrics.py` exists with 12 passing tests: FOUND
- `tests/sports_science/test_pmc.py` exists with 9 passing tests: FOUND
- Commit 5db0e03 (RED): FOUND
- Commit 2a8271a (GREEN): FOUND
- TRUST-01: zero anthropic imports in sports_science/: PASS

---
*Phase: 01-sports-science-foundation*
*Completed: 2026-06-19*
