---
phase: 08-trust-model-integrity
plan: 04
subsystem: sports-science
tags: [python, plan-generation, ctl, mesocycle, testing]

# Dependency graph
requires:
  - phase: 08-trust-model-integrity
    provides: "D-02/D-07 architecture pattern for server-side injection of generate_plan's trust-sensitive inputs (research/pattern context only; no code dependency)"
provides:
  - "generate_plan honors preferred_days for real per-user session scheduling"
  - "CTL-gap-aware progression: _is_true_beginner_ramp helper flattens weeks 2-3 to week 1's conservative cap for true low-base beginners"
  - "at-risk beginner combination (low base + moderate back) tightens week 1 cap below the existing 30-minute cap"
  - "ctl_gap_flat_ramp marker in constraints_applied when the ramp is active"
  - "dedicated tests/sports_science/test_plan.py as the PLAN-07 test home"
affects: [08-06 (server-side injection wiring of these same params into dispatch_tool)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Pure-computation helper functions in sports_science/*.py stay dependency-free and directly unit-testable (no mocking)"

key-files:
  created:
    - tests/sports_science/test_plan.py
  modified:
    - backend/sports_science/plan.py

key-decisions:
  - "gap_ratio >= 0.5 (or cold-start current_ctl<=0) confirmed as the true-beginner-ramp threshold per 08-RESEARCH.md Assumption A3"
  - "At-risk beginner (ramp AND back_status=='moderate') week 1 cap tightened to min(20, ...), below the existing 30-minute back-moderate cap"
  - "Week 3's existing lack of a back_status duration cap (uncapped except via the new flat-ramp override) preserved as-is -- out of this plan's scope per truths"
  - "ctl_gap_flat_ramp added to constraints_applied as an observable marker so the ramp is verifiable in plan output, not just internal logic"

patterns-established:
  - "generate_plan's optional/injected params (preferred_days) default to None so existing callers (Plan 03/05 wiring, existing tests) keep working until Plan 06 wires real server-injected values"

requirements-completed: [PLAN-07, PLAN-06]

coverage:
  - id: D1
    description: "generate_plan schedules sessions on preferred_days when supplied, falling back to _DEFAULT_DAYS only when empty/None"
    requirement: "PLAN-07"
    verification:
      - kind: unit
        ref: "tests/sports_science/test_plan.py#test_preferred_days_used_when_supplied"
        status: pass
      - kind: unit
        ref: "tests/sports_science/test_plan.py#test_preferred_days_none_falls_back_to_default"
        status: pass
      - kind: unit
        ref: "tests/sports_science/test_plan.py#test_preferred_days_empty_list_falls_back_to_default"
        status: pass
    human_judgment: false
  - id: D2
    description: "True low-base beginner (current_ctl far below recommended_ctl_target, including cold-start) gets flat weeks 1-3 duration instead of ramping to full base_duration"
    requirement: "PLAN-07"
    verification:
      - kind: unit
        ref: "tests/sports_science/test_plan.py#test_true_beginner_cold_start_flat_ramp_weeks_1_to_3_equal"
        status: pass
    human_judgment: false
  - id: D3
    description: "At-risk beginner (true-beginner-ramp AND back_status=='moderate') gets week 1 duration capped tighter than the existing 30-minute back-moderate cap"
    requirement: "PLAN-07"
    verification:
      - kind: unit
        ref: "tests/sports_science/test_plan.py#test_at_risk_beginner_week1_capped_below_30"
        status: pass
    human_judgment: false
  - id: D4
    description: "Near-target non-beginner preserves today's week1-conservative/week2-3-full template (change is conditional, not blanket)"
    requirement: "PLAN-07"
    verification:
      - kind: unit
        ref: "tests/sports_science/test_plan.py#test_near_target_non_beginner_preserves_week2_3_full_template"
        status: pass
    human_judgment: false
  - id: D5
    description: "_is_true_beginner_ramp helper correctly classifies target<=0, gap_ratio boundary (0.5), gap_ratio small (0.1), and cold-start cases"
    requirement: "PLAN-07"
    verification:
      - kind: unit
        ref: "tests/sports_science/test_plan.py#test_is_true_beginner_ramp_target_non_positive_is_false"
        status: pass
      - kind: unit
        ref: "tests/sports_science/test_plan.py#test_is_true_beginner_ramp_gap_ratio_half_is_true"
        status: pass
      - kind: unit
        ref: "tests/sports_science/test_plan.py#test_is_true_beginner_ramp_gap_ratio_small_is_false"
        status: pass
      - kind: unit
        ref: "tests/sports_science/test_plan.py#test_is_true_beginner_ramp_cold_start_always_true"
        status: pass
    human_judgment: false

# Metrics
duration: 12min
completed: 2026-07-04
status: complete
---

# Phase 8 Plan 04: generate_plan CTL-gap-aware progression and preferred_days Summary

**Wired `generate_plan`'s previously-dead `current_ctl`/`load_targets` params into a real CTL-gap-aware progression and replaced the hardcoded `_DEFAULT_DAYS` scheduling with real `preferred_days` support, backed by a new dedicated test module.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-04T21:41:00Z
- **Completed:** 2026-07-04T21:53:00Z
- **Tasks:** 2
- **Files modified:** 2 (1 modified, 1 created)

## Accomplishments
- `generate_plan` gains `preferred_days: list[str] | None = None`, threaded into `_build_sessions`, replacing the hardcoded `_DEFAULT_DAYS[:n_sessions]` slice with `(preferred_days or _DEFAULT_DAYS)[:n_sessions]`
- New `_is_true_beginner_ramp(current_ctl, load_targets) -> bool` helper (gap_ratio >= 0.5 threshold, cold-start current_ctl<=0 always qualifies) makes the previously-ignored `current_ctl`/`load_targets` params actually drive plan structure
- When the ramp is active, weeks 2 and 3 use the same conservative duration cap as week 1 (flat volume) instead of ramping to full `base_duration`; when the ramp is active AND `back_status=='moderate'`, week 1's cap tightens to `min(20, ...)` (below the existing 30-minute back-moderate cap)
- `ctl_gap_flat_ramp` marker added to `constraints_applied` when the ramp is active, making the effect observable in plan output
- Dedicated `tests/sports_science/test_plan.py` created (11 tests) covering preferred_days scheduling, the CTL-gap progression, and the `_is_true_beginner_ramp` boundary cases directly (no mocking, pure function calls)

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire preferred_days and CTL-gap-aware progression into plan.py** - `c1eda53` (feat)
2. **Task 2: Create tests/sports_science/test_plan.py (PLAN-07 dedicated coverage)** - `9f82447` (test)

## Files Created/Modified
- `backend/sports_science/plan.py` - `generate_plan` gains `preferred_days`; `_build_sessions` gains `preferred_days`/`current_ctl`/`load_targets`; new `_is_true_beginner_ramp` helper; week1_duration cap reused to flatten weeks 2-3; `ctl_gap_flat_ramp` constraint marker
- `tests/sports_science/test_plan.py` - New dedicated PLAN-07 test module (11 tests)

## Decisions Made
- Confirmed `gap_ratio >= 0.5` (or cold-start `current_ctl<=0`) as the true-beginner-ramp threshold, matching 08-RESEARCH.md's proposed value (Assumption A3) with no adjustment needed after sanity-checking against the plan's example scenarios
- At-risk beginner week 1 cap set to `min(20, ...)`, satisfying the plan's "tighter than the current 30-minute back-moderate cap" requirement with a clean round number
- Left week 3's pre-existing lack of a `back_status=='moderate'` duration cap untouched (it was never capped even before this plan, except now via the new flat-ramp override) -- out of this plan's stated scope; not a regression, matches "existing non-beginner behaviour is preserved"

## Deviations from Plan

None - plan executed exactly as written. The `_is_true_beginner_ramp` implementation, the week1/2/3 flat-ramp logic, the at-risk tightened cap, and the `preferred_days` fallback all match the plan's `<action>` and `<behavior>` blocks verbatim (including the RESEARCH.md-sourced algorithm).

## Issues Encountered

None. The worktree had no local `.venv`; tests were run via the main repo's `.venv/bin/python` (absolute path) since the interpreter/site-packages are independent of the invoking cwd and pytest resolves paths relative to the repo root either way.

## User Setup Required

None - no external service configuration required. Pure computation change, no DB/schema/package changes.

## Next Phase Readiness

- `backend/sports_science/plan.py` is ready for Plan 06 to wire the real server-injected `current_ctl`/`load_targets`/`preferred_days` values into `dispatch_tool`'s `generate_plan` interception (per 08-RESEARCH.md's D-02/D-07 combined Pattern 2) -- this plan's function signature already accepts and correctly consumes all five trust-sensitive inputs Plan 06 will inject.
- Verified via full test suite run: `9 failed, 261 passed` -- the 9 failures are the exact pre-existing baseline documented in 08-RESEARCH.md (`tests/agent/test_sse.py` x8, `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields` x1). No new regressions from this plan's changes.

## Self-Check: PASSED

- FOUND: backend/sports_science/plan.py
- FOUND: tests/sports_science/test_plan.py
- FOUND commit c1eda53 in git log
- FOUND commit 9f82447 in git log

---
*Phase: 08-trust-model-integrity*
*Completed: 2026-07-04*
