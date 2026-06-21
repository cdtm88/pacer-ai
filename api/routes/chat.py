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

Phase 3 note:
  - conversation_id is now used to load messages from Supabase DB via load_conversation.
  - New messages are NOT persisted here (Phase 4: streaming makes it non-trivial to
    capture new assistant content outside run_turn without refactor). The onboarding
    route handles persistence for onboarding turns; coaching persistence is Phase 4.
"""

import os

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

# run_turn is imported at module scope so tests can monkeypatch chat_module.run_turn.
# Passing run_turn to sse_generator as _run_turn keeps the monkeypatch effective.
from api.agent.loop import run_turn  # noqa: F401 (passed to sse_generator for test compat)
from api.auth import get_current_user
from api.routes._sse import sse_generator
from api.routes.onboarding import create_conversation, load_conversation

router = APIRouter()

# Separate router for /conversations/ prefix (mounted at "" in main.py)
conversations_router = APIRouter()

# Default model per CLAUDE.md (AI/LLM Layer section); configurable via env var.
_DEFAULT_MODEL = "claude-sonnet-4-5"

# Fallback opening message when a conversation has no prior history.
_OPENING_MESSAGE = (
    "Hello! I'm ready to start my cycling training. "
    "What information do you need from me?"
)


@router.get("/stream")
async def chat_stream(
    conversation_id: str = Query(...),
    current_user: dict = Depends(get_current_user),
):
    """
    GET /chat/stream?conversation_id=...&token=<jwt>

    Returns a server-sent events stream for a conversation turn.

    Phase 4: JWT is accepted via header (Authorization: Bearer) or ?token= query
    param for SSE clients (EventSource cannot send headers; Pitfall 1).

    Loads the last 20 messages from the Supabase DB scoped to the authenticated
    user. Falls back to an opening message if the conversation has no history.
    """
    user_id = current_user["user_id"]
    model = os.environ.get("ANTHROPIC_MODEL", _DEFAULT_MODEL)

    # Load last 20 messages from DB scoped to the owning user (defence-in-depth).
    try:
        messages = await load_conversation(conversation_id, user_id=user_id, limit=20)
    except Exception:
        messages = []

    # If no prior messages, seed with the fallback opening message.
    if not messages:
        messages = [{"role": "user", "content": _OPENING_MESSAGE}]

    return StreamingResponse(
        sse_generator(messages, model, _run_turn=run_turn),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx: disables proxy response buffering (Pitfall 2)
        },
    )


@conversations_router.post("/conversations/")
async def create_chat_conversation(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    POST /conversations/

    Creates a new coaching conversation for the authenticated user and returns
    its UUID. Calls the create_conversation helper from onboarding.py with
    context_type='coaching' so the conversation is tagged for the coaching flow.

    user_id is sourced from the verified JWT sub claim (T-04-01).

    Returns: {"conversation_id": str}
    """
    user_id = current_user["user_id"]
    conversation_id = await create_conversation(user_id, context_type="coaching")
    return {"conversation_id": conversation_id}
