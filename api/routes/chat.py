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

import os

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

# run_turn is imported at module scope so tests can monkeypatch chat_module.run_turn.
# The monkeypatch reaches _sse.py via the shared import; keeping it here ensures
# the existing test_sse.py monkeypatch target (chat_module.run_turn) still resolves.
from agent.loop import run_turn  # noqa: F401 (re-exported for test monkeypatching)
from api.routes._sse import sse_generator

router = APIRouter()

# Default model per CLAUDE.md (AI/LLM Layer section); configurable via env var.
_DEFAULT_MODEL = "claude-sonnet-4-5"


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
        sse_generator(messages, model, _run_turn=run_turn),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx: disables proxy response buffering (Pitfall 2)
        },
    )
