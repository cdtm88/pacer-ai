---
phase: 04-ui-and-calendar
plan: 19
subsystem: backend-api
tags: [gap-closure, uat-gap-3, uat-gap-6, sessions, onboarding, supabase-py]
dependency_graph:
  requires: []
  provides: [working-mark-done, confirmed-onboarding-persistence]
  affects: [frontend/src/lib/api.ts, api/routes/sessions.py, api/routes/onboarding.py]
tech_stack:
  added: []
  patterns: [supabase-py-select-on-update]
key_files:
  created: []
  modified:
    - api/routes/sessions.py
decisions:
  - "Added .select(_SESSION_COLUMNS) to update_session query chain — mirrors the pattern already used by all GET handlers in the same file (lines 69, 104, 306)"
  - "onboarding.py verified unchanged — save_messages call path is intact from 04-12; no re-implementation needed"
metrics:
  duration: "4 minutes"
  completed: "2026-06-21"
  tasks_completed: 2
  tasks_total: 2
status: complete
requirements: [UI-02, ONBD-01]
---

# Phase 04 Plan 19: UAT GAP 3 + GAP 6 Closure Summary

PATCH /sessions/{id} now returns the updated row so Mark Done succeeds; onboarding save_messages persistence confirmed intact from 04-12.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Add select(_SESSION_COLUMNS) to update_session PATCH handler | d423c09 | api/routes/sessions.py |
| 2 | Verify onboarding save_messages persistence path (GAP 6 confirmation) | n/a (no changes) | api/routes/onboarding.py |

## What Was Built

**Task 1 (UAT GAP 3):** The `update_session` handler in `api/routes/sessions.py` was missing `.select(_SESSION_COLUMNS)` before `.execute()`. The supabase-py client returns `data=[]` for any `.update()` call without a `.select()` — so the handler's `if not result.data: raise HTTPException(404, ...)` guard fired on every successful update. The frontend received a 404, re-enabled the "Mark Done" button, and the session appeared to never update (even though the row was actually changed in the DB).

Fix: inserted `.select(_SESSION_COLUMNS)` into the query chain after the two `.eq()` ownership filters, before `.execute()`. This mirrors the exact pattern already used by the GET handlers at lines 69, 104, and 306 of the same file. Now a successful PATCH returns the updated row in `result.data`, the 200 flows to the frontend, and the card refreshes correctly.

The ownership filter `.eq("user_id", user_id)` and the 404 guard are unchanged. When no row matches (non-existent ID or another user's session), `result.data` is still `[]` and the 404 fires correctly — IDOR protection T-04-03 is preserved.

**Task 2 (UAT GAP 6 confirmation):** Read `api/routes/onboarding.py` to confirm the save_messages persistence path introduced in 04-12 is still present. All three conditions confirmed:

1. `save_messages` is **defined** at lines 148-173: INSERTs `{conversation_id, user_id, role, content}` rows; returns early on empty input.
2. `save_messages` is **called** after the stream completes in `_stream_with_metadata` at lines 279-291: captures the incoming `body.message` (when non-empty) and the assistant reply from `assistant_sink` (when non-empty), builds `new_turns`, then calls `save_messages(conversation_id, user_id, new_turns)` inside a best-effort `try/except`.
3. `load_conversation` is **called** at line 253 before the agent run: prior persisted turns are reloaded on every request, which is what prevents the opening-question loop.

No changes made to `onboarding.py`. GAP 6 was already closed by 04-12 and has not regressed.

## Deviations from Plan

None. Plan executed exactly as written.

## Test Results

- `tests/api/test_sessions.py`: 13 passed (all passing before and after the fix)
- `tests/api/test_onboarding.py`: 4 passed

## Known Stubs

None.

## Threat Flags

None. No new network endpoints, auth paths, file access patterns, or schema changes introduced.

## Self-Check: PASSED

- `api/routes/sessions.py` modified and committed (d423c09)
- Both test suites pass
- `onboarding.py` unchanged; persistence path confirmed at exact line numbers
- SUMMARY.md written to `.planning/phases/04-ui-and-calendar/04-19-SUMMARY.md`
