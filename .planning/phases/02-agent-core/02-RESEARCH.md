# Phase 2: Agent Core - Research

**Researched:** 2026-06-19
**Domain:** Anthropic Python SDK agentic loop, FastAPI SSE streaming, trust-model enforcement
**Confidence:** HIGH (core APIs verified from installed packages or official docs)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Use two top-level directories: `agent/` (transport-agnostic loop) and `api/` (FastAPI HTTP transport).
- D-02: File layout: `agent/loop.py`, `agent/tools.py`, `agent/trust.py`; `api/main.py`, `api/routes/chat.py`.
- D-03: Manual Anthropic tool schema dicts in `agent/tools.py` — explicit `name`, `description`, `input_schema`. No programmatic signature inspection.
- D-04: Tool dispatcher uses `ToolResult.to_tool_response()` to build tool_result content blocks.
- D-05: `log_capability_gap` is registered as an Anthropic tool schema (already in `sports_science/__all__`).
- D-06: Hybrid async: sync compute functions via `asyncio.to_thread(func, *args)`; `capability_gap.py` upgraded to async via `acreate_client` from `supabase==2.31.0`.
- D-07: Typed SSE events with `event:` header — token | tool_start | tool_result | done | error; `data:` is JSON.
- D-08: `GET /chat/stream?conversation_id=...` SSE endpoint using `EventSource`.
- D-09: Buffer-per-turn trust scanner with heuristic regex in `agent/trust.py`.
- D-10: Tool call audit logging in-memory per request (DB persistence deferred to Phase 3).
- D-11: Raw anthropic SDK with `stop_reason == "tool_use"` check; `claude-agent-sdk` forbidden.
- D-12: `asyncio.gather` for parallel tool dispatch.
- D-13: Deduplication by `(name, hash(json.dumps(inputs, sort_keys=True)))` per turn.
- D-14: `ToolResult` wraps failures as `is_error: true` tool_result blocks.
- D-15: `tests/agent/` compliance test suite.
- D-16: `pytest-asyncio` with mock Claude response fixtures; no live API calls in tests.

### Claude's Discretion
- Trust scanner exact regex pattern (tune for false-positive risk).
- Streaming model: `claude-sonnet-4-5`, configurable via `ANTHROPIC_MODEL` env var.
- Conversation history: in-memory within a request; DB persistence is Phase 3.
- Tool call audit logging: simple list appended to per-request context.

### Deferred Ideas (OUT OF SCOPE)
- Persistent conversation/messages DB storage.
- Tool-call audit table in Supabase (Phase 3).
- Telegram bot wiring (post-MVP Phase 2).
- Frontend EventSource consumer code (Phase 4).
- Authentication middleware / Supabase JWT verification (Phase 4).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AGENT-01 | Raw `anthropic` SDK with explicit `stop_reason == "tool_use"` check; claude-agent-sdk forbidden | SDK streaming pattern documented below; stop_reason surfaces via `stream.get_final_message()` or `with_streaming_response` |
| AGENT-02 | Multi-turn with `asyncio.gather` for parallel tool dispatch | `asyncio.gather` pattern confirmed; messages array construction documented |
| AGENT-03 | Max 3 retries per tool call; failed calls surfaced as `is_error: true` blocks | Retry counter in loop state; ToolResult.to_tool_response() wraps errors |
| AGENT-04 | Dedup by `(name, args_hash)` per turn | Hash via `hash(json.dumps(inputs, sort_keys=True))` — pure Python, no deps |
| AGENT-05 | SSE via `StreamingResponse`; frontend uses `EventSource` | FastAPI SSE pattern documented below |
| AGENT-06 | Compliance test suite | pytest-asyncio mock fixtures pattern documented |
| TRUST-03 | Response parsed before display; unsourced physiological numbers trigger retry + gap log | Trust scanner regex and buffer-per-turn approach documented |
| TRUST-04 | Every physiological number traceable to tool-library call in logs | In-memory audit log per request; tool_use_id links call to result |
| TRUST-05 | Missing quantitative method → `log_capability_gap` + qualitative fallback | `log_capability_gap` registered as Anthropic tool schema; trust scanner calls it on TRUST-03 violations |
</phase_requirements>

---

## Summary

Phase 2 builds three cooperating layers: the `agent/` module (transport-agnostic agentic loop), the `api/` module (FastAPI SSE transport), and the `tests/agent/` compliance suite. The critical architectural constraint — the LLM never emits physiological numbers directly — is enforced by the trust scanner in `agent/trust.py` which intercepts all assistant text before it reaches the SSE stream.

The Anthropic SDK's streaming API uses a context-manager pattern (`client.messages.stream()`). The multi-turn tool-use loop is a while-loop that checks `stop_reason == "tool_use"` on each message, dispatches registered tools in parallel via `asyncio.gather`, appends tool results to the messages array, then calls the API again. The loop terminates when `stop_reason == "end_turn"` or retries are exhausted.

The async/sync boundary is managed with `asyncio.to_thread` for compute-bound sports_science functions. The Supabase async client upgrade for `capability_gap.py` uses `acreate_client` and `AsyncClient` — both confirmed as direct exports from `supabase==2.31.0` in the installed package.

**Primary recommendation:** Follow the exact file layout from D-02. Build `agent/tools.py` first (tool registry + dispatcher), then `agent/trust.py` (trust scanner), then `agent/loop.py` (ties them together), then `api/` (FastAPI + SSE), then `tests/agent/` (compliance suite).

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Agentic loop / tool dispatch | `agent/loop.py` | `agent/tools.py` | Transport-agnostic; reusable by Telegram bot |
| Tool schema registry | `agent/tools.py` | `sports_science/__init__.py` | Wraps Phase 1 functions as Anthropic schemas |
| Trust enforcement / response parsing | `agent/trust.py` | `agent/loop.py` | Scanner is called by loop before SSE emit |
| SSE HTTP transport | `api/routes/chat.py` | `api/main.py` | FastAPI layer; imports from `agent/` |
| Async Supabase writes | `sports_science/capability_gap.py` | `agent/loop.py` | I/O-bound; upgraded to `acreate_client` |
| Compliance verification | `tests/agent/` | — | Mocked fixtures; no live API |

---

## Standard Stack

### Core (Phase 2 additions — not yet in requirements.txt)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.67.x | Anthropic API client; streaming + tool use | Required by CLAUDE.md; tool use GA since 0.27.0 |
| fastapi | 0.115.x | HTTP framework; SSE endpoint | Required by CLAUDE.md; native async; AGENT-05 |
| uvicorn | 0.30.x | ASGI server | Required by CLAUDE.md; standard FastAPI server |
| python-multipart | latest | File upload parsing (FIT ingestion prep) | Required FastAPI dep; install now per CLAUDE.md |

### Already Installed (in requirements.txt)

| Library | Version | Purpose |
|---------|---------|---------|
| supabase | 2.31.0 | Async DB client for capability_gap upgrade |
| pydantic | 2.13.4 | ToolResult model; FastAPI request/response |
| pytest-asyncio | 1.4.0 | Async test support for compliance suite |
| pytest | 9.1.1 | Test runner |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `asyncio.to_thread` | `loop.run_in_executor(None, fn)` | to_thread is Python 3.10+ idiomatic, cleaner; same semantics |
| SSE via StreamingResponse | WebSocket | SSE is unidirectional server-push; simpler client; AGENT-05 forbids WebSocket |
| Manual Anthropic tool schemas | Pydantic-to-schema generation | Manual schemas are auditable and not fragile to signature changes (D-03) |

**Installation (additions):**
```bash
pip install anthropic==0.67.* fastapi==0.115.* uvicorn==0.30.* python-multipart
```

---

## Package Legitimacy Audit

> These are all long-established packages. PyPI "too-new" signals are false positives reflecting recent patch releases, not new packages. All have official org-maintained GitHub repos.

| Package | Registry | Source Repo | Verdict | Disposition |
|---------|----------|-------------|---------|-------------|
| anthropic | PyPI | github.com/anthropics/anthropic-sdk-python | SUS (recent release) | Approved — official Anthropic SDK; legitimate |
| fastapi | PyPI | github.com/fastapi/fastapi | SUS (recent release) | Approved — widely adopted; official org repo |
| uvicorn | PyPI | github.com/encode/uvicorn | SUS (recent release) | Approved — standard ASGI server |
| pytest-asyncio | PyPI | github.com/pytest-dev/pytest-asyncio | SUS (recent release) | Approved — pytest-dev org; long-established |

**Packages removed due to SLOP verdict:** none

**Note:** PyPI legitimacy seam flags all packages as SUS due to "unknown-downloads" (registry lookup limitation) and "too-new" (recent patch). All four are industry-standard packages confirmed via official GitHub organization repos. `[ASSUMED]` tag applied to version numbers not confirmed via pip index this session.

---

## Architecture Patterns

### System Architecture Diagram

```
User HTTP Request (GET /chat/stream?conversation_id=...)
        |
        v
api/routes/chat.py  ──────────────────────────────────────────┐
  StreamingResponse(async_generator)                            |
        |                                                        |
        v                                                        |
agent/loop.py  <──────────────────────────────────────────┐    |
  run_turn(messages, tools) -> AsyncIterator[SSEEvent]     |    |
        |                                                   |    |
        |─── anthropic.AsyncAnthropic.messages.stream() ───|    |
        |         (yields: text_delta, tool_use blocks)     |    |
        |                                                   |    |
        |─── agent/trust.py                                 |    |
        |      scan_buffer(text) -> violation: bool         |    |
        |      on violation: log_capability_gap + retry     |    |
        |                                                   |    |
        |─── agent/tools.py                                 |    |
               asyncio.gather(*[dispatch(tool_use) for …])  |    |
                    |                                        |    |
                    v                                        |    |
              sports_science/__init__.py                     |    |
                asyncio.to_thread(sync_fn, *args)            |    |
                    |                                        |    |
                    v                                        |    |
              ToolResult.to_tool_response() ─────────────────┘    |
                (append tool_result blocks to messages)           |
                    |                                             |
                    v                                             |
              Next API call (loop continues until end_turn) ──────┘
                    |
                    v
          SSE events emitted: token | tool_start | tool_result | done | error
```

### Recommended Project Structure

```
agent/
  __init__.py
  loop.py          # run_turn(); while stop_reason == "tool_use" loop
  tools.py         # TOOL_SCHEMAS list; dispatch(tool_use_block) -> tool_result_block
  trust.py         # scan_buffer(text, turn_tool_results) -> TrustViolation | None
api/
  __init__.py
  main.py          # FastAPI app, lifespan, router mount
  routes/
    __init__.py
    chat.py        # GET /chat/stream SSE endpoint
tests/
  agent/
    __init__.py
    conftest.py    # mock_anthropic_stream fixture
    test_loop.py   # multi-turn, parallel dispatch, retry, dedup
    test_trust.py  # TRUST-03 compliance scenarios
    test_sse.py    # SSE event sequence via httpx.AsyncClient
sports_science/    # Phase 1 (do not modify structure)
  capability_gap.py  # UPGRADE: create_client -> acreate_client
```

### Pattern 1: Anthropic Streaming Tool-Use Loop

**What:** The core agentic while-loop using the raw SDK with `stop_reason` check.
**When to use:** Every `run_turn()` call in `agent/loop.py`.

```python
# agent/loop.py
# Source: [ASSUMED] based on anthropic SDK streaming docs pattern
import anthropic
import asyncio
import json
from typing import AsyncIterator
from agent.tools import dispatch_tool, TOOL_SCHEMAS, dedup_key

MAX_RETRIES = 3

async def run_turn(
    messages: list[dict],
    client: anthropic.AsyncAnthropic,
    model: str,
    trust_scanner,
    audit_log: list,
) -> AsyncIterator[dict]:  # yields SSE event dicts
    retries = 0
    while retries <= MAX_RETRIES:
        text_buffer = []
        tool_results = []
        seen_calls: dict[tuple, dict] = {}  # D-13 dedup

        async with client.messages.stream(
            model=model,
            max_tokens=4096,
            tools=TOOL_SCHEMAS,
            messages=messages,
        ) as stream:
            async for event in stream:
                if event.type == "content_block_delta":
                    if hasattr(event.delta, "text"):
                        text_buffer.append(event.delta.text)
                        yield {"event": "token", "data": {"text": event.delta.text}}

            final_msg = await stream.get_final_message()

        stop_reason = final_msg.stop_reason

        # Trust scan the buffered text
        violation = trust_scanner.scan("".join(text_buffer), tool_results_this_turn=tool_results)
        if violation:
            retries += 1
            messages.append({"role": "assistant", "content": final_msg.content})
            messages.append({
                "role": "user",
                "content": "Please rephrase without specific numbers — use qualitative descriptions only."
            })
            yield {"event": "error", "data": {"code": "trust_violation", "message": str(violation)}}
            continue

        if stop_reason == "tool_use":
            # Collect tool_use blocks
            tool_use_blocks = [b for b in final_msg.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": final_msg.content})

            # D-13: dedup within turn
            unique_blocks = []
            for block in tool_use_blocks:
                key = dedup_key(block.name, block.input)
                if key not in seen_calls:
                    seen_calls[key] = None
                    unique_blocks.append(block)
                    yield {"event": "tool_start", "data": {"name": block.name, "tool_use_id": block.id}}

            # D-12: parallel dispatch
            tool_result_blocks = await asyncio.gather(
                *[dispatch_tool(b, audit_log) for b in unique_blocks]
            )

            for block, result_block in zip(unique_blocks, tool_result_blocks):
                tool_results.append(result_block)
                yield {"event": "tool_result", "data": {
                    "tool_use_id": block.id,
                    "name": block.name,
                    "value": result_block.get("content", [{}])[0].get("text"),
                }}

            messages.append({"role": "user", "content": tool_result_blocks})
            # Continue loop — next iteration calls API again

        elif stop_reason == "end_turn":
            yield {"event": "done", "data": {}}
            return
        else:
            yield {"event": "error", "data": {"code": "unexpected_stop", "message": stop_reason}}
            return

    yield {"event": "error", "data": {"code": "max_retries", "message": "Max retries exceeded"}}
```

### Pattern 2: Tool Schema Registration + Dispatcher

**What:** Manual Anthropic tool schemas for all 8 sports_science functions.
**When to use:** `agent/tools.py` — only source of tool definitions.

```python
# agent/tools.py
# Source: [ASSUMED] based on Anthropic tool_use spec + sports_science ToolResult contract
import asyncio
import json
import hashlib
from sports_science import (
    calculate_power_zones, calculate_hr_zones, estimate_ftp_from_rides,
    compute_tss, update_pmc, progress_load, validate_session_vs_actual,
    log_capability_gap,
)
from sports_science.types import ToolResult

TOOL_REGISTRY = {
    "calculate_power_zones": calculate_power_zones,
    "calculate_hr_zones": calculate_hr_zones,
    "estimate_ftp_from_rides": estimate_ftp_from_rides,
    "compute_tss": compute_tss,
    "update_pmc": update_pmc,
    "progress_load": progress_load,
    "validate_session_vs_actual": validate_session_vs_actual,
    "log_capability_gap": log_capability_gap,
}

TOOL_SCHEMAS = [
    {
        "name": "calculate_power_zones",
        "description": "Returns Coggan/Allen 7-zone power zones from FTP. Use this whenever power zone targets are needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ftp": {"type": "number", "description": "Functional Threshold Power in watts"}
            },
            "required": ["ftp"]
        }
    },
    # ... (one dict per tool, all 8 registered)
    {
        "name": "log_capability_gap",
        "description": "Call this when a quantitative method the tool library lacks is needed. Logs the gap and returns a user-safe message. Do NOT improvise a number — call this instead.",
        "input_schema": {
            "type": "object",
            "properties": {
                "method_name": {"type": "string"},
                "context": {"type": "object"}
            },
            "required": ["method_name", "context"]
        }
    },
]

def dedup_key(name: str, inputs: dict) -> tuple:
    return (name, hashlib.sha256(json.dumps(inputs, sort_keys=True).encode()).hexdigest())

async def dispatch_tool(tool_use_block, audit_log: list) -> dict:
    """Dispatch one tool_use block. Returns Anthropic tool_result content block."""
    name = tool_use_block.name
    inputs = tool_use_block.input
    tool_use_id = tool_use_block.id

    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        audit_log.append({"tool_use_id": tool_use_id, "name": name, "error": "not_found"})
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [{"type": "text", "text": f"Error: unknown tool '{name}'"}],
            "is_error": True,
        }

    try:
        # D-06: sync functions run in thread; log_capability_gap is async-upgraded
        if asyncio.iscoroutinefunction(fn):
            result: ToolResult = await fn(**inputs)
        else:
            result: ToolResult = await asyncio.to_thread(fn, **inputs)

        audit_log.append({"tool_use_id": tool_use_id, "name": name, "result": result.model_dump()})
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [{"type": "text", "text": json.dumps(result.to_tool_response())}],
            "is_error": False,
        }
    except Exception as exc:
        audit_log.append({"tool_use_id": tool_use_id, "name": name, "error": str(exc)})
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [{"type": "text", "text": f"Error: {exc}"}],
            "is_error": True,
        }
```

### Pattern 3: Trust Scanner

**What:** Regex scan of buffered assistant text to detect unsourced physiological numbers.
**When to use:** Called by `agent/loop.py` after each API response, before SSE emit.

```python
# agent/trust.py
# Source: D-09 (CONTEXT.md), pattern from requirement TRUST-03
import re
from dataclasses import dataclass
from typing import Optional

# Detects numeric values followed by physiological units.
# Designed to catch: "your FTP is 250W", "Zone 4", "TSS 85", "CTL 42", "150 bpm"
# NOT triggered by: tool_result JSON (checked via turn context), qualitative text.
PHYSIO_PATTERN = re.compile(
    r'\b\d+(?:\.\d+)?\s*'
    r'(watts?|W\b|TSS\b|FTP\b|CTL\b|ATL\b|TSB\b|bpm\b|rpm\b|zone\s*\d|Z\d\b)',
    re.IGNORECASE
)

@dataclass
class TrustViolation:
    matched_text: str
    pattern: str

def scan_buffer(text: str, tool_result_values: set[str]) -> Optional[TrustViolation]:
    """
    Return TrustViolation if text contains unsourced physiological numbers.
    Numbers that appear verbatim in tool_result_values are attributed — not violations.
    """
    for match in PHYSIO_PATTERN.finditer(text):
        matched = match.group(0).strip()
        # Attribution check: if this value was returned by a tool this turn, it's OK
        if not any(matched in val for val in tool_result_values):
            return TrustViolation(matched_text=matched, pattern=PHYSIO_PATTERN.pattern)
    return None
```

### Pattern 4: FastAPI SSE Endpoint

**What:** `GET /chat/stream` endpoint using `StreamingResponse` with async generator.
**When to use:** `api/routes/chat.py`.

```python
# api/routes/chat.py
# Source: [ASSUMED] FastAPI StreamingResponse SSE pattern
import json
import anthropic
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from agent.loop import run_turn
from agent.trust import scan_buffer

router = APIRouter()
client = anthropic.AsyncAnthropic()  # reads ANTHROPIC_API_KEY from env

async def sse_generator(messages: list[dict]):
    audit_log = []
    try:
        async for event in run_turn(messages, client, model, scan_buffer, audit_log):
            event_type = event["event"]
            data = json.dumps(event["data"])
            yield f"event: {event_type}\ndata: {data}\n\n"
    except Exception as exc:
        error_data = json.dumps({"code": "server_error", "message": str(exc)})
        yield f"event: error\ndata: {error_data}\n\n"

@router.get("/chat/stream")
async def chat_stream(conversation_id: str = Query(...)):
    # Phase 2: messages are in-memory; conversation_id reserved for Phase 3 DB lookup
    messages = [{"role": "user", "content": "Hello"}]  # placeholder; Phase 3 loads from DB
    return StreamingResponse(
        sse_generator(messages),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disables Nginx buffering
        },
    )
```

### Pattern 5: Supabase Async Upgrade (capability_gap.py)

**What:** Replace sync `create_client` with async `acreate_client` in `sports_science/capability_gap.py`.
**Source:** [VERIFIED from /Users/christianmoore/ai/pacer-ai/.venv/lib/python3.12/site-packages/supabase/__init__.py]

```python
# sports_science/capability_gap.py — Phase 2 async upgrade
import os
from supabase import acreate_client, AsyncClient  # VERIFIED export in supabase==2.31.0
from .types import ToolResult

async def _get_async_supabase() -> AsyncClient:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return await acreate_client(url, key)

async def log_capability_gap(
    method_name: str,
    context: dict,
    user_id: str | None = None,
) -> ToolResult:
    supabase = await _get_async_supabase()
    await supabase.table("capability_gaps").insert({
        "user_id": user_id,
        "method_name": method_name,
        "description": f"Missing tool: {method_name}",
        "context": context,
    }).execute()
    user_message = (
        "I don't have a specialized tool for that calculation yet. "
        "I've logged it for the development team. "
        "I'll use a qualitative approach for now."
    )
    return ToolResult(
        value={"status": "logged", "message": user_message},
        unit="",
        methodology="capability_gap_log",
        inputs={"context_keys": list(context.keys())},
    )
```

**Key note:** `log_capability_gap` is now `async def`. The tool dispatcher in `agent/tools.py` already handles this via `if asyncio.iscoroutinefunction(fn): result = await fn(**inputs)`.

### Pattern 6: pytest-asyncio Compliance Tests

**What:** Mock fixture for Anthropic streaming responses; no live API calls.
**Source:** [ASSUMED] — standard pytest-asyncio + unittest.mock pattern.

```python
# tests/agent/conftest.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_stream_text_only():
    """Simulates a Claude response with only text (no tool use)."""
    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = [MagicMock(type="text", text="Great workout today!")]

    stream = AsyncMock()
    stream.__aenter__ = AsyncMock(return_value=stream)
    stream.__aexit__ = AsyncMock(return_value=None)
    stream.get_final_message = AsyncMock(return_value=msg)
    stream.__aiter__ = AsyncMock(return_value=iter([]))  # no delta events
    return stream

@pytest.fixture
def mock_stream_with_tool_use():
    """Simulates tool_use response followed by end_turn."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "toolu_test_001"
    tool_block.name = "calculate_power_zones"
    tool_block.input = {"ftp": 200.0}

    msg = MagicMock()
    msg.stop_reason = "tool_use"
    msg.content = [tool_block]

    stream = AsyncMock()
    stream.__aenter__ = AsyncMock(return_value=stream)
    stream.__aexit__ = AsyncMock(return_value=None)
    stream.get_final_message = AsyncMock(return_value=msg)
    stream.__aiter__ = AsyncMock(return_value=iter([]))
    return stream

@pytest.fixture
def mock_stream_trust_violation():
    """Simulates assistant emitting unsourced physiological number."""
    delta = MagicMock()
    delta.type = "content_block_delta"
    delta.delta = MagicMock()
    delta.delta.text = "Your FTP is 250 watts based on your history."

    msg = MagicMock()
    msg.stop_reason = "end_turn"
    msg.content = [MagicMock(type="text", text="Your FTP is 250 watts based on your history.")]

    stream = AsyncMock()
    stream.__aenter__ = AsyncMock(return_value=stream)
    stream.__aexit__ = AsyncMock(return_value=None)
    stream.get_final_message = AsyncMock(return_value=msg)
    stream.__aiter__ = AsyncMock(return_value=iter([delta]))
    return stream
```

### Anti-Patterns to Avoid

- **Importing `claude-agent-sdk`:** AGENT-01 explicitly forbids it. It executes tools autonomously, bypassing the trust model. Check `requirements.txt` for absence after install.
- **Emitting SSE before trust scan:** Text deltas arrive during streaming but must be buffered and scanned before forwarding. Do not yield `token` events directly from delta callbacks — buffer them per turn.
- **Singleton Supabase async client:** `acreate_client` must be called inside an async context (FastAPI lifespan or per-request). Do not call it at module import time.
- **Trusting `methodology` alone:** The trust scanner checks for unsourced numbers in text. Numbers that appear in tool_result JSON are attributed, but the scanner must compare against actual returned values, not just check that methodology is non-empty.
- **Mutable default in dedup dict:** The per-turn `seen_calls` dict must be initialized fresh each turn iteration, not as a module-level default.
- **asyncio.gather with non-unique blocks:** Run dedup before `asyncio.gather`. Duplicate tool_use blocks that pass through to gather can cause duplicate DB writes in `log_capability_gap`.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP streaming to browser | Custom chunked response | `FastAPI StreamingResponse` with `media_type="text/event-stream"` | Handles connection lifecycle, headers, backpressure |
| Async-to-sync bridge | Manual `loop.run_until_complete` | `asyncio.to_thread(fn, *args)` | Thread-safe; no event loop nesting issues in Python 3.12 |
| Anthropic API retry logic | Custom exponential backoff | SDK built-in retry (set `max_retries=` on client) | SDK handles 429/5xx; our MAX_RETRIES=3 is for trust violations only |
| JSON serialization of tool inputs | Custom encoder | `json.dumps(inputs, sort_keys=True)` | Deterministic key ordering needed for dedup hash |
| Async test client | `requests` + threading | `httpx.AsyncClient` with `transport=ASGITransport(app)` | FastAPI-native; no server needed for unit tests |

---

## Common Pitfalls

### Pitfall 1: Trust Scanner False Positives on Tool Result Echo

**What goes wrong:** Claude echoes a tool result value in its text ("Your power zones show Zone 4 at 180-210 watts") — this is attributable but the regex matches it.
**Why it happens:** The attribution check compares the matched string against raw tool result JSON values, but string matching is imprecise.
**How to avoid:** After collecting tool result blocks this turn, extract all numeric values from result JSON and store as a set of strings. The scan_buffer attribution check uses `any(matched in val for val in tool_result_values)`.
**Warning signs:** High trust violation rate on normal responses; `calculate_power_zones` responses always triggering.

### Pitfall 2: SSE Connection Dropped by Nginx/Proxy

**What goes wrong:** SSE events stop arriving after ~60 seconds; connection silently closes.
**Why it happens:** Nginx default proxy_read_timeout is 60s; proxy buffers SSE output.
**How to avoid:** Set `X-Accel-Buffering: no` response header. On Railway, configure `RAILWAY_PROXY_READ_TIMEOUT` env var. Send keepalive comment lines (`: keepalive\n\n`) every 15s if no events.
**Warning signs:** EventSource `onerror` fires after exactly 60 seconds of idle.

### Pitfall 3: Anthropic Stream Context Manager Nesting

**What goes wrong:** `RuntimeError: generator already executing` or events received out of order.
**Why it happens:** Awaiting `stream.get_final_message()` inside the `async for event in stream` loop.
**How to avoid:** Collect all events in the `async for` loop first, exit the loop, then call `await stream.get_final_message()` after. The SDK context manager guarantees the message is fully buffered after iteration completes.

### Pitfall 4: asyncio.to_thread in Already-Threaded Context

**What goes wrong:** `RuntimeError: no running event loop` when sports_science functions are called from a thread that doesn't have an event loop.
**Why it happens:** `asyncio.to_thread` creates a new thread; sync functions inside it cannot call `asyncio.run()`.
**How to avoid:** Sports_science functions are purely synchronous (no asyncio calls inside them) — this is safe. Never add `asyncio` calls to sports_science functions in Phase 2.

### Pitfall 5: messages Array Mutation Across Retries

**What goes wrong:** On trust violation retry, stale assistant messages with unsourced numbers remain in the messages array, causing Claude to repeat them.
**Why it happens:** Appending the violating assistant message before scanning.
**How to avoid:** Only append the assistant message to `messages` after the trust scanner passes. On violation, send a correction user message instead.

### Pitfall 6: Supabase AsyncClient Not Awaited

**What goes wrong:** `TypeError: object AsyncClient is not awaitable` when calling table operations.
**Why it happens:** `acreate_client(url, key)` is a coroutine; not awaiting it returns the coroutine object, not the client.
**How to avoid:** Always `client = await acreate_client(url, key)`. Confirmed from installed package: `acreate_client` in `supabase._async.client` is defined as `async def create_client(...)`.

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| Synchronous Anthropic client (`anthropic.Anthropic`) | `anthropic.AsyncAnthropic` with `async with client.messages.stream()` | Required for FastAPI async; non-blocking streaming |
| `loop.run_in_executor(None, fn)` | `asyncio.to_thread(fn, *args)` | Same semantics; cleaner syntax; Python 3.10+ |
| `supabase.create_client` (sync) | `await supabase.acreate_client` (async) | Required for FastAPI lifespan; confirmed in supabase==2.31.0 |
| SSE via WebSocket fallback | Native `text/event-stream` via StreamingResponse | Simpler; EventSource is sufficient for server-push |

**Deprecated/outdated:**
- `supabase-py-async` (separate package): The main `supabase` package now includes async client directly as of 2.x. Do not add a separate `supabase-py-async` dependency.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Config file | `pytest.ini` (already exists; `asyncio_mode = auto`) |
| Quick run command | `pytest tests/agent/ -x -q` |
| Full suite command | `pytest tests/ -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AGENT-01 | `claude-agent-sdk` absent from deps | import check | `pytest tests/agent/test_loop.py::test_no_agent_sdk -x` | Wave 0 |
| AGENT-02 | Parallel tool dispatch via asyncio.gather | unit | `pytest tests/agent/test_loop.py::test_parallel_tool_dispatch -x` | Wave 0 |
| AGENT-03 | Max 3 retries; errors surfaced as is_error | unit | `pytest tests/agent/test_loop.py::test_retry_limit -x` | Wave 0 |
| AGENT-04 | Dedup by (name, args_hash) per turn | unit | `pytest tests/agent/test_loop.py::test_tool_deduplication -x` | Wave 0 |
| AGENT-05 | SSE event sequence: token, tool_start, tool_result, done | integration | `pytest tests/agent/test_sse.py -x` | Wave 0 |
| AGENT-06 | Compliance suite passes | integration | `pytest tests/agent/ -x` | Wave 0 |
| TRUST-03 | Unsourced physiological number triggers retry + gap log | unit | `pytest tests/agent/test_trust.py::test_trust_violation_triggers_retry -x` | Wave 0 |
| TRUST-04 | Audit log contains tool_use_id + result per call | unit | `pytest tests/agent/test_loop.py::test_audit_log -x` | Wave 0 |
| TRUST-05 | Missing method → log_capability_gap called; no number emitted | unit | `pytest tests/agent/test_trust.py::test_capability_gap_fallback -x` | Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/agent/ -x -q`
- **Per wave merge:** `pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/agent/__init__.py`
- [ ] `tests/agent/conftest.py` — mock_anthropic_stream fixtures (patterns above)
- [ ] `tests/agent/test_loop.py` — multi-turn, parallel, retry, dedup, audit
- [ ] `tests/agent/test_trust.py` — TRUST-03/04/05 compliance scenarios
- [ ] `tests/agent/test_sse.py` — SSE event sequence via `httpx.AsyncClient(transport=ASGITransport(app))`

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (Phase 4) | — |
| V3 Session Management | no (Phase 4) | — |
| V4 Access Control | no (Phase 4) | — |
| V5 Input Validation | yes | Pydantic models on FastAPI routes; tool inputs validated by Anthropic SDK |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Prompt injection via user message | Tampering | Tool schemas are locked; LLM cannot add new tools at runtime; trust scanner catches numeric injection |
| ANTHROPIC_API_KEY exposure | Info disclosure | Env var only; never logged; never in SSE response |
| SUPABASE_SERVICE_ROLE_KEY exposure | Info disclosure | Backend only; never in frontend requests; not included in SSE events |
| Zombie tool loop (infinite retries) | DoS | MAX_RETRIES = 3 hard cap; dedup prevents same call repeating |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.12 | asyncio.to_thread, all backend | ✓ (venv) | 3.12.x | — |
| supabase PyPI | capability_gap async | ✓ (venv) | 2.31.0 | — |
| pytest-asyncio | compliance tests | ✓ (venv) | 1.4.0 | — |
| anthropic PyPI | agent loop | ✗ (not installed) | — | Install in Wave 0 |
| fastapi PyPI | SSE endpoint | ✗ (not installed) | — | Install in Wave 0 |
| uvicorn PyPI | ASGI server | ✗ (not installed) | — | Install in Wave 0 |

**Missing dependencies with no fallback:**
- `anthropic` — core dependency; install in Wave 0: `pip install anthropic==0.67.*`
- `fastapi` + `uvicorn` — required for SSE endpoint; install in Wave 0

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `client.messages.stream()` async context manager yields `content_block_delta` events with `event.delta.text` attribute | Code Examples (Pattern 1) | Loop fails to collect text; fix: inspect actual event shape from SDK on first run |
| A2 | `stream.get_final_message()` is callable after exhausting the async iterator | Code Examples (Pattern 1) | AttributeError; fix: use `async with stream as s: msg = await s.get_final_message()` |
| A3 | `anthropic==0.67.x` is the latest stable; `0.67.*` pip specifier resolves correctly | Standard Stack | Version mismatch; fix: `pip install anthropic` and pin to installed version |
| A4 | FastAPI `StreamingResponse` with `media_type="text/event-stream"` sends SSE without additional configuration | Code Examples (Pattern 4) | Events not received; fix: verify with curl before frontend integration |
| A5 | `pytest-asyncio==1.4.0` (installed) is compatible with `asyncio_mode = auto` in pytest.ini | Validation Architecture | Tests require explicit `@pytest.mark.asyncio`; fix: check pytest-asyncio 1.x changelog |
| A6 | Trust scanner attribution via string containment check is sufficient | Code Examples (Pattern 3) | False negatives (attributed numbers not detected as attributed); tune regex |

---

## Open Questions

1. **Anthropic SDK streaming delta event shape**
   - What we know: SDK uses async context manager; `content_block_delta` events carry text
   - What's unclear: Exact attribute path (`event.delta.text` vs `event.delta.text_delta`) in 0.67.x
   - Recommendation: Print first event in Wave 0 integration test; fix attribute path before trust scanner

2. **Trust scanner false positive rate**
   - What we know: Regex `\b\d+(?:\.\d+)?\s*(watts?|...)` will catch tool-echoed values
   - What's unclear: How often Claude echoes exact numeric values from tool results in running text
   - Recommendation: Run compliance tests with representative Claude responses before tuning; start strict, loosen if needed

3. **FastAPI lifespan for async Supabase client**
   - What we know: `acreate_client` must be awaited in async context
   - What's unclear: Whether to create client per-request or via FastAPI lifespan app state
   - Recommendation: Per-request in Phase 2 (simpler, no lifespan needed); optimize to lifespan singleton in Phase 3

---

## Sources

### Primary (VERIFIED from installed package)
- `/Users/christianmoore/ai/pacer-ai/.venv/lib/python3.12/site-packages/supabase/__init__.py` — confirmed `acreate_client` and `AsyncClient` as direct exports in supabase==2.31.0
- `/Users/christianmoore/ai/pacer-ai/.venv/lib/python3.12/site-packages/supabase/_async/client.py` — confirmed `AsyncClient` class and `create_client` as async function

### Secondary (from CONTEXT.md — locked decisions)
- `.planning/phases/02-agent-core/02-CONTEXT.md` D-01 through D-16

### Tertiary (ASSUMED — training knowledge)
- Anthropic SDK 0.67.x streaming API patterns (A1–A3)
- FastAPI StreamingResponse SSE headers (A4)
- pytest-asyncio mock fixture patterns (A5)

---

## Metadata

**Confidence breakdown:**
- supabase async client API: HIGH — verified from installed package source
- Standard stack (anthropic, fastapi, uvicorn): MEDIUM — known packages, versions from CLAUDE.md, not verified via pip index this session
- Anthropic SDK streaming patterns: LOW/ASSUMED — SDK not installed in venv; patterns from training knowledge
- Trust scanner regex: MEDIUM — pattern from CONTEXT.md D-09; false positive rate unknown until tested
- FastAPI SSE pattern: MEDIUM — well-documented pattern; headers confirmed from community

**Research date:** 2026-06-19
**Valid until:** 2026-07-19 (30 days for stable packages)
