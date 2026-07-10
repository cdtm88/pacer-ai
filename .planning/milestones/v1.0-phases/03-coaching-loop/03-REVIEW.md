---
phase: 03-coaching-loop
reviewed: 2026-07-07T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - backend/agent/tools.py
  - backend/routes/_sse.py
  - tests/agent/test_tools_phase3.py
  - tests/agent/test_sse.py
findings:
  critical: 0
  warning: 1
  info: 1
  total: 2
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-07-07T00:00:00Z
**Depth:** standard
**Files Reviewed:** 4
**Status:** issues_found

## Summary

This review is scoped to plan 03-06, a gap-closure plan that fixed two findings from the prior
`03-REVIEW.md`: CR-01 (duplicate `scheduled_date` collisions in `_resolve_all_scheduled_dates` when
`preferred_days` is shorter than the weekly session count) and WR-06 (SSE `assistant_sink`
persisting partial/truncated assistant text on an abnormally-terminated turn). `diff_base` isolates
exactly four commits: `05b30ad` (CR-01 fix), `9382857` (CR-01 regression test), `4e88add` (WR-06
failing test), `088c8c6` (WR-06 fix).

Both fixes were verified correct, not just plausible:

- **CR-01**: Confirmed via manual trace of the new collision-aware first pass (single-source dup
  collisions, cross-week boundary safety given the current `_sessions_per_week` cap of 4, and a
  combined roll-forward + duplicate-day scenario not covered by any test -- see IN-01) and by
  actually running the test suite. `test_scheduled_dates_unique_when_preferred_days_shorter_than_sessions`
  and the two pre-existing WR-02 regression tests all pass against the current code. Reverting to
  the pre-fix `_resolve_all_scheduled_dates` (checked out at
  `29a453f1a865684ee3ebbb9fe4f1a7edd2ff9108^` in an isolated worktree) reproduces the exact
  duplicate-date bug class this fix closes.
- **WR-06**: Confirmed `run_turn` (`backend/agent/loop.py`) never yields further events after an
  `"error"` event -- every `error` yield site is immediately followed by `return` -- so gating the
  `assistant_sink` append on `terminal_event == "done"` (stricter than the originally-suggested
  `!= "error"`) is both correct and safe. `TestAssistantSinkGating`'s two new tests pass.

No Critical or Warning-level *correctness* defects were found in the diff content itself. I found
one genuine robustness/maintainability gap introduced alongside the CR-01 fix (WR-01 below) and one
test-coverage observation (IN-01). I explicitly did **not** re-flag the 8 pre-existing
`tests/agent/test_sse.py::TestSSEEventSequence` failures (`401` instead of expected status codes) --
I confirmed by running the same test file against the `diff_base` commit in an isolated worktree
that these failures pre-date plan 03-06 entirely (an auth-related regression from other,
out-of-scope work) and are not something 03-06 touched or introduced.

## Warnings

### WR-01: Collision-avoidance loop in `_resolve_all_scheduled_dates` depends on an unenforced cross-module invariant

**File:** `backend/agent/tools.py:493-499`

**Issue:** The new first-pass loop pushes a colliding non-rolled session's date forward one day at
a time (`while candidate in used: candidate += timedelta(days=1)`). This is proven collision-free
today, but its correctness -- specifically, that a pushed-forward date can never collide with a
*different* week's legitimately-targeted date -- implicitly depends on the maximum push distance
(`n_sessions - 1`) staying smaller than the 7-day gap to the next week's naive target for the same
weekday. That holds today because `_sessions_per_week()` (`backend/sports_science/plan.py`) caps at
4 sessions/week, but nothing in `tools.py` asserts or even comments on this dependency. If
`_sessions_per_week` is ever changed to allow 5+ sessions/week (e.g. a future "advanced athlete"
tier) without revisiting this function, the collision-avoidance guarantee this fix exists to
provide could silently regress with no test catching it, since no existing regression test
parametrizes `n_sessions` beyond 4.

**Fix:** Add an explicit guard or comment coupling the two modules, e.g.:
```python
# Invariant: this loop assumes the push distance (at most n_sessions - 1) stays
# under 7 days, so a pushed-forward date can never collide with the next
# week's naive target for the same weekday. Revisit if _sessions_per_week()
# is ever raised above 6.
assert len(sessions) <= 28, "resolver assumes <=7 sessions/week; revisit collision math otherwise"
```
or, more robustly, make the guarantee independent of `n_sessions` by tracking `used` per
`(target - monday_of_week1).days % 7` bucket instead of relying on the small-push-distance
assumption.

## Info

### IN-01: No regression test exercises both the CR-01 and WR-02 collision sources in the same plan

**File:** `tests/agent/test_tools_phase3.py`

**Issue:** `test_scheduled_dates_unique_when_preferred_days_shorter_than_sessions` (CR-01) uses a
confirm date with no week-1 roll-forward, and `test_week1_rollforward_avoids_week2_collision`
(WR-02) uses `preferred_days` with no cycling/duplication. Neither test -- nor any other in the
suite -- exercises a plan where a `preferred_days` list shorter than `n_sessions` *and* a week-1
roll-forward happen together. I manually traced this combined scenario (2 preferred days,
`n_sessions=4`, confirm date mid-week so the first Tuesday session rolls) and confirmed the current
fix still produces unique dates, but there is no automated test locking in that guarantee.

**Fix:** Add a regression test combining both conditions, e.g. `preferred_days=["Tuesday",
"Thursday"]` with `weekly_hours=4.0` and a `confirm_date` that falls after both week-1 Tuesday
sessions' naive dates, asserting `len(set(dates)) == len(dates)` as the other tests do.

---

_Reviewed: 2026-07-07T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
