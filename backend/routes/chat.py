# api/routes/chat.py
"""
SSE chat endpoint for PacerAI (AGENT-05, D-07, D-08).

GET /chat/stream?conversation_id=...&message=...

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
  - Anthropic client is instantiated per-request (not at module import time) to
    avoid eagerly reading ANTHROPIC_API_KEY and to keep the module importable in
    test environments without the key set (Open Question 3 resolved per-request).
  - The trust scanner (scan_buffer from agent/trust.py) is passed as the
    trust_scanner argument to run_turn, wiring the real TRUST-03 enforcement.
  - X-Accel-Buffering: no disables Nginx/proxy buffering (Pitfall 2).

Phase 4 note (04-13):
  - message query param is now read and appended to conversation history so the
    agent responds to the user's actual typed message (UAT GAP 5 closed).
  - Both the user message and the assistant reply are persisted via save_messages
    after the stream completes, using the assistant_sink mechanism from 04-12.
"""

import os

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

# run_turn is imported at module scope so tests can monkeypatch chat_module.run_turn.
# Passing run_turn to sse_generator as _run_turn keeps the monkeypatch effective.
from backend.agent.loop import run_turn  # noqa: F401 (passed to sse_generator for test compat)
from backend.auth import get_current_user
from backend.routes._sse import sse_generator
from backend.routes.onboarding import create_conversation, load_conversation, save_messages

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
    message: str | None = Query(None),
    current_user: dict = Depends(get_current_user),
):
    """
    GET /chat/stream?conversation_id=...&message=...&token=<jwt>

    Returns a server-sent events stream for a conversation turn.

    Phase 4: JWT is accepted via header (Authorization: Bearer) or ?token= query
    param for SSE clients (EventSource cannot send headers; Pitfall 1).

    Loads the last 20 messages from the Supabase DB scoped to the authenticated
    user. Appends the incoming user message to the history before streaming so
    the agent responds to the actual user input (UAT GAP 5). Falls back to an
    opening message only when there is no prior history and no incoming message.

    After the stream completes, persists the user message and assistant reply via
    save_messages (best-effort; a persistence failure never breaks the response).
    """
    user_id = current_user["user_id"]
    model = os.environ.get("ANTHROPIC_MODEL", _DEFAULT_MODEL)

    # Load last 20 messages from DB scoped to the owning user (defence-in-depth).
    try:
        messages = await load_conversation(conversation_id, user_id=user_id, limit=20)
    except Exception:
        messages = []

    # Append the incoming user message to history when present.
    if message:
        messages.append({"role": "user", "content": message})
    elif not messages:
        # No prior history and no incoming message: seed with the fallback opening.
        messages = [{"role": "user", "content": _OPENING_MESSAGE}]

    async def _stream_and_persist():
        """Yield SSE chunks and persist the new turns after the stream completes."""
        assistant_sink: list[str] = []
        async for chunk in sse_generator(messages, model, _run_turn=run_turn, assistant_sink=assistant_sink):
            yield chunk
        # Persist both turns after the stream is done (best-effort).
        try:
            new_turns: list[dict] = []
            if message:
                new_turns.append({"role": "user", "content": message})
            if assistant_sink and assistant_sink[0]:
                new_turns.append({"role": "assistant", "content": assistant_sink[0]})
            if new_turns:
                await save_messages(conversation_id, user_id, new_turns)
        except Exception:
            pass  # best-effort; persistence failure must not surface on the completed stream

    return StreamingResponse(
        _stream_and_persist(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
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
