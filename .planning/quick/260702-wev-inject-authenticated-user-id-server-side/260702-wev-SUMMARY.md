---
phase: quick-260702-wev
plan: 01
subsystem: auth
tags: [identity, authorization, tool-schema, save_profile, generate_plan]

requires:
  - phase: quick-260702-w52
    provides: "Multi-round trust attribution working correctly"
provides:
  - "Server-side user_id injection for save_profile and generate_plan, replacing LLM-guessed placeholder UUIDs"
affects: [onboarding, chat, profiles, plans]

tech-stack:
  added: []
  patterns:
    - "Sensitive identity parameters removed from LLM-facing tool schemas entirely; injected server-side by the dispatcher from the authenticated JWT, with an explicit allowlist of which tools receive the injection"

key-files:
  created: []
  modified:
    - backend/agent/tools.py
    - backend/agent/loop.py
    - backend/routes/_sse.py
    - backend/routes/onboarding.py
    - backend/routes/chat.py
    - tests/agent/test_loop.py

key-decisions:
  - "Removed user_id from the LLM-facing tool schemas entirely rather than just overriding a supplied value -- the LLM should never be asked for or shown an identity-critical parameter it cannot reliably know"
  - "Used an explicit two-name allowlist ({save_profile, generate_plan}) in dispatch_tool for the injection, rather than a generic 'inject into inputs if user_id key exists' check -- avoids accidentally injecting into a tool whose function doesn't accept a user_id kwarg"
  - "Built a new inputs dict ({**inputs, user_id: ...}) rather than mutating tool_use_block.input in place, to avoid side effects on dedup_key/audit_log which read the original block"
  - "Also fixed backend/routes/chat.py's identical latent vulnerability even though the regular coaching chat path wasn't live-tested this session -- same sse_generator/run_turn/dispatch_tool chain, same bug"

patterns-established:
  - "Identity-critical values (user_id) flow from the authenticated JWT through the route handler -> sse_generator -> run_turn -> dispatch_tool chain as explicit parameters, never as LLM tool-call arguments"

requirements-completed: [AUTH-04]

coverage:
  - id: D1
    description: "save_profile and generate_plan tool schemas no longer declare user_id -- the LLM is never shown or asked for it"
    requirement: "AUTH-04"
    verification:
      - kind: unit
        ref: "grep 'User UUID' backend/agent/tools.py (empty) + tests/agent/test_tools_phase3.py (8 passed)"
        status: pass
    human_judgment: false
  - id: D2
    description: "run_turn(..., user_id=X) -> dispatch_tool -> save_profile: the real function receives user_id=X, overriding any LLM-supplied value"
    requirement: "AUTH-04"
    verification:
      - kind: unit
        ref: "tests/agent/test_loop.py::test_user_id_injected_server_side_through_run_turn"
        status: pass
    human_judgment: false
  - id: D3
    description: "onboarding_start and chat_stream pass the authenticated current_user['user_id'] into sse_generator"
    requirement: "AUTH-04"
    verification:
      - kind: unit
        ref: "tests/api/test_onboarding.py (4 passed); manual grep confirms both sse_generator call sites pass user_id=user_id"
        status: pass
    human_judgment: false
  - id: D4
    description: "Full backend suite shows exactly the same 9 pre-existing failures, zero new failures"
    requirement: "AUTH-04"
    verification:
      - kind: unit
        ref: "pytest tests/ -q -- 9 failed (unchanged identities), 212 passed (baseline 211 + 1 new test)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A real onboarding conversation results in an actually-persisted profiles row and plans row in production"
    requirement: "AUTH-04"
    verification: []
    human_judgment: true
    rationale: "Not driven from within this executor (no browser/live-URL/production-DB access per plan constraints) -- confirmed separately via the ongoing Playwright E2E test session after this deploy."

duration: 20min
completed: 2026-07-02
status: complete
---

# Quick Task 260702-wev: Inject authenticated user_id server-side Summary

**Removed `user_id` from the LLM-facing `save_profile`/`generate_plan` tool schemas and threaded the JWT-resolved authenticated user ID from the route handlers through `sse_generator` → `run_turn` → `dispatch_tool`, which now injects it server-side — closing the reason no onboarding profile has ever been persisted in production.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 4/4 complete
- **Files modified:** 6

## Accomplishments
- Diagnosed via live Playwright E2E testing: after 260702-w52's fix resolved the "Connection lost" trust-scanner issue, `save_profile` still failed on every attempt with Postgres uuid-syntax or foreign-key errors, because the LLM was guessing placeholder `user_id` values (`"new_user"`, `"user_001"`, random UUIDs) — the tool schema required it as an LLM-supplied argument, and the LLM had no way to know the real value.
- Removed `user_id` entirely from both `save_profile`'s and `generate_plan`'s Anthropic tool schemas (`backend/agent/tools.py`).
- `dispatch_tool(tool_use_block, audit_log, user_id=None)` now injects the authenticated `user_id` into `inputs` for an explicit `{"save_profile", "generate_plan"}` allowlist, always overriding any LLM-supplied value, via a new dict (not in-place mutation).
- Threaded `user_id` through `run_turn` (one `dispatch_tool` call site) and `sse_generator` (following its existing conditional-kwargs pattern).
- Updated both real call sites — `onboarding.py`'s `onboarding_start` and `chat.py`'s `chat_stream` — to pass `user_id=user_id` (the authenticated value already in scope from `current_user["user_id"]`).
- Also fixed the identical latent vulnerability in the regular coaching chat path (`chat.py`), not just onboarding — same shared code path, same bug, even though it wasn't live-tested this session.
- New regression test (`test_user_id_injected_server_side_through_run_turn`) proves the injection end-to-end: builds a `save_profile` tool_use block with no `user_id` in its inputs (matching the post-fix schema), patches the real `TOOL_REGISTRY["save_profile"]`, drives it through `run_turn`, and asserts the actual function call received the injected UUID while still receiving the LLM's other arguments.
- Full verification: `test_tools_phase3.py`, `test_loop.py` (10 tests), `test_onboarding.py` all pass. Full suite: `9 failed, 212 passed` — same 9 pre-existing failure identities as the documented baseline (211 passed), +1 for the new test, zero new failures.
- Committed and pushed to `origin/main` (`b3fcf39`), auto-deploying the Vercel Python function.

## Task Commits

1. **Task 1: Remove user_id from schemas + inject in dispatch_tool** - included in `b3fcf39`
2. **Task 2: Thread user_id through run_turn + sse_generator** - included in `b3fcf39`
3. **Task 3: Pass user_id at both route call sites** - included in `b3fcf39`
4. **Task 4: Regression test + full verification** - `b3fcf39` (fix)

## Files Created/Modified
- `backend/agent/tools.py` - removed `user_id` from 2 tool schemas; `dispatch_tool` injects it for an allowlist of 2 tool names
- `backend/agent/loop.py` - `run_turn` accepts and forwards `user_id`
- `backend/routes/_sse.py` - `sse_generator` accepts and forwards `user_id`
- `backend/routes/onboarding.py` - `onboarding_start` passes `user_id=user_id`
- `backend/routes/chat.py` - `chat_stream` passes `user_id=user_id`
- `tests/agent/test_loop.py` - new end-to-end injection regression test

## Decisions Made
- Removed `user_id` from the schemas entirely rather than just overriding whatever the LLM supplied — an identity-critical value should never be an LLM-controlled input in the first place, this is a spoofing/elevation risk class, not just a bug.
- Explicit two-tool allowlist in `dispatch_tool`, not a generic "inject if key present" check — prevents accidentally passing `user_id` to a tool function that doesn't accept it.
- Built a new `inputs` dict rather than mutating `tool_use_block.input` — avoids unintended side effects on dedup/audit logic that reads the original block.

## Deviations from Plan
None — plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None.

## Next Phase Readiness
- This is the fourth fix in the chain (after 260702-vsp, 260702-vs6, 260702-w52) needed to get a real, persisted onboarding completion working in production. Combined, all four should allow a full signup → onboarding → confirm → saved profile → generated plan flow to complete end-to-end for the first time. Live confirmation is happening via the ongoing Playwright E2E test session.

---
*Quick task: 260702-wev*
*Completed: 2026-07-02*
</content>
