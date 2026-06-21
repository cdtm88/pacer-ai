# api/routes/onboarding.py
"""
Onboarding interview entry point for PacerAI (ONBD-01 through ONBD-04).

POST /onboarding/start

Returns a text/event-stream SSE response that drives the agent through a
structured interview to collect 6 required profile fields, then gates
save_profile on explicit user approval (D-03 / ONBD-04).

The ONBOARDING_SYSTEM_PROMPT instructs the agent to:
  1. Collect exactly 6 fields (fitness_goals, weekly_hours, preferred_days,
     back_status, equipment, rpe_baseline) through natural conversation (D-02).
  2. Present a plain-text confirmation summary beginning "Here is what I have"
     and WAIT for explicit user approval before calling save_profile (D-03).
  3. Call save_profile ONLY after approval, then call progress_load and
     calculate_hr_zones BEFORE calling generate_plan (D-08 tool order).
  4. Never emit a physiological number without a prior tool call (TRUST-04).

Conversation persistence (Phase 3 upgrade):
  - create_conversation: inserts a conversations row with context_type, returns id
  - load_conversation: SELECT last 20 messages by conversation_id (Phase 4 token
    truncation is deferred -- see TODO comment in load_conversation)
  - save_messages: INSERT new messages to the messages table for audit trail

Architecture notes:
  - Supabase singleton reuses the exact pattern from sports_science/capability_gap.py
    (WR-04: module-level cached client, SERVICE_ROLE_KEY, bypasses RLS).
  - run_turn is imported at module scope so tests can monkeypatch onboarding_module.run_turn.
  - sse_generator is imported from api.routes._sse (no duplication per key_links).
"""

import json
import os

import anthropic
from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel as _PydanticBaseModel

from api.agent.loop import run_turn  # noqa: F401 -- module-scope import for test monkeypatching
from api.agent.trust import scan_buffer
from api.auth import get_current_user
from api.calendar_sync import push_all_sessions_to_calendar
from api.db import get_async_supabase as _get_async_supabase
from api.routes._sse import sse_generator

router = APIRouter()

# Default model per CLAUDE.md (AI/LLM Layer section); configurable via env var.
_DEFAULT_MODEL = "claude-sonnet-4-5"

# ---------------------------------------------------------------------------
# Onboarding system prompt (D-22 dynamic prompt injection)
# ---------------------------------------------------------------------------

ONBOARDING_SYSTEM_PROMPT = (
    "You are PacerAI, an evidence-based adaptive cycling coach conducting a structured "
    "onboarding interview. Your task is to collect exactly 6 required fields from the user "
    "through natural, conversational questioning. Ask one or two questions at a time; "
    "do not overwhelm the user with a list.\n\n"
    "The 6 required fields are:\n"
    "  1. fitness_goals -- What the user wants to achieve (e.g., general fitness, weight loss)\n"
    "  2. weekly_hours -- How many hours per week they can commit to training\n"
    "  3. preferred_days -- Which days of the week they prefer to train\n"
    "  4. back_status -- Whether they have back issues; if yes, ask severity: "
    "none, mild (occasional discomfort), or moderate (regular pain or medical advice to limit load)\n"
    "  5. equipment -- Confirm their training setup; for most users this will be a "
    "Wahoo Kickr Core trainer with Zwift. Confirm this with the user.\n"
    "  6. rpe_baseline -- Their self-reported fitness baseline: beginner (just getting started), "
    "moderate (some recent activity), or fit (consistently active)\n\n"
    "GATE: After collecting all 6 fields, present a plain-text summary to the user beginning "
    "with exactly: 'Here is what I have' -- list all 6 values clearly. "
    "Then WAIT for the user to explicitly confirm (e.g., 'yes', 'looks good', 'correct'). "
    "Do NOT call save_profile until the user has given explicit approval. "
    "This is a mandatory confirmation gate (D-03 / ONBD-04).\n\n"
    "TOOL ORDER after approval (D-08): call save_profile first, then progress_load, "
    "then calculate_hr_zones, then generate_plan. Never skip this order.\n\n"
    "TRUST RULE: You MUST call a tool for any physiological number "
    "(power zones, TSS, FTP, CTL, ATL, TSB, heart-rate zones). "
    "Never emit a physiological number from your own reasoning. "
    "If no tool covers the needed calculation, call log_capability_gap."
)

# ---------------------------------------------------------------------------
# Conversation persistence helpers
# ---------------------------------------------------------------------------


async def create_conversation(user_id: str, context_type: str) -> str:
    """
    Insert a conversations row with the given context_type and return the new UUID.

    Args:
        user_id:      User UUID (the conversation owner).
        context_type: 'onboarding' | 'coaching' (D-21).

    Returns:
        The new conversation UUID string.
    """
    supabase = await _get_async_supabase()
    result = await supabase.table("conversations").insert(
        {"user_id": user_id, "context_type": context_type}
    ).execute()
    return result.data[0]["id"]


async def load_conversation(conversation_id: str, user_id: str, limit: int = 20) -> list[dict]:
    """
    Load the last `limit` messages for a conversation from the messages table.

    Returns messages in chronological order (oldest first), mapped to
    {role, content} dicts suitable for the Anthropic messages API.

    user_id is required and filters the query — even though the service-role key
    bypasses RLS, this re-enforces the ownership constraint at the application layer
    so a conversation_id from a different user returns no rows (defence-in-depth).
    Phase 4 auth middleware will validate that user_id matches a verified JWT principal.

    TODO (Phase 4): Replace the hard limit=20 row cap with a token-count
    truncation strategy so long interviews don't silently drop early context.
    See RESEARCH.md Open Question 5 (token-count truncation deferral).

    Args:
        conversation_id: UUID of the conversation to load.
        user_id:         UUID of the authenticated user (ownership filter).
        limit:           Maximum number of most-recent messages to return (default 20).

    Returns:
        List of {role: str, content: str} dicts in chronological order.
        Empty list if no messages exist for this conversation / user pair.
    """
    supabase = await _get_async_supabase()
    result = await (
        supabase.table("messages")
        .select("role, content, created_at")
        .eq("conversation_id", conversation_id)
        .eq("user_id", user_id)  # re-enforce ownership at app layer (defence-in-depth)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    # Result is DESC (newest first); reverse to get chronological order.
    rows = list(reversed(result.data))
    return [{"role": row["role"], "content": row["content"]} for row in rows]


async def save_messages(
    conversation_id: str, user_id: str, new_messages: list[dict]
) -> None:
    """
    Persist new messages to the messages table for audit trail (T-03-10).

    Args:
        conversation_id: UUID of the parent conversation.
        user_id:         UUID of the message author (for RLS ownership).
        new_messages:    List of {role, content} dicts to persist.
                         Typically the new turns added during a run_turn call.
    """
    if not new_messages:
        return

    supabase = await _get_async_supabase()
    rows = [
        {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "role": msg["role"],
            "content": msg["content"] if isinstance(msg["content"], str) else json.dumps(msg["content"]),
        }
        for msg in new_messages
    ]
    await supabase.table("messages").insert(rows).execute()


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post("/plan-calendar-sync")
async def onboarding_plan_calendar_sync(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    POST /onboarding/plan-calendar-sync

    Called by the frontend after the onboarding agent finishes generating the
    initial plan and sessions are persisted to the database (CAL-01).

    Fire-and-forget: pushes all planned sessions for this user to Google Calendar
    as background work. A calendar failure never blocks this endpoint (CAL-04).
    The helper is a no-op when the user has not connected Google Calendar.

    Returns immediately with {"status": "scheduled"}.
    """
    user_id = current_user["user_id"]
    # Register the push with FastAPI's BackgroundTasks so it runs after the
    # response is sent and is tied to the worker's event loop lifecycle (CR-003).
    background_tasks.add_task(push_all_sessions_to_calendar, user_id)
    return {"status": "scheduled"}


class OnboardingStartBody(_PydanticBaseModel):
    """Request body for POST /onboarding/start (WR-005)."""
    message: str | None = None
    conversation_id: str | None = None


@router.post("/start")
async def onboarding_start(
    body: OnboardingStartBody = OnboardingStartBody(),
    current_user: dict = Depends(get_current_user),
):
    """
    POST /onboarding/start

    Starts or continues an onboarding interview. Accepts an optional
    `conversation_id` to resume a prior session -- when absent, a new
    conversation is created (WR-005: multi-turn context preservation).

    The response begins with a `metadata` SSE event carrying the
    `conversation_id` so the frontend can store it and send it back on
    subsequent turns.

    Phase 4: JWT is accepted via Authorization: Bearer header or ?token= query
    param for SSE clients. user_id is sourced exclusively from the verified JWT sub claim.

    Returns:
        StreamingResponse (text/event-stream) of SSE frames.
    """
    user_id = current_user["user_id"]
    model = os.environ.get("ANTHROPIC_MODEL", _DEFAULT_MODEL)

    # Seed the conversation with the canonical opening user message.
    # The agent's first response will be the interview opener.
    seed_messages: list[dict] = [
        {"role": "user", "content": "I'd like to start my training interview."}
    ]

    # WR-005: reuse the supplied conversation_id when provided; create a new one otherwise.
    conversation_id: str | None = body.conversation_id
    if conversation_id is None:
        try:
            conversation_id = await create_conversation(user_id, context_type="onboarding")
        except Exception:
            pass  # best-effort; stream will proceed without persistence

    # Load prior turns when conversation_id is available; fall back to seed on new conversations.
    if conversation_id is not None:
        try:
            prior_turns = await load_conversation(conversation_id, user_id)
        except Exception:
            prior_turns = []
        # Append the incoming user message to prior context if provided.
        if body.message:
            prior_turns.append({"role": "user", "content": body.message})
        messages: list[dict] = prior_turns if prior_turns else seed_messages
    else:
        messages = seed_messages

    async def _stream_with_metadata():
        """Yield a metadata event first, then the full SSE generator output."""
        # Send conversation_id to the client so it can pass it back on subsequent turns.
        if conversation_id:
            yield f"event: metadata\ndata: {json.dumps({'conversation_id': conversation_id})}\n\n"
        async for chunk in sse_generator(messages, model, system_prompt=ONBOARDING_SYSTEM_PROMPT, _run_turn=run_turn):
            yield chunk

    return StreamingResponse(
        _stream_with_metadata(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Nginx: disables proxy response buffering (Pitfall 2)
        },
    )
