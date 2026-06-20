# api/routes/chat.py
"""
SSE chat endpoint for PacerAI (AGENT-05, D-07, D-08).

GET /chat/stream?conversation_id=...

Returns a text/event-stream StreamingResponse that drives run_turn from
agent/loop.py and emits typed SSE frames to an EventSource client.

SSE event schema (D-07):
  event: token
  data: {"text": "..."}        # streaming text delta from Claude

  event: tool_start
  data: {"name": "...", "tool_use_id": "toolu_..."}

  event: tool_result
  data: {"tool_use_id": "toolu_...", "name": "...", "value": ...}

  event: done
  data: {}

  event: error
  data: {"code": "...", "message": "..."}

Anti-pattern notes:
  - SSE only (AGENT-05 mandates EventSource; bi-directional transport is out of scope).
  - No auth middleware (Phase 4 / deferred per D-CONTEXT deferred section).
  - Anthropic client is instantiated per-request (not at module import time) to
    avoid eagerly reading ANTHROPIC_API_KEY and to keep the module importable in
    test environments without the key set (Open Question 3 resolved per-request).
  - The trust scanner (scan_buffer from agent/trust.py) is passed as the
    trust_scanner argument to run_turn, wiring the real TRUST-03 enforcement.
  - X-Accel-Buffering: no disables Nginx/proxy buffering (Pitfall 2).

Phase 2 note:
  - conversation_id query param is accepted and validated (T-02-09 input validation)
    but NOT used for DB lookup -- conversations are in-memory for Phase 2.
  - Phase 3 will load the conversation from the Supabase DB here.
"""

import json
import os

import anthropic
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from agent.loop import run_turn
from agent.trust import scan_buffer

router = APIRouter()

# Default model per CLAUDE.md (AI/LLM Layer section); configurable via env var.
_DEFAULT_MODEL = "claude-sonnet-4-5"


async def sse_generator(messages: list[dict], model: str):
    """
    Async generator that drives run_turn and formats each event as an SSE frame.

    Frame format per D-07:
      event: <event_type>\ndata: <json>\n\n

    Error handling: any unexpected exception from run_turn is caught and emitted
    as a final `event: error` frame so the stream never dies silently.
    """
    # Per-request Anthropic client: reads ANTHROPIC_API_KEY from env.
    # Instantiated here (not at module import) so the module is importable without the key.
    client = anthropic.AsyncAnthropic()
    audit_log: list = []

    try:
        async for event in run_turn(messages, client, model, scan_buffer, audit_log):
            event_type = event["event"]
            data = json.dumps(event["data"])
            yield f"event: {event_type}\ndata: {data}\n\n"
    except Exception as exc:  # noqa: BLE001
        error_data = json.dumps({"code": "server_error", "message": str(exc)})
        yield f"event: error\ndata: {error_data}\n\n"


@router.get("/stream")
async def chat_stream(conversation_id: str = Query(...)):
    """
    GET /chat/stream?conversation_id=...

    Returns a server-sent events stream for a conversation turn.

    Phase 2: conversation_id is validated (FastAPI Query type check) but the
    messages history is in-memory only. Phase 3 loads messages from the
    Supabase DB using conversation_id.
    """
    model = os.environ.get("ANTHROPIC_MODEL", _DEFAULT_MODEL)

    # Phase 2: in-memory placeholder messages.
    # Phase 3 will replace this with: messages = await load_conversation(conversation_id)
    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                "Hello! I'm ready to start my cycling training. "
                "What information do you need from me?"
            ),
        }
    ]

    return StreamingResponse(
        sse_generator(messages, model),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx: disables proxy response buffering (Pitfall 2)
        },
    )
