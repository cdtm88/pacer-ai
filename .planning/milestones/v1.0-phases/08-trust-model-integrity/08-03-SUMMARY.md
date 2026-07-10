---
phase: 08-trust-model-integrity
plan: 03
subsystem: sports-science-tool-library
tags: [python, coggan-allen, hr-zones, trust-model, tool-registry, pytest]

# Dependency graph
requires:
  - phase: 01-tool-library
    provides: calculate_hr_zones and the ToolResult shape convention
  - phase: 02-trust-enforcement
    provides: TOOL_REGISTRY / TOOL_SCHEMAS TRUST-02 invariant assertion
provides:
  - Corrected HR_ZONE_BOUNDARIES matching true Coggan/Allen percentages of LTHR (68/83/94/105)
  - LTHR_FROM_MAX_HR_RATIO auditable constant (0.875)
  - estimate_lthr_from_max_hr tool, registered in TOOL_REGISTRY and TOOL_SCHEMAS
  - HR zone boundary-no-overlap and Zone 2 ceiling regression test coverage
affects: [08-07-onboarding-lthr-question]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Methodology-tagged estimate tools: low-confidence derivations (max-HR -> LTHR) still originate in the tool library with an explicit caveat in the methodology string, never in LLM reasoning"

key-files:
  created: []
  modified:
    - backend/sports_science/constants.py
    - backend/sports_science/zones.py
    - backend/agent/tools.py
    - tests/sports_science/test_zones.py
    - tests/agent/test_tools_phase3.py

key-decisions:
  - "HR_ZONE_BOUNDARIES corrected to true Coggan/Allen (0.68/0.83/0.94/1.05 of LTHR), dropping Zone 2 ceiling from 0.90 to 0.83 -- one fix resolves both the methodology-honesty defect (D-06) and the beginner-safety concern"
  - "LTHR_FROM_MAX_HR_RATIO (0.875) lives in constants.py as an explicit, auditable, low-confidence estimate rather than being computed ad hoc"
  - "estimate_lthr_from_max_hr is a pure function (constants/types imports only) preserving the TRUST-01 boundary; not added to the save_profile/generate_plan user_id injection allowlist since it takes no user_id"

patterns-established:
  - "Pattern: HR_ZONE_BOUNDARIES dict shape mirrors POWER_ZONE_BOUNDARIES exactly so zones.py logic requires no change when boundary values are corrected"

requirements-completed: [TOOL-02, ONBD-05]

coverage:
  - id: D1
    description: "HR_ZONE_BOUNDARIES corrected to true Coggan/Allen percentages (68/83/94/105 of LTHR), honest methodology label, Zone 2 ceiling gentler for beginners"
    requirement: "TOOL-02"
    verification:
      - kind: unit
        ref: "tests/sports_science/test_zones.py#test_hr_zone_boundary_no_overlap"
        status: pass
      - kind: unit
        ref: "tests/sports_science/test_zones.py#test_hr_zone2_ceiling_is_beginner_safe"
        status: pass
    human_judgment: false
  - id: D2
    description: "estimate_lthr_from_max_hr tool added, pure, methodology-tagged, registered in TOOL_REGISTRY and TOOL_SCHEMAS"
    requirement: "ONBD-05"
    verification:
      - kind: unit
        ref: "tests/sports_science/test_zones.py#test_estimate_lthr_from_max_hr"
        status: pass
      - kind: unit
        ref: "tests/agent/test_tools_phase3.py#test_trust02_still_passes_after_new_tools"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-07-04
status: complete
---

# Phase 08 Plan 03: HR Zone Correction and LTHR Estimator Summary

**Corrected mislabeled HR_ZONE_BOUNDARIES to true Coggan/Allen (68/83/94/105% of LTHR, Zone 2 ceiling dropping from 90% to 83%) and added a registered, methodology-tagged estimate_lthr_from_max_hr tool for the onboarding max-HR branch.**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-04T21:41:09+01:00
- **Completed:** 2026-07-04T21:44:33+01:00
- **Tasks:** 3 completed
- **Files modified:** 5 (4 planned + 1 deviation fix)

## Accomplishments
- HR_ZONE_BOUNDARIES now matches the true Coggan/Allen model (0.68/0.83/0.94/1.05 of LTHR), so the "Coggan/Allen" methodology label the tool already claimed is now honest, and Zone 2's ceiling drops from a hot 90% to a beginner-safe 83% of LTHR
- Added LTHR_FROM_MAX_HR_RATIO (0.875), an explicit, auditable constant for the max-HR-to-LTHR heuristic
- Added estimate_lthr_from_max_hr(max_hr) -> ToolResult in zones.py: pure, no DB/Anthropic imports, methodology string explicitly flags it as a rough estimate
- Registered the new tool in both TOOL_REGISTRY and TOOL_SCHEMAS; the TRUST-02 import-time invariant (schema names == registry keys) still passes
- Extended test_zones.py with an HR zone boundary-no-overlap parametrized test (mirroring the existing power-zone test), a Zone 2 ceiling regression guard, and a dedicated estimator test
- Fixed a pre-existing hardcoded tool-count assertion (10 -> 11) in tests/agent/test_tools_phase3.py that the new tool registration correctly broke

## Task Commits

Each task was committed atomically:

1. **Task 1: Correct HR_ZONE_BOUNDARIES and add LTHR_FROM_MAX_HR_RATIO** - `ed04cf8` (fix)
2. **Task 2: Add estimate_lthr_from_max_hr tool and register it (TDD)**
   - RED: `4786050` (test) - failing test for not-yet-existing estimate_lthr_from_max_hr
   - GREEN: `210aced` (feat) - implementation + registration
3. **Task 3: Extend test_zones.py with HR boundary + Zone 2 ceiling coverage** - `479c7b6` (test)
4. **Deviation fix: update hardcoded tool count (10 -> 11)** - `aa8e471` (fix)

**Plan metadata:** committed by orchestrator after wave completion (worktree mode - STATE.md/ROADMAP.md excluded here).

## Files Created/Modified
- `backend/sports_science/constants.py` - corrected HR_ZONE_BOUNDARIES; added LTHR_FROM_MAX_HR_RATIO
- `backend/sports_science/zones.py` - added estimate_lthr_from_max_hr(max_hr) -> ToolResult
- `backend/agent/tools.py` - imported and registered estimate_lthr_from_max_hr in TOOL_REGISTRY and TOOL_SCHEMAS
- `tests/sports_science/test_zones.py` - HR boundary-no-overlap test, Zone 2 ceiling regression guard, LTHR estimator test
- `tests/agent/test_tools_phase3.py` - updated hardcoded tool count from 10 to 11 (deviation fix)

## Decisions Made
- Kept the HR_ZONE_BOUNDARIES dict shape identical to POWER_ZONE_BOUNDARIES so zones.py's calculate_hr_zones logic required zero changes; only the data was wrong, not the logic
- Value shape for estimate_lthr_from_max_hr is `{"lthr": <int>}` for consistency with how other tool outputs are consumed downstream
- Did not add estimate_lthr_from_max_hr to __init__.py's public `__all__` re-export list, following the plan's explicit instruction to import it directly from `backend.sports_science.zones` in tools.py; only calculate_power_zones/calculate_hr_zones/etc. (the original TRUST-02 contract set) are re-exported at the package level

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed hardcoded TOOL_REGISTRY/TOOL_SCHEMAS count in test_tools_phase3.py**
- **Found during:** Task 2 (full-suite verification after registering the new tool)
- **Issue:** `test_trust02_still_passes_after_new_tools` hardcoded `len(TOOL_REGISTRY) == 10` and `len(TOOL_SCHEMAS) == 10`, which was correct pre-plan but is now stale now that an 11th tool (estimate_lthr_from_max_hr) is legitimately registered
- **Fix:** Updated the docstring and both length assertions to 11, and added an explicit `"estimate_lthr_from_max_hr" in registry_names` membership check
- **Files modified:** tests/agent/test_tools_phase3.py
- **Verification:** Full suite baseline confirmed at exactly 9 pre-existing failures (8x test_sse.py + 1x test_capability_gap.py), matching the documented Phase 08 baseline in 08-RESEARCH.md and 08-VALIDATION.md; no new failures introduced
- **Committed in:** aa8e471

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug caused directly by this plan's correctly-scoped change)
**Impact on plan:** Necessary fix for correctness; no scope creep. The stale hardcoded count would have been a false regression signal for every future plan that touches the tool registry.

## Issues Encountered
None beyond the deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- estimate_lthr_from_max_hr is ready for Plan 07 (onboarding) to wire into the LTHR-question prompt; the tool itself is fully built and registered, only the prompt integration remains
- HR zone correction is a pure data fix; no downstream code needed updates since calculate_hr_zones logic already read from the constant
- Full test suite confirmed at the documented 9 pre-existing baseline failures, no regressions introduced by this plan

---
*Phase: 08-trust-model-integrity*
*Completed: 2026-07-04*

## Self-Check: PASSED

All created/modified files confirmed present on disk; all task and deviation-fix commit hashes confirmed present in `git log --oneline --all` (ed04cf8, 4786050, 210aced, 479c7b6, aa8e471).
