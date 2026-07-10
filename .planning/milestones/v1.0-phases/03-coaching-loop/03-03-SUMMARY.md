---
phase: 03-coaching-loop
plan: "03"
subsystem: onboarding-endpoint, sse-generator, conversation-persistence
tags: [onboarding, sse, D-22, ONBD-01, ONBD-02, ONBD-03, ONBD-04, PLAN-06, TRANSP-01, DB-backed-chat]
dependency_graph:
  requires: [03-01, 03-02]
  provides: [api/routes/_sse.py, api/routes/onboarding.py, agent/loop.py@system-param, tests/api/test_onboarding.py@filled]
  affects: [03-04, 03-05]
tech_stack:
  added: []
  patterns: [dynamic-system-prompt-D22, pydantic-request-model, SSE-generator-extraction, DB-backed-conversation-load]
key_files:
  created:
    - api/routes/_sse.py
    - api/routes/onboarding.py
  modified:
    - agent/loop.py
    - api/routes/chat.py
    - api/main.py
    - tests/api/test_onboarding.py
decisions:
  - "sse_generator accepts _run_turn as an optional parameter so callers pass their own module-level run_turn reference; monkeypatch at chat_module.run_turn and onboarding_module.run_turn both remain effective"
  - "user_id: str = Body(...) rejected by FastAPI when client sends JSON object; changed to OnboardingStartRequest Pydantic model (Rule 1 fix)"
  - "onboarding_start wraps create_conversation in try/except best-effort so DB unavailability does not block SSE stream"
  - "chat.py Phase 3 upgrade: load_conversation replaces in-memory placeholder; fallback to opening message if DB empty"
  - "Phase 4 TODO placed in load_conversation docstring for token-count truncation (Open Question 5 deferral)"
metrics:
  duration: "6 minutes"
  completed: "2026-06-20"
  tasks_completed: 3
  files_created: 2
  files_modified: 4
status: complete
---

# Phase 03 Plan 03: Onboarding Endpoint and DB-backed Conversation Summary

**One-liner:** Shared `sse_generator` extracted to `_sse.py` with dynamic system prompt injection (D-22); `POST /onboarding/start` created with 6-field gated interview prompt; `run_turn` accepts `system` parameter; conversation load/save helpers added; chat.py upgraded to DB-backed message loading; all 4 onboarding tests filled and passing.

## What Was Built

### Task 1: Shared sse_generator and run_turn system parameter

**`api/routes/_sse.py`** (created):
- `sse_generator(messages, model, system_prompt=None, _run_turn=None)` extracted from `chat.py`
- `system_prompt=None` defaults to the existing SYSTEM_PROMPT constant via `run_turn`'s default parameter
- `_run_turn` parameter lets each calling module pass its own module-level `run_turn` reference so test monkeypatches remain effective (key architecture decision)
- Exception-to-error-frame handling preserved from original chat.py

**`agent/loop.py`** (modified):
- `run_turn` signature gains `system: str = SYSTEM_PROMPT` keyword parameter (D-22)
- `system=SYSTEM_PROMPT` inside `client.messages.stream(...)` replaced with `system=system`
- All existing callers and tests are unaffected (default value preserves behavior)

**`api/routes/chat.py`** (modified):
- Local `async def sse_generator` removed; imports from `api.routes._sse`
- `run_turn` kept as module-scope import, passed as `_run_turn=run_turn` to `sse_generator` so `chat_module.run_turn` monkeypatch in `test_sse.py` still works

### Task 2: POST /onboarding/start, conversation helpers, DB-backed chat

**`api/routes/onboarding.py`** (created, 250 lines):
- `ONBOARDING_SYSTEM_PROMPT`: names all 6 required interview fields (fitness_goals, weekly_hours, preferred_days, back_status, equipment, rpe_baseline); includes "Here is what I have" confirmation gate instruction; specifies D-08 tool order (save_profile then progress_load then calculate_hr_zones then generate_plan); includes TRUST-04 rule
- `_get_async_supabase()`: module-level singleton reusing capability_gap.py WR-04 pattern; SERVICE_ROLE_KEY bypasses RLS
- `create_conversation(user_id, context_type) -> str`: inserts conversations row, returns UUID
- `load_conversation(conversation_id, limit=20) -> list[dict]`: SELECT DESC LIMIT 20, reversed to chronological; Phase 4 token-truncation TODO documented
- `save_messages(conversation_id, user_id, new_messages)`: INSERT rows to messages table; handles non-string content via json.dumps
- `OnboardingStartRequest`: Pydantic model for JSON body (user_id field)
- `onboarding_start(request)`: creates conversation best-effort, returns `StreamingResponse(sse_generator(..., system_prompt=ONBOARDING_SYSTEM_PROMPT, _run_turn=run_turn))`

**`api/routes/chat.py`** (modified, Phase 3 upgrade):
- In-memory placeholder replaced with `load_conversation(conversation_id, limit=20)`
- Empty result falls back to hardcoded opening message
- `load_conversation` imported from `api.routes.onboarding`

**`api/main.py`** (modified):
- `onboarding_router` imported and mounted at `/onboarding` prefix with `tags=["onboarding"]`
- No rides or adaptations routers added (those are 03-04, 03-05)

### Task 3: Onboarding tests (Wave 2 stubs filled)

**`tests/api/test_onboarding.py`** (all 4 skips removed, fully implemented):
- `test_onboarding_returns_sse`: POST /onboarding/start with monkeypatched run_turn and _get_async_supabase; asserts 200 + text/event-stream + token frame + done frame (ONBD-01)
- `test_confirmation_gate`: drives two mock sequences (compliant: approval token before save_profile; non-compliant: save_profile without approval); asserts structural D-03 gate contract (ONBD-04); note in code that LLM adherence requires manual verification (03-VALIDATION manual-only row)
- `test_back_status_constraint`: calls save_profile directly with mocked Supabase capturing upsert payload; asserts constraints == {"back_issues": True, "load_ramp_flag_threshold_pct": 10} for back_status="moderate" (ONBD-02)
- `test_profile_persisted`: asserts upsert called on profiles table with on_conflict=user_id and result.value["saved"] is True (ONBD-03)

## Test Results

```
172 passed, 13 skipped, 2 warnings in 0.72s
```

4 new tests pass; 4 stubs removed from skip list. No regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] FastAPI Body(...) incompatible with JSON object body**
- **Found during:** Task 3 (test_onboarding_returns_sse returned 422)
- **Issue:** `user_id: str = Body(...)` expects a raw string body, but the client sends `{"user_id": "..."}` as a JSON object; FastAPI returns 422 "Input should be a valid string"
- **Fix:** Changed to `OnboardingStartRequest(BaseModel)` Pydantic model with `user_id: str` field; endpoint signature changed to `onboarding_start(request: OnboardingStartRequest)`
- **Files modified:** `api/routes/onboarding.py`
- **Commit:** a7b66b9

**2. [Rule 1 - Bug] Docstring misplaced after variable assignment**
- **Found during:** Task 3 review of onboarding.py
- **Issue:** Docstring for `onboarding_start` was placed after `user_id = request.user_id` due to edit ordering; Python treats it as a string literal, not a docstring
- **Fix:** Moved docstring to be first statement of function body; `user_id = request.user_id` moved below
- **Files modified:** `api/routes/onboarding.py`
- **Commit:** a7b66b9

## Threat Surface Scan

The plan's threat model covers all new surface introduced:
- `POST /onboarding/start` accepts untrusted `user_id` (T-03-07: accepted gap, documented)
- SSE output passes through `scan_buffer` trust scanner inherited from Phase 2 (T-03-08)
- conversation/message DB writes use SERVICE_ROLE_KEY via `_get_async_supabase` (T-03-09)
- `save_profile` inputs recorded in ToolResult.inputs for audit trail (T-03-10)

No new threat surface beyond the plan's threat model.

## Self-Check

### Files created/modified:
- /Users/christianmoore/ai/pacer-ai/api/routes/_sse.py: FOUND
- /Users/christianmoore/ai/pacer-ai/api/routes/onboarding.py: FOUND
- /Users/christianmoore/ai/pacer-ai/agent/loop.py: FOUND
- /Users/christianmoore/ai/pacer-ai/api/routes/chat.py: FOUND
- /Users/christianmoore/ai/pacer-ai/api/main.py: FOUND
- /Users/christianmoore/ai/pacer-ai/tests/api/test_onboarding.py: FOUND

### Commits:
- 0918ecb: feat(03-03): extract shared sse_generator with system_prompt param; add system param to run_turn (D-22)
- 840d0ee: feat(03-03): add POST /onboarding/start, conversation persistence helpers, DB-backed chat load
- a7b66b9: feat(03-03): fill in onboarding tests; fix Body->Pydantic model for JSON request (ONBD-01 through ONBD-04)

## Self-Check: PASSED
