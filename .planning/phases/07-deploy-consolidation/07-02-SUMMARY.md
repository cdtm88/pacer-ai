---
phase: 07-deploy-consolidation
plan: 02
subsystem: backend-serverless-correctness
tags: [fastapi, vercel, backgroundtasks, google-calendar, inline-await]
dependency-graph:
  requires: []
  provides:
    - backend/routes/onboarding.py::onboarding_plan_calendar_sync (inline-await, no BackgroundTasks)
    - backend/routes/adaptations.py::check_adaptations (inline-await calendar sync)
    - backend/routes/adaptations.py::mark_session_missed (inline-await calendar sync)
    - backend/calendar_sync.py::CALENDAR_API_TIMEOUT_SECS (bounded per-call timeout)
  affects:
    - Phase 7 plan 07-04 (preview-deploy verification of these routes under Vercel)
tech-stack:
  added: []
  patterns:
    - "BackgroundTasks -> inline-await (Vercel serverless constraint), matching the Phase 6 rides.py pattern"
    - "asyncio.wait_for(asyncio.to_thread(...), timeout=N) bounding a synchronous Google API call inside an existing try/except-swallow"
key-files:
  created: []
  modified:
    - backend/routes/onboarding.py
    - backend/routes/adaptations.py
    - backend/calendar_sync.py
    - tests/api/test_onboarding.py
    - tests/api/test_adaptations.py
decisions:
  - "onboarding_plan_calendar_sync response literal changed from 'scheduled' to 'completed' -- verified no frontend caller branches on the prior literal, so this is a safe rename"
  - "Bounded timeout set to 8.0s (CALENDAR_API_TIMEOUT_SECS) around each outbound Google Calendar API call; TimeoutError is caught by each helper's existing except Exception swallow (CAL-04), no new error surfacing added"
metrics:
  duration: 12min
  completed: 2026-07-03
status: complete
---

# Phase 07 Plan 02: Convert remaining BackgroundTasks call sites to inline-await Summary

Converted the last three FastAPI `BackgroundTasks` scheduling sites (onboarding plan-calendar-sync, adaptations `check_adaptations`, adaptations `mark_session_missed`) to inline-await, matching the Phase 6 `rides.py` pattern, and added a bounded 8-second timeout around every outbound Google Calendar API call so the now-inline requests cannot hang up to the function's `maxDuration`.

## What Was Built

- **`backend/routes/onboarding.py::onboarding_plan_calendar_sync`**: dropped the `background_tasks: BackgroundTasks` parameter, replaced `background_tasks.add_task(push_all_sessions_to_calendar, user_id)` with `await push_all_sessions_to_calendar(user_id)` directly before the return, changed the response literal from `{"status": "scheduled"}` to `{"status": "completed"}`, removed `BackgroundTasks` from the `fastapi` import, and updated the docstring to describe inline-await behavior.
- **`backend/routes/adaptations.py::check_adaptations`**: dropped the `background_tasks` parameter; the per-session `background_tasks.add_task(update_calendar_event, ...)` call inside the applied-sessions loop is now `await update_calendar_event(user_id, event_id, session)`.
- **`backend/routes/adaptations.py::mark_session_missed`**: same conversion at its call site, inside the existing `try`/`except`-swallow block so a calendar failure still never breaks the endpoint (CAL-04). `BackgroundTasks` removed from the shared `fastapi` import (both routes live in the same module).
- **`backend/calendar_sync.py`**: added module-level `CALENDAR_API_TIMEOUT_SECS = 8.0` and wrapped each of the three `asyncio.to_thread(...)` calls (`push_session_to_calendar`'s `_insert`, `update_calendar_event`'s `_update`, `delete_calendar_event`'s `_delete`) in `asyncio.wait_for(..., timeout=CALENDAR_API_TIMEOUT_SECS)`. A timeout raises `asyncio.TimeoutError`, which each helper's pre-existing `except Exception:` block already swallows (CAL-04) -- no new error-surfacing logic was added.

`backend/` now has zero `background_tasks.add_task(...)` scheduling calls (verified via `grep -rn "add_task" backend/`).

## Tests

Added two RED-then-GREEN test pairs (TDD task):

- `tests/api/test_onboarding.py::test_plan_calendar_sync_inline_await` -- monkeypatches `push_all_sessions_to_calendar` with an `AsyncMock`, POSTs `/onboarding/plan-calendar-sync`, and asserts the mock was awaited once with the authenticated `user_id`, the response body reports `"completed"` (not `"scheduled"`), and `inspect.signature` on the route callable no longer exposes a `background_tasks` parameter.
- `tests/api/test_adaptations.py::test_check_adaptations_inline_awaits_calendar_update` -- drives `POST /adaptations/check` through a monkeypatched `detect_signals` + `apply_micro_adjustment` returning an applied session with a `calendar_event_id`, asserts `update_calendar_event` was awaited with `(user_id, event_id, session)`, and asserts the signature no longer exposes `background_tasks`.
- `tests/api/test_adaptations.py::test_mark_missed_inline_awaits_calendar_update` -- same pattern through `POST /adaptations/sessions/{id}/missed`.

Confirmed RED (all three signature/completion assertions failed) before Task 2, and GREEN after.

## Verification

- `pytest tests/api/test_onboarding.py tests/api/test_adaptations.py -v` -- 28 passed.
- `pytest tests/ -v` -- 245 passed, 9 pre-existing failures unrelated to this plan (see Deviations below; confirmed identical failures with this plan's changes removed).
- `grep -rn "add_task" backend/` -- zero matches.

## Deviations from Plan

### Auto-fixed Issues

None -- plan executed exactly as written for its declared file scope.

### Out-of-Scope Findings (not fixed, logged for awareness)

**1. Unused vestigial `background_tasks: BackgroundTasks` parameter in `backend/routes/rides.py:452`**
- **Found during:** final `grep -rn "BackgroundTasks" backend/` sweep after Task 2.
- **Detail:** `upload_fit`'s signature still declares `background_tasks: BackgroundTasks`, and the `fastapi` import on line 39 still includes `BackgroundTasks`, but no `background_tasks.add_task(...)` call exists anywhere in the function (Phase 6 already inline-awaits `process_ride_background`). This is dead code, not a scheduling call site -- it does not affect behavior or the Vercel freeze-after-response risk.
- **Why not fixed here:** `backend/routes/rides.py` is not in this plan's `files_modified` list (07-02-PLAN.md scopes only `onboarding.py`, `adaptations.py`, and the two test files) and was already fully converted in Phase 6. Removing the unused parameter is a one-line, zero-risk cleanup, but it belongs to a file this plan does not own; flagging it here rather than expanding scope.
- **Recommendation:** A future quick task or Phase 7 plan should drop the unused `background_tasks` parameter (and confirm no other Phase 6 file has a similar residual) so `backend/` is also free of unused `BackgroundTasks` symbols, not just active scheduling calls.

**2. 9 pre-existing test failures unrelated to this plan** (`tests/agent/test_sse.py` -- 8 failures in `TestSSEEventSequence`; `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields`)
- Confirmed these fail identically with this plan's changes removed (verified against the base commit) -- out of scope per the executor's scope boundary (pre-existing failures unrelated to onboarding/adaptations/calendar_sync). Not fixed here.

## Threat Flags

None -- no new network endpoints, auth paths, or schema changes were introduced. The trust-boundary and STRIDE items already declared in 07-02-PLAN.md's `<threat_model>` (T-07-02-01/02/03) are the complete set; T-07-02-01 (DoS via hanging Calendar call) is mitigated by the new `CALENDAR_API_TIMEOUT_SECS` bound.

## Self-Check: PASSED

- `backend/routes/onboarding.py` -- FOUND, modified as described.
- `backend/routes/adaptations.py` -- FOUND, modified as described.
- `backend/calendar_sync.py` -- FOUND, modified as described.
- `tests/api/test_onboarding.py` -- FOUND, new test present and passing.
- `tests/api/test_adaptations.py` -- FOUND, two new tests present and passing.
- Commit `d5dba15` (test: RED tests) -- FOUND in `git log --oneline`.
- Commit `5158051` (feat: inline-await conversion) -- FOUND in `git log --oneline`.
