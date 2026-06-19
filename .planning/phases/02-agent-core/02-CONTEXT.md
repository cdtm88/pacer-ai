# Phase 2: Agent Core - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the FastAPI backend application, the Anthropic agent loop (raw SDK), the tool registry wrapping Phase 1's sports-science functions as Anthropic tool schemas, SSE streaming to the frontend, and the trust-model enforcement layer (TRUST-03/04/05). The agent loop must provably never emit an unsourced physiological number, verified by a compliance test suite.

**In scope:** `agent/` (loop, tool registry, trust parser), `api/` (FastAPI app, SSE chat route), async Supabase upgrade for capability_gap, multi-turn conversation with parallel tool dispatch, deduplication, retry, SSE streaming, compliance tests.

**Out of scope:** FIT ingestion, plan generation, onboarding interview, frontend React UI, Google Calendar, ZWO export — all Phase 3+.

</domain>

<decisions>
## Implementation Decisions

### Backend Directory Layout

- **D-01:** Use two top-level directories: `agent/` for the reusable agent loop logic and `api/` for the FastAPI HTTP transport. The `agent/` layer is transport-agnostic so the Telegram bot (Phase 2 post-MVP priority from PROJECT.md) can reuse it without touching `api/`. The `api/` layer mounts FastAPI routes and imports from `agent/`.
- **D-02:** Suggested file layout:
  ```
  agent/
    loop.py          # core agentic loop (multi-turn, tool dispatch, retry, dedup)
    tools.py         # Anthropic tool schemas + dispatcher
    trust.py         # trust-model response scanner (TRUST-03)
  api/
    main.py          # FastAPI app lifespan, routers
    routes/
      chat.py        # SSE /chat/stream endpoint
  ```

### Tool Registry Schema Strategy

- **D-03:** Manual Anthropic tool schema dicts in `agent/tools.py` — one dict per tool, explicit `name`, `description`, `input_schema`. No programmatic inspection of function signatures. Explicit schemas are auditable and not fragile to function signature changes.
- **D-04:** The tool dispatcher in `agent/tools.py` maps `tool_name -> sports_science function`. After calling the function, it uses `ToolResult.to_tool_response()` to build the `{"type": "tool_result", "tool_use_id": ..., "content": [...]}` content block. All 8 exports from `sports_science/__all__` are registered — no ad-hoc tool definitions permitted (TRUST-02).
- **D-05:** `log_capability_gap` is registered as an Anthropic tool schema (it's in `sports_science/__all__`). When Claude calls it, the dispatcher calls the function (which logs to DB) and returns the ToolResult. This satisfies TRUST-05.

### Async/Sync Boundary

- **D-06:** Hybrid strategy:
  - Pure-compute functions (`calculate_power_zones`, `calculate_hr_zones`, `compute_tss`, `update_pmc`, `estimate_ftp_from_rides`, `progress_load`, `validate_session_vs_actual`) remain synchronous. The agent loop calls them via `asyncio.to_thread(func, *args)` — the Python 3.12 equivalent of `run_in_executor(None, ...)` with cleaner syntax. This matches the CLAUDE.md guidance: "FIT parsing is CPU-bound so offload via `asyncio.get_event_loop().run_in_executor()`."
  - `capability_gap.py` has I/O (Supabase DB write). Upgrade it in Phase 2 to async: migrate `create_client` to `acreate_client` from `supabase==2.31.0`. Verify `AsyncClient` import surface before implementing (PATTERNS.md Open Question 2).

### SSE Streaming Event Schema

- **D-07:** Typed SSE events — `event:` header distinguishes message types; `data:` is JSON. Frontend EventSource handler switches on `event` field. Schema:
  ```
  event: token
  data: {"text": "..."}        # streaming text delta from Claude

  event: tool_start
  data: {"name": "calculate_power_zones", "tool_use_id": "toolu_..."}

  event: tool_result
  data: {"tool_use_id": "toolu_...", "name": "calculate_power_zones", "value": {...}}

  event: done
  data: {}                      # turn complete

  event: error
  data: {"code": "trust_violation|tool_error|max_retries", "message": "..."}
  ```
- **D-08:** Frontend uses `EventSource` (per AGENT-05). No WebSocket. SSE endpoint: `GET /chat/stream?conversation_id=...` — Tokens stream as they arrive from Claude's streaming API.

### Trust-Model Response Parser (TRUST-03)

- **D-09:** Buffer-per-turn approach: the agent loop collects complete assistant text content within each `stop_reason` check cycle. Before forwarding text to the SSE stream, the trust scanner in `agent/trust.py` runs a heuristic regex against the buffered text:
  - Pattern: `\b\d+(?:\.\d+)?\s*(watts?|W\b|TSS|FTP|CTL|ATL|TSB|bpm|rpm|zone\s*\d|Z\d)\b`
  - If a match is found in text that is NOT attributable to a preceding `tool_result` in the current turn messages, it is an unsourced physiological number.
  - On detection: log via `log_capability_gap`, send `event: error` with `code: trust_violation`, increment retry counter, retry the turn (AGENT-03: max 3 retries).
- **D-10:** TRUST-04 enforcement: every tool call is logged with its `(tool_use_id, name, inputs, result)` to the `capability_gaps` table or a separate `tool_calls` log. This creates the audit trail that makes physiological numbers traceable.

### Agent Loop Core Behavior (from requirements)

- **D-11:** Agent loop uses raw `anthropic` SDK with explicit `stop_reason == "tool_use"` check (AGENT-01). `claude-agent-sdk` must never appear in `requirements.txt`.
- **D-12:** Parallel tool dispatch via `asyncio.gather` when Claude returns multiple `tool_use` blocks in one response (AGENT-02). Each tool is dispatched independently; results are collected before the next API call.
- **D-13:** Deduplication by `(name, hash(json.dumps(inputs, sort_keys=True)))` per turn (AGENT-04). If a duplicate appears in the same turn's tool_use blocks, the cached result is returned without re-executing.
- **D-14:** All tools return `ToolResult` (which has `value, unit, methodology, inputs`). The dispatcher wraps failures as `{"type": "tool_result", "tool_use_id": "...", "content": [{"type": "text", "text": "Error: ..."}], "is_error": true}`. Failed tool calls are surfaced in chat, not silently swallowed (AGENT-03).

### Compliance Test Suite (AGENT-06)

- **D-15:** A dedicated `tests/agent/` directory contains the compliance tests. The suite covers:
  1. Agent never emits unsourced physiological number across representative scenarios (TRUST-03 verified by injecting a tampered Claude response)
  2. Multi-turn parallel tool dispatch completes without errors
  3. Retry and deduplication paths verified
  4. SSE event sequence verified for a complete turn (token, tool_start, tool_result, done)
- **D-16:** Compliance tests use `pytest-asyncio` (already in requirements). Claude API calls in tests are intercepted with a mock that replays known response fixtures — no live API calls in the test suite.

### Claude's Discretion

- Trust scanner regex: the exact pattern for detecting unsourced physiological numbers is an implementation detail; researcher/planner can tune based on false-positive risk.
- Streaming model: use `claude-sonnet-4-5` (specified in CLAUDE.md as default). Model is configurable via env var.
- Conversation history storage: Phase 2 uses in-memory conversation history within a request; persistent DB storage of messages is Phase 3 (conversations/messages tables exist in schema but are not the Phase 2 concern).
- Tool call audit logging: implement as a simple list appended to per-request context (Phase 3 persists to DB).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements

- `.planning/REQUIREMENTS.md` §Agent Core (AGENT-01 through AGENT-06) — exact agent loop behaviors, SSE, retry, dedup, compliance tests
- `.planning/REQUIREMENTS.md` §Trust Model Enforcement (TRUST-03, TRUST-04, TRUST-05) — response parsing, traceability, capability-gap fallback
- `.planning/REQUIREMENTS.md` §Capability-Gap Logging (GAP-01, GAP-02, GAP-03) — already implemented; Phase 2 calls it as an Anthropic tool

### Phase 1 Context (decisions carried forward)

- `.planning/phases/01-sports-science-foundation/01-CONTEXT.md` — D-01 through D-10 locked; tool library complete; `ToolResult` contract; async upgrade note for capability_gap (Open Question 2 in PATTERNS.md)

### Codebase

- `sports_science/__init__.py` — `__all__` defines the exact 8 functions to register as Anthropic tool schemas in Phase 2; nothing else
- `sports_science/types.py` — `ToolResult.to_tool_response()` is the serializer for tool_result content blocks; use it
- `sports_science/capability_gap.py` — needs async Supabase client upgrade (`create_client` → `acreate_client`) before FastAPI integration
- `.planning/phases/01-sports-science-foundation/01-PATTERNS.md` — Phase 1 code patterns; async upgrade note at bottom of capability_gap section

### Project Context

- `.planning/PROJECT.md` §Non-Negotiable Architecture — trust model rules (LLM never emits physiological numbers)
- `.planning/PROJECT.md` §Business Context — "Phase 2 Telegram bot reuses the agent layer as the top priority post-MVP" → justifies transport-agnostic `agent/` directory
- `.planning/ROADMAP.md` §Phase 2 — success criteria for this phase (5 criteria)
- `prd.md` §Non-negotiable architecture — PRD trust model language

### Technology

- `requirements.txt` — current deps (no FastAPI, anthropic, uvicorn yet; Phase 2 adds these)
- CLAUDE.md §Backend — FastAPI + asyncpg + httpx version recommendations
- CLAUDE.md §AI/LLM Layer — `anthropic==0.67.x`, `claude-sonnet-4-5`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `sports_science/__all__` (8 functions): exact set to register as Anthropic tool schemas in `agent/tools.py`. No other functions are exported; the registry boundary is enforced.
- `ToolResult.to_tool_response()`: serializes any ToolResult to the Anthropic tool_result content block format. Call this directly in the tool dispatcher — no manual serialization.
- `sports_science/capability_gap.py` `log_capability_gap`: already implemented and tested. Phase 2 registers it as an Anthropic tool schema AND calls it from the trust scanner on TRUST-03 violations. It's both a callable tool and a trust enforcement mechanism.

### Established Patterns

- `ToolResult(value, unit, methodology, inputs)` frozen Pydantic model: all tool dispatching must go through this contract; the trust scanner reads `methodology` to confirm a number is tool-attributed.
- `pytest` + `pytest-asyncio` already in requirements; `asyncio_mode = auto` in `pytest.ini` — async tests work out of the box.
- `ruff.toml` for linting; `Makefile` with `make test` and `make lint` targets.
- Sync Supabase client pattern in `capability_gap.py`: reference before upgrading to async; the `_get_supabase()` helper pattern can be replicated as `_get_async_supabase()`.
- Zero-Anthropic-import boundary test (`tests/sports_science/test_import_boundary.py`): extend to also verify `sports_science/` has zero FastAPI imports in Phase 2.

### Integration Points

- `sports_science/__init__.py` → imported by `agent/tools.py` to dispatch tool calls
- `supabase/migrations/` → Phase 2 may add a `tool_calls` audit table if D-10 logging requires DB persistence (currently deferred to Phase 3 for conversations/messages)
- `api/main.py` → mounts `api/routes/chat.py`; chat route imports from `agent/loop.py`
- `agent/loop.py` → imports `agent/tools.py` (dispatcher) and `agent/trust.py` (scanner)

</code_context>

<specifics>
## Specific Ideas

- The Anthropic SDK version is `anthropic==0.67.x` (CLAUDE.md); streaming uses `client.messages.stream()` context manager which yields delta events natively.
- `asyncio.to_thread` (Python 3.12) is the preferred wrapper for sync sports_science compute calls — cleaner than `loop.run_in_executor(None, ...)`.
- Trust scanner should also check `methodology` field of any ToolResult in the response — if a physiological value was computed by the tool library, `methodology` will be a non-empty string naming the source. The scanner can use this as a positive attribution signal.
- Claude model to use: `claude-sonnet-4-5` (CLAUDE.md default), configurable via `ANTHROPIC_MODEL` env var.
- `fastapi==0.115.x`, `uvicorn==0.30.x` per CLAUDE.md stack table; add `python-multipart` (required for file upload, used in Phase 3 but install now).

</specifics>

<deferred>
## Deferred Ideas

- Persistent conversation/messages DB storage — `conversations` and `messages` tables exist (Phase 1 schema) but are populated in Phase 3, not Phase 2.
- Tool-call audit table in Supabase — D-10 defers full audit persistence to Phase 3; Phase 2 logs in-memory per request only.
- Telegram bot wiring — agent/ is built transport-agnostic for this; bot itself is post-MVP Phase 2 (not this sprint).
- Frontend EventSource consumer code — Phase 4 (UI and Calendar). Phase 2 only implements the SSE server endpoint; frontend integration is Phase 4.
- Authentication middleware — FastAPI auth (Supabase JWT verification) is a Phase 4 concern; Phase 2 endpoints are protected only by local dev setup.

</deferred>

---

*Phase: 2-Agent Core*
*Context gathered: 2026-06-19*
