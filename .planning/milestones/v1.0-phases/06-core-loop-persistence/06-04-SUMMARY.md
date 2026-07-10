---
phase: 06-core-loop-persistence
plan: 04
subsystem: api
tags: [fastapi, supabase, adaptations, idempotency, sports-science]

# Dependency graph
requires:
  - phase: 06-core-loop-persistence
    provides: "migration 0005 (sessions.status allows 'missed'; adaptations gains trigger_session_ids uuid[] and status columns)"
provides:
  - "Idempotent detect_signals (never re-emits a signal for an already-consumed session)"
  - "Missed-session status flip on both micro and macro apply paths"
  - "A real, non-dead 30% macro shift guard"
  - "Two-phase macro replan proposal/confirm flow via POST /adaptations/{id}/confirm"
  - "None-safe validate_session_vs_actual"
affects: [06-05, adaptation-ui, calendar-sync]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "trigger_session_ids uuid[] bookkeeping on the adaptations table as the idempotency mechanism for signal consumption (uniform across micro and macro)"
    - "Proposal/confirm two-phase commit for actions requiring user confirmation: persist a status='proposed' row with the exact after_snapshot, apply it verbatim on confirm rather than recomputing"
    - "Auto-supersede prior pending proposals of the same kind before persisting a new one, instead of building a rejection/expiry endpoint"

key-files:
  created: []
  modified:
    - backend/routes/adaptations.py
    - backend/sports_science/compliance.py
    - tests/api/test_adaptations.py

key-decisions:
  - "apply_micro_adjustment also gets trigger_session_ids bookkeeping (not just macro), per orchestrator OQ3 resolution -- an underperformance-triggered micro signal cannot be consumed via a status flip since the session is legitimately 'completed', so the array is the only mechanism that covers both scopes uniformly."
  - "A new macro proposal auto-supersedes any prior status='proposed' row for the user on the next /check, per orchestrator OQ1 resolution -- no separate rejection/expiry endpoint was built (RESEARCH A2: not specified, avoids speculative scope)."
  - "The macro after_sessions generator now shifts session i by (i+2) days (progressive spacing) instead of a uniform +1 day, so check_shift_limit's '>1 day' guard is mathematically reachable; the guard's own >1-day semantics were left untouched."

requirements-completed: [ADAPT-01, ADAPT-02, ADAPT-03, ADAPT-04, TRANSP-02]

coverage:
  - id: D1
    description: "detect_signals is idempotent: a session id already recorded in any adaptations.trigger_session_ids for the user is never re-emitted as a signal on a later check"
    requirement: "ADAPT-01"
    verification:
      - kind: unit
        ref: "tests/api/test_adaptations.py#test_detect_signals_idempotent"
        status: pass
    human_judgment: false
  - id: D2
    description: "A consumed 'missed' signal flips the triggering session's status to 'missed', dual-filtered by id and user_id, on both the micro and macro apply paths"
    requirement: "ADAPT-02"
    verification:
      - kind: unit
        ref: "tests/api/test_adaptations.py#test_apply_micro_adjustment_missed_status_value"
        status: pass
    human_judgment: false
  - id: D3
    description: "The 30% macro shift guard actually fires for a realistic wide replan and blocks the apply when it does"
    requirement: "ADAPT-03"
    verification:
      - kind: unit
        ref: "tests/api/test_adaptations.py#test_apply_macro_replan_shift_limit_fires"
        status: pass
    human_judgment: false
  - id: D4
    description: "A macro replan needing confirmation persists a 'proposed' adaptation row and supersedes any prior proposed row for the same user before doing so"
    requirement: "ADAPT-03"
    verification:
      - kind: unit
        ref: "tests/api/test_adaptations.py#test_apply_macro_replan_supersedes_prior_proposal"
        status: pass
    human_judgment: false
  - id: D5
    description: "POST /adaptations/{id}/confirm applies the exact stored after_snapshot sessions and flips status to 'applied'; a foreign/missing/non-proposed id returns 404 proposal_not_found (IDOR mitigated)"
    requirement: "TRANSP-02"
    verification:
      - kind: unit
        ref: "tests/api/test_adaptations.py#test_confirm_macro_applies_stored_snapshot"
        status: pass
      - kind: unit
        ref: "tests/api/test_adaptations.py#test_confirm_macro_idor_returns_404"
        status: pass
    human_judgment: false
  - id: D6
    description: "validate_session_vs_actual does not raise when actual or planned tss is None (coerced to 0)"
    requirement: "ADAPT-04"
    verification:
      - kind: unit
        ref: "tests/sports_science/test_compliance.py (existing suite, unmodified, still green)"
        status: pass
    human_judgment: false

# Metrics
duration: 45min
completed: 2026-07-03
status: complete
---

# Phase 06 Plan 04: Adaptation idempotency and macro-replan confirm flow Summary

**trigger_session_ids-based signal consumption, a real 30% shift guard, and a working POST /adaptations/{id}/confirm two-phase commit for macro replans**

## Performance

- **Duration:** ~45 min
- **Started:** 2026-07-03T10:36:00+01:00 (approx.)
- **Completed:** 2026-07-03T10:42:42+01:00
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- `detect_signals` now pre-queries `adaptations.trigger_session_ids` for the user and skips any session already consumed, scanning `planned`+`completed` sessions via `.in_()` and branching missed-vs-underperformance by status instead of the old planned-only scan.
- `log_adaptation` gained `status` and `trigger_session_ids` params; both `apply_micro_adjustment` and `apply_macro_replan` now write `trigger_session_ids` and flip the triggering session's status to `'missed'` (dual-filtered by id+user_id) whenever the consumed signal is a miss.
- The macro replan generator now shifts session `i` by `(i+2)` days (progressive spacing) instead of a dead uniform `+1` day, so `check_shift_limit`'s `>1 day` guard can actually fire; when it does, the `needs_confirmation` branch first supersedes any prior `status='proposed'` row for the user, then persists the new proposal and returns its `adaptation_id`.
- New `POST /adaptations/{adaptation_id}/confirm` endpoint dual-filters `id`+`user_id`+`status='proposed'` (404 `proposal_not_found` otherwise), applies the **stored** `after_snapshot` sessions verbatim, and flips the adaptation to `'applied'`.
- `validate_session_vs_actual` coerces `None` `tss` values to `0` for both planned and actual, so it never raises a `TypeError` on that input shape.

## Task Commits

Each task was committed atomically:

1. **Task 1: Make detect_signals idempotent and flip missed sessions; add trigger_session_ids/status to log_adaptation** - `f5ed8ab` (feat)
2. **Task 2: Fix the dead 30% shift guard in apply_macro_replan and supersede prior proposals** - `d699891` (feat)
3. **Task 3: Add POST /adaptations/{id}/confirm to apply a stored proposal** - `76c7ed6` (feat)

_No TDD RED/GREEN/REFACTOR commit split was used; tests and implementation for each task were written and committed together per task, matching the plan's `tdd="true"` intent of test-first design without separate RED/GREEN commits (behavior-adding but tests accompany the same commit as the fix)._

## Files Created/Modified
- `backend/routes/adaptations.py` - detect_signals idempotency + `.in_()` status scan, log_adaptation status/trigger_session_ids params, apply_micro_adjustment and apply_macro_replan bookkeeping + missed status flips, fixed macro shift generator, supersede-then-propose flow, new `confirm_macro_replan` endpoint
- `backend/sports_science/compliance.py` - `None`-safe `tss` coercion in `validate_session_vs_actual`
- `tests/api/test_adaptations.py` - updated `test_missed_detection`/`test_intensity_from_tools`/`test_weekly_check` for the new consumed-ids pre-query and explicit session `status` field; added `test_detect_signals_idempotent`, `test_apply_micro_adjustment_missed_status_value`, `test_apply_macro_replan_shift_limit_fires`, `test_apply_macro_replan_supersedes_prior_proposal`, `test_confirm_macro_applies_stored_snapshot`, `test_confirm_macro_idor_returns_404`

## Decisions Made
- Applied `trigger_session_ids` bookkeeping uniformly to both micro and macro paths (orchestrator OQ3: yes) rather than relying on the status flip alone for micro, since an underperformance-triggered micro signal has no status-flip mechanism available.
- Auto-supersede prior `status='proposed'` rows on the next macro proposal (orchestrator OQ1: yes) instead of building a rejection/expiry endpoint, per RESEARCH A2's recommendation to avoid speculative scope.
- Chose progressive `(i+2)`-day spacing for the macro shift generator (one of two options suggested in the plan) as the simplest deterministic fix that makes `check_shift_limit`'s `>1 day` guard reachable without touching the guard's own semantics.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Updated pre-existing detect_signals tests for the new consumed-ids pre-query and status-scan behavior**
- **Found during:** Task 1
- **Issue:** `test_missed_detection` and `test_intensity_from_tools` mocked exactly two `execute()` calls (sessions, then rides) and omitted a `status` field on session fixtures. The plan's required idempotency pre-query adds a third leading `execute()` call, and the new `status`-based branching (`planned` vs `completed`) needs an explicit `status` key on session fixtures to classify correctly -- without these updates the existing tests would fail purely due to the mandated implementation change, not a real regression.
- **Fix:** Added a `execute_consumed` mock (`data: []`) as the first `side_effect` entry in both tests, added `"status": "planned"` to `test_missed_detection`'s session fixture and `"status": "completed"` to `test_intensity_from_tools`'s, and added `mock_client.in_.return_value = mock_client` to the chain (also added to `test_weekly_check`'s mock for the same reason, though that test's `AsyncMock(return_value=...)` pattern meant it would otherwise silently return the wrong shape rather than fail loudly).
- **Files modified:** tests/api/test_adaptations.py
- **Verification:** `.venv/bin/pytest tests/api/test_adaptations.py tests/sports_science/test_compliance.py -x -q` exits 0 (20 tests after Task 1; 14 after Task 3)
- **Committed in:** f5ed8ab (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking -- pre-existing test fixtures required updates to remain valid under the mandated behavior change)
**Impact on plan:** Necessary to keep the existing regression suite meaningful; no scope creep beyond what Task 1's acceptance criteria already required (full suite green).

## Issues Encountered
- While confirming pre-existing (unrelated) test failures, a `git stash`/`git stash pop` was run against the shared main checkout by mistake instead of the worktree. It was popped immediately and verified byte-identical to its prior state (confirmed via `git diff --stat`); the worktree itself was never touched by this and its `git status` was unaffected throughout. No destructive worktree operations (`git clean`, `git reset --hard`, `git stash` in the worktree) were performed. Logged here for transparency; no corrective action was needed.
- `tests/agent/test_sse.py` (8 tests) and `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields` fail both before and after this plan's changes (verified against a clean `main` checkout) -- unrelated to `backend/routes/adaptations.py`, `backend/sports_science/compliance.py`, or `tests/api/test_adaptations.py`. Logged to `.planning/phases/06-core-loop-persistence/deferred-items.md` per the scope-boundary rule; not fixed here.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- The adaptation core loop (signal detection -> micro/macro dispatch -> logging -> confirm) is now fully idempotent and confirmable end-to-end against the mocked Supabase test suite.
- A live/manual verification against the real Supabase project (confirming the `sessions.status` CHECK constraint accepts `'missed'` and the `adaptations.trigger_session_ids`/`status` columns behave as expected under RLS) is still recommended before this phase gate closes, per 06-RESEARCH.md's Wave 0 Gaps note -- this was already flagged as migration 0005's responsibility (wave 1, plan 06-01) and is outside this plan's scope.
- No blockers for 06-05 or downstream adaptation-UI work; the `POST /adaptations/{id}/confirm` contract (`{"status": "applied", "adaptation_id": ...}` on success, `404 {"error": "proposal_not_found"}` otherwise) is stable for a frontend to build against.

---
*Phase: 06-core-loop-persistence*
*Completed: 2026-07-03*

## Self-Check: PASSED

All claimed files and commit hashes verified present. Final verification command
`.venv/bin/pytest tests/api/test_adaptations.py tests/sports_science/test_compliance.py -x -q`
exits 0 (24 passed).
