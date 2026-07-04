---
phase: 08-trust-model-integrity
plan: 07
subsystem: onboarding-agent
tags: [python, fastapi, anthropic, trust-model, onboarding, tdd]

# Dependency graph
requires:
  - phase: 08-01
    provides: "profiles.hr_zones_available nullable boolean column (live migration)"
  - phase: 08-03
    provides: "estimate_lthr_from_max_hr tool, registered in TOOL_REGISTRY and TOOL_SCHEMAS"
  - phase: 08-05
    provides: "conversation_id threading through onboarding.py's sse_generator call site (not touched by this plan)"
provides:
  - "save_profile persists hr_zones_available, derived server-side as (lthr_estimate is not None)"
  - "ONBOARDING_SYSTEM_PROMPT collects a 7th field (heart_rate_baseline) with three explicit LTHR/max-HR/neither branches and correct tool order"
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Derived flag from an existing optional parameter (hr_zones_available <- lthr_estimate is not None) instead of adding a new LLM-facing tool parameter, keeping tools.py's save_profile schema unchanged"
    - "Three-branch prompt instruction pattern: user-given value used as-is, tool-derived estimate flagged as an estimate, unknown case routed to an existing safe fallback path -- LLM never invents the number in any branch"

key-files:
  created: []
  modified:
    - backend/sports_science/profile.py
    - backend/routes/onboarding.py
    - tests/api/test_onboarding.py

key-decisions:
  - "hr_zones_available is derived, not a new function parameter -- tools.py's save_profile schema needed zero changes, matching the plan's explicit instruction"
  - "The 6-field onboarding list became 7 fields (added heart_rate_baseline) rather than folding the HR question into back_status or another existing field, since it is a genuinely independent required input with its own three-branch behavior"
  - "sse_generator call site in onboarding.py was left untouched per the plan's explicit boundary (Plan 05 owns conversation_id threading there)"

patterns-established:
  - "Prompt-contract tests assert string-contains behavior on ONBOARDING_SYSTEM_PROMPT (tool name, RPE fallback wording, branch keywords) rather than attempting to assert live LLM behavior -- matching the existing structural test style in this file"

requirements-completed: [ONBD-05]

coverage:
  - id: D1
    description: "save_profile writes hr_zones_available=True when lthr_estimate is given/estimated, False when lthr_estimate is None"
    requirement: "ONBD-05"
    verification:
      - kind: unit
        ref: "tests/api/test_onboarding.py::test_save_profile_persists_hr_zones_available_true_when_lthr_given"
        status: pass
      - kind: unit
        ref: "tests/api/test_onboarding.py::test_save_profile_persists_hr_zones_available_false_when_lthr_none"
        status: pass
    human_judgment: false
  - id: D2
    description: "ONBOARDING_SYSTEM_PROMPT asks the LTHR/max-HR question, references estimate_lthr_from_max_hr, describes the RPE-only fallback, and preserves the confirmation gate + tool order"
    requirement: "ONBD-05"
    verification:
      - kind: unit
        ref: "tests/api/test_onboarding.py::test_onboarding_prompt_covers_lthr_question_and_branches"
        status: pass
      - kind: other
        ref: "python -c import-time assertion (estimate_lthr_from_max_hr in prompt; lthr/lactate threshold in prompt; rpe in prompt) -- printed 'ok'"
        status: pass
    human_judgment: false
  - id: D3
    description: "Live onboarding conversation asks the HR question before any HR-zone/plan tool call and all three branches produce the expected profile state"
    requirement: "ONBD-05"
    verification:
      - kind: manual
        ref: "08-VALIDATION.md Manual-Only row (not yet executed in this plan)"
        status: pending
    human_judgment: true

duration: 12min
completed: 2026-07-04
status: complete
---

# Phase 08 Plan 07: Onboarding LTHR Question and hr_zones_available Persistence Summary

**Closed the onboarding LTHR gap (CONTEXT.md defect #5 / D-05): added a heart-rate baseline question with three explicit branches to ONBOARDING_SYSTEM_PROMPT (LTHR given, max-HR estimated via the registered estimate_lthr_from_max_hr tool, or neither known falling back to RPE-only), and made save_profile persist an explicit hr_zones_available flag derived from LTHR presence.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 2 completed (Task 1 followed full TDD RED -> GREEN)
- **Files modified:** 3

## Accomplishments
- `save_profile` (`backend/sports_science/profile.py`) now writes `hr_zones_available: lthr_estimate is not None` to the `profiles` upsert dict, alongside the existing `lthr_estimate`/`lthr` keys. No new function parameter was added, so `tools.py`'s registered `save_profile` schema is unchanged.
- `ONBOARDING_SYSTEM_PROMPT` (`backend/routes/onboarding.py`) now collects 7 required fields (added `heart_rate_baseline`), asking "Do you know your lactate threshold heart rate (LTHR), or your resting/max heart rate?" with three explicit branches:
  - Branch A (LTHR known): used directly as `lthr_estimate` for `save_profile`, then `calculate_hr_zones`.
  - Branch B (max HR known, not LTHR): routes through the `estimate_lthr_from_max_hr` tool (registered by Plan 03), tells the user the result is an estimate, then uses the tool's LTHR for `save_profile` and `calculate_hr_zones`.
  - Branch C (neither known): tells the user the plan uses RPE targets, calls `save_profile` with no LTHR, and skips `calculate_hr_zones` entirely — falling back to the existing RPE-only cold-start path (Phase 3 D-07).
  - The confirmation GATE ("Here is what I have") and the D-08 TOOL ORDER instruction (`save_profile` -> `progress_load` -> `[calculate_hr_zones]` -> `generate_plan`) were preserved and updated to reflect the conditional `calculate_hr_zones` step.
  - The `sse_generator` call site was not touched, per the plan's explicit boundary (Plan 05 owns `conversation_id` threading there).
- `tests/api/test_onboarding.py` gained 3 new tests: two direct `save_profile` persistence tests (`hr_zones_available` True/False) and one prompt-contract test (`test_onboarding_prompt_covers_lthr_question_and_branches`) asserting the prompt references the LTHR question, the `estimate_lthr_from_max_hr` tool name, the RPE-only fallback, and that the pre-existing confirmation-gate/tool-order contract still holds.
- Full suite (`pytest tests/ -q`): 286 passed, 9 failed — the exact pre-existing baseline (8x `test_sse.py` + 1x `test_capability_gap.py`), zero new regressions.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): add failing test for hr_zones_available persistence** - `08195fa` (test)
2. **Task 1 (GREEN): persist hr_zones_available in save_profile** - `7c5c26b` (feat)
3. **Task 2: add LTHR onboarding question and three-branch handling** - `e09dc9d` (feat)

**Plan metadata:** SUMMARY.md committed by this worktree agent per parallel-execution convention; STATE.md/ROADMAP.md excluded (orchestrator owns those writes after the wave completes).

## Files Created/Modified
- `backend/sports_science/profile.py` - `save_profile` writes `hr_zones_available` derived from `lthr_estimate` presence
- `backend/routes/onboarding.py` - `ONBOARDING_SYSTEM_PROMPT` gains the LTHR/max-HR/neither question, three-branch handling, and updated tool-order instruction
- `tests/api/test_onboarding.py` - 2 `hr_zones_available` persistence tests + 1 `ONBOARDING_SYSTEM_PROMPT` contract test

## Decisions Made
- Kept `hr_zones_available` derived (not a new parameter) exactly as the plan specified, so `tools.py`'s `save_profile` tool schema needed zero changes — the flag is a pure server-side derivation from an already-existing optional parameter.
- Expanded the field count from 6 to 7 rather than overloading an existing field, since the heart-rate baseline question is a genuinely independent required input with its own three-branch behavior that needed explicit prompt real estate.
- Followed full TDD RED -> GREEN for Task 1 (tdd="true") even though the change was small: wrote and confirmed two failing assertions against the un-modified `profile.py`, then implemented the one-line derived-flag addition and confirmed both tests went green.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched the plan's `<action>` blocks; no Rule 1-4 fixes were needed.

## Issues Encountered
- This worktree has no `.venv` checked out per-worktree (consistent with 08-01/08-05's documented finding). Resolved by invoking the main repo's `.venv/bin/python` by absolute path for all test runs; no workaround touches git-tracked state.
- Also noted: absolute-path Edit/Write calls constructed from the main-repo path are rejected by the harness's worktree isolation guard ("Edit the worktree copy of this file instead of the shared-checkout path"). Confirmed via `diff` that the main-repo and worktree copies of the touched files were byte-identical before editing, then re-issued every Edit against the worktree's own absolute path (`.claude/worktrees/agent-ac2039c69efe49923/...`).

## User Setup Required
None - no external service configuration required. `estimate_lthr_from_max_hr` (Plan 03) and the `profiles.hr_zones_available` column (Plan 01) were both already live before this plan started.

## Next Phase Readiness
- ONBD-05 (D-05) is closed: the onboarding interview now always asks the HR baseline question before any HR-zone/plan tool call, with no code path where the LLM could invent an LTHR number.
- Manual-Only verification (D3 above) — a real onboarding conversation exercising all three branches end-to-end — is recorded as pending per 08-VALIDATION.md and is not blocking for this plan's completion.
- No blockers for subsequent phase-8 plans.

---
*Phase: 08-trust-model-integrity*
*Completed: 2026-07-04*
