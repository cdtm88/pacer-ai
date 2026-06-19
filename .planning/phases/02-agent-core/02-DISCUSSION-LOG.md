# Phase 2: Agent Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 02-agent-core
**Mode:** --auto (fully autonomous, no user prompts)
**Areas discussed:** Backend directory layout, Tool registry schema strategy, Async/sync boundary, SSE event schema, Trust parser placement

---

## Backend Directory Layout

| Option | Description | Selected |
|--------|-------------|----------|
| Single `api/` dir | All agent + FastAPI code in one directory | |
| Separate `agent/` + `api/` | `agent/` is transport-agnostic; `api/` mounts HTTP routes | ✓ |
| Single `backend/` dir | Matches "Python FastAPI (backend)" CLAUDE.md language | |

**Auto-selected:** Separate `agent/` and `api/` directories
**Rationale:** PROJECT.md explicitly calls out the Telegram bot as the top post-MVP priority; it must reuse the agent loop without the FastAPI transport layer. Transport-agnostic `agent/` makes this trivial.

---

## Tool Registry Schema Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Manual schema dicts | One explicit Anthropic tool schema dict per function | ✓ |
| Programmatic via inspect | Generate schemas from function signatures + docstrings | |
| JSON file | External `tools.json` loaded at startup | |

**Auto-selected:** Manual Anthropic tool schemas in `agent/tools.py`
**Rationale:** Explicit and auditable. Programmatic generation is fragile to signature changes. JSON files add indirection without benefit. Manual schemas are the pattern used in Anthropic's own examples.

---

## Async/Sync Boundary

| Option | Description | Selected |
|--------|-------------|----------|
| All sync via run_in_executor | Keep everything sync; wrap all in executor | |
| Hybrid | Compute stays sync (asyncio.to_thread); capability_gap upgrades to async | ✓ |
| All async | Rewrite sports_science module with async functions | |

**Auto-selected:** Hybrid — compute stays sync wrapped in `asyncio.to_thread`; `capability_gap.py` upgrades to async Supabase client
**Rationale:** CLAUDE.md explicitly recommends `run_in_executor` for CPU-bound functions. Only `capability_gap.py` does real I/O and benefits from async. Rewriting the entire sports_science module is out of scope.

---

## SSE Event Schema

| Option | Description | Selected |
|--------|-------------|----------|
| Text-only SSE | Simple `data: text_chunk` events | |
| Typed events | `event: token|tool_start|tool_result|done|error` with JSON | ✓ |
| OpenAI-compatible | `data: [DONE]` terminator, delta-only events | |

**Auto-selected:** Typed events with `event:` field
**Rationale:** Frontend needs to distinguish text from tool activity for trust model UX (showing when tools are being called). Typed events enable this without WebSocket overhead.

---

## Trust Parser Placement

| Option | Description | Selected |
|--------|-------------|----------|
| Buffer per turn | Collect complete assistant text, scan, then forward to SSE | ✓ |
| Inline intercept | Scan at streaming level and redact in real-time | |
| Post-response only | Validate after turn completes, TRUST-04 only | |

**Auto-selected:** Buffer per turn, scan before forwarding to SSE
**Rationale:** Only safe approach that guarantees unsourced numbers never reach the frontend (TRUST-03). Inline interception at token level is too granular — physiological patterns span multiple tokens. Post-response validation violates TRUST-03 (user would see the number before retry).

---

## Claude's Discretion

- Trust scanner regex pattern: exact regex is an implementation detail; researcher/planner can tune based on false-positive testing.
- Streaming model selection: `claude-sonnet-4-5` as default per CLAUDE.md; configurable via `ANTHROPIC_MODEL` env var.
- Conversation history storage strategy: in-memory per request for Phase 2; DB persistence deferred to Phase 3.
- Tool-call audit logging granularity: in-memory list per request for Phase 2; DB persistence deferred to Phase 3.

## Deferred Ideas

- Telegram bot wiring — `agent/` directory is built for this; bot itself is post-MVP.
- Persistent conversation/messages DB — tables exist (Phase 1 schema) but populated in Phase 3.
- Authentication middleware — FastAPI JWT verification is a Phase 4 concern.
- Frontend EventSource consumer code — Phase 4 (UI and Calendar).
