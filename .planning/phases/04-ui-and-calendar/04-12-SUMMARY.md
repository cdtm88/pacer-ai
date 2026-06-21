---
phase: 04-ui-and-calendar
plan: 12
subsystem: onboarding
status: complete
tags: [gap-closure, persistence, sse, onboarding, uat-gap-6]
completed_date: "2026-06-21"
duration: 2min
tasks_completed: 2
files_modified: 2
requirements: [UI-01]

dependency_graph:
  requires: [04-06, 04-09]
  provides: [onboarding-conversation-persistence]
  affects: [onboarding-interview-progression]

tech_stack:
  patterns:
    - async generator sink pattern (list passed by reference to collect streamed output)
    - best-effort persistence in async generator (try/except after yield loop)

key_files:
  modified:
    - api/routes/_sse.py
    - api/routes/onboarding.py

decisions:
  - assistant_sink as list parameter: async generators cannot return values; a mutable list sink is the cleanest way to pass the accumulated text back to the caller without altering any yielded frame
  - best-effort save_messages: persistence after an already-completed stream must never surface errors to the client; try/except swallows all DB failures

key_decisions:
  - assistant_sink list pattern for async generator output without altering SSE frames
  - best-effort save_messages in _stream_with_metadata to protect completed stream

metrics:
  duration: 2min
  tasks: 2
  files: 2
---

# Phase 04 Plan 12: Onboarding Conversation Persistence (UAT GAP 6) Summary

**One-liner:** Wire `save_messages` into the onboarding stream via an `assistant_sink` list so each turn persists real user and assistant messages, ending the interview loop.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add assistant_sink output parameter to sse_generator | 93ece4c | api/routes/_sse.py |
| 2 | Persist user and assistant turns after each onboarding stream (UAT GAP 6) | 7885d65 | api/routes/onboarding.py |

## What Was Built

**Task 1 — `_sse.py`:** Added an optional `assistant_sink: list | None = None` parameter to `sse_generator`. While iterating events from `run_turn`, text from every `"token"` event is appended to a local `accumulated_text` string. After the `async for` loop completes normally, `assistant_sink.append(accumulated_text)` is called once if the sink is provided. On the exception path (where an `event: error` frame is emitted), nothing is appended. Existing callers (`chat.py`) that do not pass `assistant_sink` are completely unaffected.

**Task 2 — `onboarding.py`:** Inside `_stream_with_metadata`, a local `assistant_sink: list[str] = []` is created before the `sse_generator` call and passed in. After the `async for chunk in sse_generator(...)` loop completes (all frames yielded to the client), the code builds `new_turns`: the incoming `body.message` (when non-empty) as a `user` turn and `assistant_sink[0]` (when non-empty) as an `assistant` turn. When `conversation_id` is set and `new_turns` is non-empty, `await save_messages(conversation_id, user_id, new_turns)` is called. The entire block is wrapped in a `try/except Exception: pass` so no DB failure can surface on the already-completed stream. The hardcoded seed message opener is never persisted as a user turn.

## Root Cause Resolved

UAT GAP 6 diagnosis: `save_messages` was defined in `onboarding.py` but never called. Every turn, `load_conversation` returned an empty (or unchanged) history, so the agent always re-seeded from the opening message and re-asked "What are your main fitness goals?" regardless of prior answers.

Fix: after each stream, real turns are persisted. The next turn's `load_conversation` returns genuine prior context, and the interview progresses through all 6 fields.

## Verification

```
.venv/bin/pytest tests/api/test_onboarding.py -q
4 passed in 1.51s

.venv/bin/python -c "import ast; ast.parse(open('api/routes/_sse.py').read()); print('parse ok')"
parse ok

.venv/bin/python -c "import ast; ast.parse(open('api/routes/onboarding.py').read()); print('parse ok')"
parse ok
```

Note: `tests/agent/test_sse.py` has 8 pre-existing failures (401 Unauthorized — tests hit the `/chat/stream` endpoint without JWT headers added in Phase 04 auth work). These failures exist on the main branch before this plan and are not caused by this plan's changes.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Threat Flags

None — changes are internal to the onboarding stream's post-stream persistence path. No new network endpoints, auth paths, or schema changes introduced.

## Self-Check: PASSED

- `api/routes/_sse.py` exists and contains `assistant_sink`: confirmed
- `api/routes/onboarding.py` exists and contains `await save_messages(`: confirmed
- Commit 93ece4c exists in git log: confirmed
- Commit 7885d65 exists in git log: confirmed
- All 4 `test_onboarding.py` tests pass: confirmed
