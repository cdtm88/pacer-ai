---
phase: 03-coaching-loop
plan: 06
subsystem: agent
tags: [scheduling, sse, trust-transparency, regression-test, gap-closure]

# Dependency graph
requires:
  - phase: 03-coaching-loop (03-01..03-05)
    provides: generate_plan/_persist_generated_plan scheduling pipeline (agent/tools.py) and the shared sse_generator transparency channel (routes/_sse.py) this plan patches
provides:
  - "Collision-aware _resolve_all_scheduled_dates: no two persisted sessions ever share a scheduled_date, including when preferred_days is shorter than n_sessions"
  - "Done-gated assistant_sink persistence: sse_generator only persists assistant text when the turn's terminal event is done, not merely when the loop exits without an exception"
  - "Three regression tests locking both fixes"
affects: [phase-10-hygiene-and-safety-nets]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Collision resolution by forward date-advance: when a naive target date is already claimed, advance +1 day in a loop until free, rather than only special-casing one known collision source"
    - "Terminal-event tracking for generator gating: track the type of the LAST yielded event across a loop, not just whether the loop exited without raising, when success is defined by a specific terminal state"

key-files:
  created:
    - .planning/phases/03-coaching-loop/deferred-items.md
  modified:
    - backend/agent/tools.py
    - backend/routes/_sse.py
    - tests/agent/test_tools_phase3.py
    - tests/agent/test_sse.py

key-decisions:
  - "Fixed the resolver's first pass (advance-past-collision) rather than _build_sessions -- smaller, targeted change that catches every collision source (not just the week-1-roll case) and is verified to preserve both pre-existing scheduling tests unchanged"
  - "Task 3 (WR-06) executed as a genuine RED/GREEN pair: wrote both new tests first and confirmed test_sink_not_appended_on_error_terminated_turn actually failed against the pre-fix _sse.py, then implemented the fix and confirmed both pass -- live proof, not asserted"
  - "Verified the CR-01 regression test would have failed pre-fix by exec'ing the pre-05b30ad function body in an isolated namespace (via git show), rather than reverting any tracked file -- avoids any destructive git operation on the working tree"
  - "Ran tests via the main repo's .venv (/Users/christianmoore/ai/pacer-ai/.venv, absolute path, cwd stayed inside the worktree throughout) since this worktree has no local .venv and .venv/ is gitignored per-checkout; read-only use of a shared binary, no writes outside the worktree"
  - "Did not fix the 8 pre-existing tests/agent/test_sse.py::TestSSEEventSequence failures (auth-gated HTTP endpoint, no JWT supplied) -- confirmed pre-existing and unrelated, already tracked in Phase 06/07 deferred-items.md and scoped to Phase 10; logged a matching entry in this phase's new deferred-items.md instead of expanding scope"

requirements-completed: [PLAN-01, FIT-04, FIT-05, ADAPT-01, TRANSP-01]

coverage:
  - id: D1
    description: "CR-01: _resolve_all_scheduled_dates is collision-aware for ALL sessions (not only week-1-rolled ones), so no two persisted sessions ever share a scheduled_date even when preferred_days is shorter than n_sessions"
    requirement: "ADAPT-01"
    verification:
      - kind: unit
        ref: "tests/agent/test_tools_phase3.py#test_week1_rollforward_avoids_week2_collision"
        status: pass
      - kind: unit
        ref: "tests/agent/test_tools_phase3.py#test_resolve_all_dates_no_roll_matches_single_resolver"
        status: pass
      - kind: unit
        ref: "tests/agent/test_tools_phase3.py#test_scheduled_dates_unique_when_preferred_days_shorter_than_sessions"
        status: pass
    human_judgment: false
  - id: D2
    description: "WR-06: sse_generator gates the assistant_sink append on a done-terminated turn; an error-event terminal (max_tool_turns/unexpected_stop/max_retries) persists nothing"
    requirement: "TRANSP-01"
    verification:
      - kind: unit
        ref: "tests/agent/test_sse.py#test_sink_not_appended_on_error_terminated_turn"
        status: pass
      - kind: unit
        ref: "tests/agent/test_sse.py#test_sink_appended_on_normal_completion"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-07-07
status: complete
---

# Phase 3 Plan 06: Coaching Loop Gap Closure (CR-01, WR-06) Summary

**Made `_resolve_all_scheduled_dates`'s first pass collision-aware for every session (not just week-1 roll-forwards), and gated `sse_generator`'s `assistant_sink` append on a `done`-terminated turn instead of "loop exited without raising" -- closing the two open findings from 03-VERIFICATION.md with three new regression tests.**

## Performance

- **Duration:** 18 min (approximate)
- **Completed:** 2026-07-07
- **Tasks:** 3
- **Files modified:** 4 (2 source, 2 test)

## Accomplishments

- **CR-01 (blocker) closed:** `_resolve_all_scheduled_dates`'s first pass now advances a non-rolled session's candidate date forward one day at a time while it collides with an already-claimed date. Previously it blindly assigned every non-rolled session its naive `(week, day)` date, so `_build_sessions` cycling a `preferred_days` list shorter than `n_sessions` (e.g. 2 preferred days, 4 sessions/week -- an ordinary onboarding answer) produced 8 duplicate `scheduled_date`s out of 16 in a 4-week plan. Confirmed live, before and after the fix, with `_build_sessions(4.0, "none", [], "insufficient_data", None, preferred_days=["Tuesday","Thursday"])` resolved against a Monday `confirm_date`: 8/16 unique pre-fix, 16/16 unique post-fix.
- **New regression test:** `test_scheduled_dates_unique_when_preferred_days_shorter_than_sessions` guards the producer really emits the collision, then asserts all 16 resolved dates are unique. Confirmed (via isolated `exec` of the pre-fix function body extracted with `git show`, no working-tree reverts) that it fails 8/16 against the pre-05b30ad resolver and passes against the current fix.
- **WR-06 closed:** `sse_generator` now tracks `terminal_event` (the type of the LAST event `run_turn` yielded) and only appends accumulated assistant text to `assistant_sink` when `terminal_event == "done"`. Previously any exception-free generator exit triggered the append, including `run_turn`'s abnormal paths (`max_tool_turns`, `unexpected_stop`, `max_retries`) which each yield `event: error` and then `return` normally -- so partial/truncated text was persisted as if the turn completed.
- **Two new regression tests** drive `sse_generator` directly (not through the HTTP endpoint): `test_sink_not_appended_on_error_terminated_turn` (written first, confirmed failing against the pre-fix code) and `test_sink_appended_on_normal_completion` (companion, locks existing correct behavior).
- Both existing scheduling tests (`test_week1_rollforward_avoids_week2_collision`, `test_resolve_all_dates_no_roll_matches_single_resolver`) still pass unchanged; the week-1-roll second pass was untouched.

## Task Commits

Each task was committed atomically (Task 3 as a genuine RED/GREEN pair per `tdd="true"`):

1. **Task 1: Make `_resolve_all_scheduled_dates` collision-aware (CR-01 fix)** - `05b30ad` (fix)
2. **Task 2: CR-01 regression test** - `9382857` (test)
3. **Task 3a: WR-06 regression tests (RED -- confirmed failing pre-fix)** - `4e88add` (test)
3. **Task 3b: WR-06 fix (GREEN)** - `088c8c6` (fix)

**Plan metadata:** `ab73800` (docs: deferred-items.md for the pre-existing test_sse.py auth-gate failures discovered during verification)

## Files Created/Modified

- `backend/agent/tools.py` - `_resolve_all_scheduled_dates`'s first pass advances past collisions for all non-rolled sessions; docstring states the general uniqueness guarantee (CR-01)
- `backend/routes/_sse.py` - `sse_generator` tracks `terminal_event`; `assistant_sink` append gated on `terminal_event == "done"` (WR-06)
- `tests/agent/test_tools_phase3.py` - added `test_scheduled_dates_unique_when_preferred_days_shorter_than_sessions`
- `tests/agent/test_sse.py` - added `_mock_run_turn_token_then_error`/`_mock_run_turn_token_then_done` mock generators and `TestAssistantSinkGating` class (2 tests)
- `.planning/phases/03-coaching-loop/deferred-items.md` - new; logs the pre-existing `test_sse.py::TestSSEEventSequence` auth-gate failures discovered while verifying this plan

## Decisions Made

- Fixed the resolver, not `_build_sessions` -- smaller, targeted, and catches every collision source while preserving both pre-existing scheduling tests unchanged (per plan instruction).
- Executed Task 3 as a real RED/GREEN pair: the error-path test was written and run against the unfixed `_sse.py` first, confirmed failing with the exact predicted symptom (`sink == ['partial reply before failure']` instead of `[]`), then the fix was implemented and both tests re-run green.
- Verified the CR-01 test's pre-fix failure via an isolated `exec` of the pre-05b30ad function body (extracted with `git show 05b30ad~1:...`), rather than reverting any tracked file -- keeps the working tree untouched by any destructive/temporary git operation.
- Used the main repo's `.venv` (absolute path `/Users/christianmoore/ai/pacer-ai/.venv/bin/python`) to run pytest, since this worktree has no local `.venv` (gitignored, per-checkout) -- cwd stayed inside the worktree for every command; this is read-only use of a shared binary, not a write outside the worktree.

## Deviations from Plan

None - plan executed exactly as written. (The `deferred-items.md` creation is process documentation, not a deviation from the plan's tasks/acceptance criteria.)

## Issues Encountered

- **8 pre-existing, out-of-scope failures in `tests/agent/test_sse.py::TestSSEEventSequence`.** Confirmed via a full baseline run of `pytest tests/agent/test_tools_phase3.py tests/agent/test_sse.py -q` *before* any 03-06 change, and via `git diff <wave-start-base> -- tests/agent/test_sse.py` showing this plan's edits are additions only (zero lines changed in the existing `TestSSEEventSequence` class). All 8 fail identically: `GET /chat/stream` requires a verified Supabase JWT via `get_current_user` (added 2026-07-02, commit `b3fcf39`), but these tests send no `Authorization` header and no `?token=` query param, so every request returns 401 before the endpoint's own logic runs (e.g. `test_sse_requires_conversation_id` expects 422, gets 401). This exact failure signature is already tracked in `.planning/phases/06-core-loop-persistence/deferred-items.md` and `.planning/phases/07-deploy-consolidation/deferred-items.md`, and is already scoped to Phase 10 (Hygiene and Safety Nets) in STATE.md's Roadmap Evolution section. Not fixed here per the scope boundary rule -- this plan's own two new tests (`test_sink_not_appended_on_error_terminated_turn`, `test_sink_appended_on_normal_completion`) sidestep the issue entirely by driving `sse_generator` directly, exactly as the plan specified. Logged in `.planning/phases/03-coaching-loop/deferred-items.md`.
- The plan's `<verify>` commands were written assuming a non-worktree `cd /Users/christianmoore/ai/pacer-ai` invocation; executed instead from this worktree's own root (same test files, same result) to avoid cwd-drift into the main repo per worktree-path-safety guidance.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Both 03-VERIFICATION.md findings (CR-01 blocker, WR-06 recommended) are closed with regression coverage; 03-01..03-05 PLAN/SUMMARY files are untouched (confirmed via diff).
- `pytest tests/agent/test_tools_phase3.py tests/agent/test_sse.py -q`: 27 passed (25 pre-existing/gap-closure tests in test_tools_phase3.py + 2 new sink-gating tests), 8 failed (pre-existing, unrelated, documented above). Full repo suite (`pytest tests/ -q`): 319 passed, 8 failed (same 8).
- No blockers for downstream phases. The 8 pre-existing `test_sse.py` auth-gate failures remain the one known gap in this file, already on the Phase 10 backlog.

## Self-Check: PASSED

- `backend/agent/tools.py`: FOUND, `_resolve_all_scheduled_dates` collision-aware first pass present
- `backend/routes/_sse.py`: FOUND, `terminal_event` gating present, signature unchanged
- `tests/agent/test_tools_phase3.py`: FOUND, new test present and passing
- `tests/agent/test_sse.py`: FOUND, new mock generators + `TestAssistantSinkGating` class present and passing
- `.planning/phases/03-coaching-loop/deferred-items.md`: FOUND
- Commits FOUND in `git log --oneline`: `05b30ad`, `9382857`, `4e88add`, `088c8c6`, `ab73800`
- All task-level `<acceptance_criteria>` re-verified passing
- Plan-level `<verification>` command re-run: 27 passed / 8 pre-existing-unrelated-failed (documented)
- No new top-level function introduced in `tools.py`; `plan.py`/`_resolve_scheduled_date` confirmed byte-identical to base via diff
- `sse_generator` and `_resolve_all_scheduled_dates` signatures confirmed unchanged via diff against base commit

---
*Phase: 03-coaching-loop*
*Completed: 2026-07-07*
