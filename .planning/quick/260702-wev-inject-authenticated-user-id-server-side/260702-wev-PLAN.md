---
phase: quick-260702-wev
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/agent/tools.py
  - backend/agent/loop.py
  - backend/routes/_sse.py
  - backend/routes/onboarding.py
  - backend/routes/chat.py
  - tests/agent/test_loop.py
autonomous: true
requirements: [AUTH-04]
must_haves:
  truths:
    - "The save_profile and generate_plan Anthropic tool schemas no longer declare user_id — the LLM is never shown or asked for it"
    - "run_turn(..., user_id='<uuid>') -> dispatch_tool -> save_profile/generate_plan: the real function receives user_id='<uuid>', overriding any LLM-supplied value"
    - "When user_id is None (existing callers/tests that omit it), dispatch behavior is byte-for-byte unchanged (backward compatible)"
    - "onboarding_start and chat_stream pass the authenticated current_user['user_id'] into sse_generator"
    - "Full backend suite still shows exactly the same 9 pre-existing failures — zero NEW failures introduced by this change"
  artifacts:
    - backend/agent/tools.py
    - backend/agent/loop.py
    - backend/routes/_sse.py
    - backend/routes/onboarding.py
    - backend/routes/chat.py
    - tests/agent/test_loop.py
  key_links:
    - "dispatch_tool allowlist {save_profile, generate_plan} + inputs = {**inputs, 'user_id': user_id} — authenticated value always wins"
    - "run_turn threads user_id into the single asyncio.gather dispatch_tool call site"
    - "sse_generator threads user_id into the fn(...) kwargs following the existing system_prompt conditional-kwargs pattern"
    - "onboarding.py line 233 user_id and chat.py line 91 user_id are already in scope at each sse_generator call"
---

<objective>
Inject the authenticated user_id server-side into save_profile and generate_plan tool calls instead of trusting LLM-supplied values. Remove user_id from both tools' Anthropic schemas so the LLM never sees or supplies it, then thread the JWT-resolved user_id from the route handlers (onboarding_start, chat_stream) through sse_generator -> run_turn -> dispatch_tool, which injects it into the tool inputs immediately before the real function is called.

Purpose: Live Playwright E2E + source inspection confirmed save_profile and generate_plan declare "user_id" as a REQUIRED LLM-supplied string. The LLM is never told the real user UUID anywhere, so it guesses placeholders ("new_user", "user_001", random UUIDs) that fail Postgres uuid-syntax or the profiles_user_id_fkey foreign key on every run. Result: no onboarding profile has ever persisted in production. This is an identity/authorization bug — the server, not the model, must decide whose profile is written.

Output: A surgical 5-file server-side injection with one new end-to-end regression test in tests/agent/test_loop.py proving injection through the full run_turn -> dispatch_tool chain.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
</execution_context>

<context>
@backend/agent/tools.py
@backend/agent/loop.py
@backend/routes/_sse.py
@backend/routes/onboarding.py
@backend/routes/chat.py
@tests/agent/test_loop.py
@tests/agent/conftest.py

Key facts already established by planning analysis (do not re-derive):
- Exactly two schemas in TOOL_SCHEMAS declare a user_id property: save_profile (property at ~lines 270-273, "user_id" in the required list at ~line 306) and generate_plan (property at ~lines 328-331, "user_id" in the required list at ~line 363). No other tool has user_id. Removing a property does NOT change len(TOOL_SCHEMAS) (still 10) or the schema-name set, so the TRUST-02 import-time invariant and test_tools_phase3.py's count/name-parity assertions still hold.
- save_profile (backend/sports_science/profile.py line 47) and generate_plan (backend/sports_science/plan.py line 176) both have a parameter literally named user_id — the injection key matches exactly. Do NOT change these two function signatures.
- dispatch_tool (backend/agent/tools.py ~line 410) currently is `async def dispatch_tool(tool_use_block, audit_log)` and calls `fn(**inputs)` where `inputs = tool_use_block.input` (LLM's raw args). It has both an async branch (await fn) and a sync-in-thread branch (asyncio.to_thread) — the injected inputs must feed BOTH branches.
- run_turn (backend/agent/loop.py line 46) has ONE dispatch_tool call site: inside `asyncio.gather(*[dispatch_tool(b, audit_log) for b in unique_blocks])` at ~lines 204-206.
- sse_generator (backend/routes/_sse.py line 34) already uses a conditional-kwargs pattern: `kwargs = {}; if system_prompt is not None: kwargs["system"] = system_prompt` then `fn(messages, client, model, scan_buffer, audit_log, **kwargs)` at ~line 83. Mirror that pattern for user_id.
- onboarding_start already has `user_id = current_user["user_id"]` (line 233) in scope at its sse_generator(...) call (~lines 270-276). chat_stream already has `user_id = current_user["user_id"]` (line 91) in scope at its sse_generator(...) call (~line 110). These are the ONLY sse_generator call sites in each file — do NOT touch onboarding_plan_calendar_sync or create_chat_conversation.
- No existing test asserts the schemas' "required" list contents, and no existing test calls dispatch_tool(...) directly with a user_id already in its constructed inputs — verified by grep. Existing save_profile/generate_plan tests call those functions directly with user_id= as a kwarg (unaffected). test_sse.py's user_id query params are unrelated to the tool-schema user_id.
- Baseline (verified this session, `.venv/bin/python -m pytest tests/ -q`): 9 failed, 211 passed. The 9 failures are 8 in tests/agent/test_sse.py::TestSSEEventSequence (test_sse_content_type, test_sse_frame_format, test_sse_event_ordering_text_only, test_sse_event_ordering_with_tools, test_sse_token_data_has_text_field, test_sse_done_data_is_empty_object, test_sse_no_live_anthropic_call, test_sse_requires_conversation_id) + 1 in tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields. These are pre-existing and OUT OF SCOPE — do not fix them, only confirm the failure set is unchanged.
- Do NOT touch: PHYSIO_PATTERN/trust.py, MAX_RETRIES/MAX_TOOL_TURNS, retry/violation handling, dedup logic (seen_calls/dedup_key), any other tool's schema, conftest.py fixtures (add new tests only).
</context>

<tasks>

<task type="auto">
  <name>Task 1: Remove user_id from save_profile/generate_plan schemas and inject it in dispatch_tool (backend/agent/tools.py)</name>
  <files>backend/agent/tools.py</files>
  <action>
Two edits in TOOL_SCHEMAS: (1) In the save_profile entry, delete the `"user_id": {...}` property block from `input_schema.properties` AND remove the `"user_id"` string from its `required` list. (2) In the generate_plan entry, delete the `"user_id": {...}` property block from `input_schema.properties` AND remove the `"user_id"` string from its `required` list. Leave every other property and required entry in both schemas untouched. Do not modify any other tool schema.

Then modify dispatch_tool: change the signature to `async def dispatch_tool(tool_use_block, audit_log: list, user_id: str | None = None) -> dict`. Immediately after `inputs = tool_use_block.input` (and before the `fn is None` check is fine, but it must be before both fn(**inputs) branches), add server-side injection: if `user_id is not None` and `name in {"save_profile", "generate_plan"}`, rebind `inputs = {**inputs, "user_id": user_id}` — build a NEW dict, do not mutate tool_use_block.input in place. This makes the authenticated value always win over any LLM-supplied value. When user_id is None, inputs is left exactly as-is so existing callers/tests are unaffected. The explicit two-name allowlist is required: those are the only TOOL_REGISTRY functions with a user_id parameter, and injecting into any other tool would raise an unexpected-keyword TypeError.

Update the dispatch_tool docstring with one line noting the server-side user_id injection and the allowlist. Do not change the injection to touch dedup_key/seen_calls (dedup happens in loop.py on the raw block before dispatch — leave it).
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/agent/test_tools_phase3.py -q</automated>
  </verify>
  <done>test_tools_phase3.py passes (len==10 and name parity intact). `grep -n 'User UUID' backend/agent/tools.py` returns nothing (both user_id schema properties removed). dispatch_tool signature has a `user_id: str | None = None` third parameter and injects `{**inputs, "user_id": user_id}` only for the two allowlisted names.</done>
</task>

<task type="auto">
  <name>Task 2: Thread user_id through run_turn and sse_generator (backend/agent/loop.py, backend/routes/_sse.py)</name>
  <files>backend/agent/loop.py, backend/routes/_sse.py</files>
  <action>
loop.py: add `user_id: str | None = None` as a trailing keyword parameter to run_turn's signature (place it after `system: str = SYSTEM_PROMPT`). Change the single dispatch_tool call site inside asyncio.gather (~lines 204-206) from `dispatch_tool(b, audit_log)` to `dispatch_tool(b, audit_log, user_id=user_id)`. Add a one-line docstring note under the Args section that user_id, when provided, is injected server-side into save_profile/generate_plan tool calls. Do not touch any other logic in run_turn.

_sse.py: add `user_id: str | None = None` to sse_generator's signature (after assistant_sink). Thread it into the fn(...) call by following the file's existing conditional-kwargs pattern: after the existing `if system_prompt is not None: kwargs["system"] = system_prompt`, add `if user_id is not None: kwargs["user_id"] = user_id`. The existing `fn(messages, client, model, scan_buffer, audit_log, **kwargs)` call then forwards it. Add a one-line note to the docstring Args describing user_id. Do not change the client instantiation, audit_log, assistant_sink accumulation, or error handling.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/agent/test_loop.py tests/agent/test_sse.py -q</automated>
  </verify>
  <done>test_loop.py fully passes. test_sse.py shows the SAME 8 pre-existing TestSSEEventSequence failures and no others (they are unrelated to this change). run_turn accepts user_id and forwards it to dispatch_tool; sse_generator accepts user_id and only adds it to kwargs when not None.</done>
</task>

<task type="auto">
  <name>Task 3: Pass authenticated user_id into sse_generator at both route call sites (backend/routes/onboarding.py, backend/routes/chat.py)</name>
  <files>backend/routes/onboarding.py, backend/routes/chat.py</files>
  <action>
onboarding.py: in onboarding_start's `_stream_with_metadata` inner generator, add `user_id=user_id` to the existing sse_generator(...) call (~lines 270-276). The `user_id` local (from line 233 `user_id = current_user["user_id"]`) is already in scope via closure. Do not touch onboarding_plan_calendar_sync.

chat.py: in chat_stream's `_stream_and_persist` inner generator, add `user_id=user_id` to the existing sse_generator(...) call (~line 110). The `user_id` local (from line 91) is already in scope via closure. Do not touch create_chat_conversation.

These are the ONLY two sse_generator call sites across both files. Make no other changes.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/api/test_onboarding.py -q</automated>
  </verify>
  <done>test_onboarding.py passes. Both sse_generator call sites now pass user_id=user_id (grep confirms). The separate onboarding_plan_calendar_sync and create_chat_conversation handlers are untouched.</done>
</task>

<task type="auto">
  <name>Task 4: Add end-to-end injection regression test to tests/agent/test_loop.py and confirm the baseline failure set is unchanged</name>
  <files>tests/agent/test_loop.py</files>
  <action>
Add ONE new async test to tests/agent/test_loop.py named `test_user_id_injected_server_side_through_run_turn`. It must prove injection through the FULL run_turn -> dispatch_tool chain (not by calling dispatch_tool directly). Follow the existing patterns in this file: import from tests.agent.conftest (build_fake_client, _build_stream, _tool_block, _final_msg) and use unittest.mock (already imported at top: AsyncMock, MagicMock, patch).

Build the streams:
- Round 1: a tool_use stream whose final_msg content is a single _tool_block calling "save_profile" with inputs that do NOT include user_id (matching the post-fix schema the LLM sees), e.g. inputs `{"fitness_goals": "weight loss", "weekly_hours": 3.0, "preferred_days": ["Tuesday"], "back_status": "none", "equipment": {}, "rpe_baseline": "beginner"}`.
- Round 2: an end_turn stream (`_final_msg(stop_reason="end_turn", content=[])`) so run_turn terminates after the tool round.
- `client = build_fake_client(round1_stream, round2_stream)`.

Intercept the real registry function: patch backend.agent.tools.TOOL_REGISTRY's "save_profile" entry with a mock so no real Supabase call happens and the actual call kwargs can be inspected. Use `unittest.mock.patch.dict("backend.agent.tools.TOOL_REGISTRY", {"save_profile": fake_save_profile})`. The replacement must return a ToolResult-shaped object because dispatch_tool calls `result.model_dump()` and `result.to_tool_response()` — configure a MagicMock return value whose `.model_dump()` returns a plain dict (e.g. `{"saved": True}`) and whose `.to_tool_response()` returns a JSON-serializable dict (e.g. `{"saved": True}`). A synchronous MagicMock is fine (dispatch_tool routes non-coroutine functions through asyncio.to_thread); if using AsyncMock instead, that also works via the coroutine branch — either is acceptable, match whichever is simplest.

Drive the loop: `events = [ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log, user_id="11111111-1111-1111-1111-111111111111")]` (use the no_op_scanner fixture and an empty audit_log list; pass a realistic UUID string). Assert:
1. The fake save_profile mock was called exactly once.
2. Its received keyword arguments include `user_id == "11111111-1111-1111-1111-111111111111"` (inspect `mock.call_args.kwargs["user_id"]`). This proves the authenticated value was injected server-side even though the tool_use block never supplied user_id.
3. The original non-user_id inputs still arrived (e.g. `mock.call_args.kwargs["back_status"] == "none"`), proving injection augments rather than replaces the LLM args.

Write a docstring referencing this task (260702-wev) and stating it proves server-side user_id injection through run_turn -> dispatch_tool, closing the identity bug where the LLM guessed placeholder UUIDs. Do not modify any existing test or conftest fixture.
  </action>
  <verify>
    <automated>.venv/bin/python -m pytest tests/agent/test_loop.py -q</automated>
  </verify>
  <done>The new test_user_id_injected_server_side_through_run_turn passes, and every other test in test_loop.py still passes. The assertion inspects the real registry function's actual call kwargs and confirms user_id == the passed UUID.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| LLM tool-call args -> backend persistence | Untrusted, model-generated tool inputs cross into DB writes (save_profile/generate_plan) |
| JWT current_user -> tool execution | The authenticated identity (JWT sub) must be the sole authority for whose profile/plan is written |

## STRIDE Threat Register

| Threat ID | Category | Component | Severity | Disposition | Mitigation Plan |
|-----------|----------|-----------|----------|-------------|-----------------|
| T-wev-01 | Spoofing / Elevation | dispatch_tool save_profile/generate_plan user_id | high | mitigate | Remove user_id from LLM schema; inject JWT-resolved user_id server-side so the model cannot select or spoof a target user. The authenticated value always overrides any inputs value (this fix). |
| T-wev-02 | Tampering | inputs dict mutation | low | mitigate | Build a new inputs dict (`{**inputs, "user_id": user_id}`) rather than mutating tool_use_block.input in place, avoiding side effects on dedup/audit that read the original block. |
| T-wev-03 | Elevation | injection allowlist | medium | mitigate | Restrict injection to the explicit two-name allowlist {save_profile, generate_plan}; injecting user_id into any other tool would raise TypeError and could mask a bug. |
</threat_model>

<verification>
Run the full backend suite and diff the failure set against the recorded baseline (9 failed / 211 passed):

```
.venv/bin/python -m pytest tests/ -q
```

Confirm the summary is exactly `9 failed, N passed` with the SAME 9 failing test IDs as the baseline (8 in tests/agent/test_sse.py::TestSSEEventSequence + 1 in tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields), and passed count increased by exactly 1 (the new regression test) to 212. If the failure count or any failing test IDENTITY changed — i.e. any NEW failure appears — STOP and investigate before committing; do not commit a change that adds a failure.
</verification>

<success_criteria>
- user_id removed from both save_profile and generate_plan input schemas (property + required); `grep 'User UUID' backend/agent/tools.py` is empty.
- dispatch_tool injects the authenticated user_id for the two allowlisted tools only, via a new dict, and is a no-op when user_id is None.
- run_turn, sse_generator, onboarding_start, and chat_stream thread the JWT user_id end-to-end.
- New test_loop.py regression test proves user_id reaches the real save_profile function through run_turn -> dispatch_tool.
- Full suite: exactly the 9 pre-existing failures remain, 212 passed (baseline 211 + 1 new test). Zero NEW failures.
- Only the 5 source files + tests/agent/test_loop.py are staged/committed; unrelated working-tree changes are left untouched. Direct push to main (pre-approved).
</success_criteria>

<output>
Create `.planning/quick/260702-wev-inject-authenticated-user-id-server-side/260702-wev-SUMMARY.md` when done.
</output>
