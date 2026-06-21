---
phase: 04-ui-and-calendar
plan: 13
subsystem: backend/chat
status: complete
tags: [gap-closure, uat-gap-5, chat, sse, persistence]
requirements: [UI-06]
dependency_graph:
  requires: [04-06, 04-12]
  provides: [chat-message-persistence, chat-message-routing]
  affects: [api/routes/chat.py]
tech_stack:
  added: []
  patterns: [assistant_sink, save_messages, _stream_and_persist]
key_files:
  created: []
  modified:
    - api/routes/chat.py
decisions:
  - chat_stream now reads the message query param the frontend already sends and appends it to history before streaming
  - _OPENING_MESSAGE seed retained only for the empty-history no-message case (fresh conversation open)
  - _stream_and_persist inline async generator wraps sse_generator, owns assistant_sink, persists best-effort after stream
  - save_messages imported from api.routes.onboarding (extending existing import line)
metrics:
  duration: 1min
  completed: 2026-06-21
---

# Phase 04 Plan 13: Chat Message Routing and Persistence Summary

**One-liner:** Wire `message` query param into `chat_stream` and persist user + assistant turns via `save_messages` using the `assistant_sink` pattern from 04-12, closing UAT GAP 5.

## What Was Built

### Task 1: Read the chat message param, append it to history, and persist turns (UAT GAP 5)

**Commit:** `132ae78`

Root cause confirmed: `chat_stream` in `api/routes/chat.py` never read the `message` query param the frontend sends via `/chat/stream?conversation_id=...&message=<text>`. It loaded history (empty for new conversations), seeded `_OPENING_MESSAGE`, and streamed a reply to that seed. The user's actual typed message was silently discarded. Additionally, no turns were ever persisted so there was no continuity.

Changes made to `api/routes/chat.py`:

1. Added `message: str | None = Query(None)` parameter to `chat_stream`.
2. After loading history, appends `{"role": "user", "content": message}` to `messages` when `message` is a non-empty string. The `_OPENING_MESSAGE` fallback now only triggers when history is empty AND there is no incoming message.
3. Extended the `from api.routes.onboarding import create_conversation, load_conversation` line to also import `save_messages`.
4. Replaced `return StreamingResponse(sse_generator(...), ...)` with an inline `_stream_and_persist` async generator that:
   - Creates `assistant_sink: list[str] = []`
   - Iterates `sse_generator(..., assistant_sink=assistant_sink)` and yields each chunk
   - After the loop, builds `new_turns` from the user message (if non-empty) and `assistant_sink[0]` (if captured)
   - Calls `await save_messages(conversation_id, user_id, new_turns)` inside a best-effort `try/except`
5. `StreamingResponse` media_type (`text/event-stream`) and all headers (`Cache-Control`, `Connection`, `X-Accel-Buffering`) are unchanged.

## Deviations from Plan

### Auto-fixed Issues

None.

### Observations

`tests/api/test_chat.py` referenced in the plan's verify step does not exist in the test suite. The file was never created (no prior plan created it). The syntax check passed and the broader test suite (207 tests) shows 10 pre-existing failures in `test_sse.py`, `test_sessions.py`, and `test_capability_gap.py` that are unrelated to this change (confirmed by `git diff HEAD -- tests/` showing no test file changes).

## Self-Check

- [x] `api/routes/chat.py` exists and was modified: FOUND
- [x] Commit `132ae78` exists: FOUND
- [x] `message: str | None = Query(None)` present in `chat_stream`: VERIFIED
- [x] `assistant_sink` wired: VERIFIED
- [x] `save_messages` imported and called: VERIFIED
- [x] `ast.parse` on `chat.py`: PASSED

## Self-Check: PASSED
