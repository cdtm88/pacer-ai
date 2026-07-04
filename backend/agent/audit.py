# backend/agent/audit.py
"""
TRUST-06 / TRUST-04: durable, verifiable per-tool-call audit trail.

write_audit_entry persists one audit_log row per tool dispatch (best-effort;
mirrors backend/sports_science/capability_gap.py's proven try/except: pass
shape so a DB outage degrades to "no audit row", never "tool call fails",
D-14). load_prior_audit_values re-loads a conversation's prior tool results
as JSON strings, which is the persisted source D-04's cross-turn
tool_result_values seeding reads from (the messages table never receives
tool_result content -- see 08-RESEARCH.md Pitfall 1).

Client acquisition uses the already-centralized backend.db.get_async_supabase()
(WR-003) -- this module intentionally does NOT define its own module-level
client-cache singleton (that would regress WR-003's consolidation).
"""
import json

from backend.db import get_async_supabase


async def write_audit_entry(
    user_id: str | None,
    conversation_id: str | None,
    tool_use_id: str,
    tool_name: str,
    inputs: dict,
    result: dict | None,
    is_error: bool,
) -> None:
    """
    Insert one best-effort audit_log row for a single tool dispatch.

    Never raises -- a DB write failure must not break the user-facing
    tool-call flow (D-14): the internal try/except always swallows the
    exception, so `await write_audit_entry(...)` completes normally (never
    propagates, never blocks indefinitely) regardless of DB outcome.

    WR-03: every call site in dispatch_tool does `await write_audit_entry(...)`
    synchronously, in-line with the tool dispatch, and that is the correct,
    intended usage -- NOT fire-and-forget (e.g. asyncio.create_task). Awaiting
    it keeps audit writes ordered relative to the tool_result response and to
    each other; a genuinely fire-and-forget call would risk reordering audit
    writes across concurrent tool dispatches (D-12's asyncio.gather) with no
    corresponding benefit, since this function already never raises or blocks
    the caller on error.

    Args:
        user_id:         Authenticated user UUID, or None if unresolved
                          (some tool calls precede auth resolution).
        conversation_id: Conversation UUID this dispatch belongs to, or None
                          if the call site does not yet thread one.
        tool_use_id:     The Anthropic tool_use block's id.
        tool_name:       The dispatched tool's name.
        inputs:          The (post server-side-injection) tool call inputs.
        result:          The ToolResult payload (or None on error).
        is_error:        Whether the tool call resulted in an error.
    """
    try:
        supabase = await get_async_supabase()
        await supabase.table("audit_log").insert({
            "user_id": user_id,
            "conversation_id": conversation_id,
            "tool_use_id": tool_use_id,
            "tool_name": tool_name,
            "inputs": inputs,
            "result": result,
            "is_error": is_error,
        }).execute()
    except Exception:
        pass  # best-effort; mirrors capability_gap.py (D-14)


async def load_prior_audit_values(
    conversation_id: str,
    user_id: str | None = None,
) -> list[str]:
    """
    Reload prior tool-result JSON strings for a conversation (D-04 seeding).

    Scoped by conversation_id and (defence-in-depth) user_id, ordered by
    created_at ascending. Returns the JSON-serialised `result` of each row
    that has one; error rows with a null result are skipped, not serialised
    as the string "null".

    Re-enforces .eq('user_id', user_id) at the app layer on top of the
    audit_log RLS policy (user_id = auth.uid()), matching the ownership
    check already established by
    backend/routes/onboarding.py::load_conversation (T-08-03 mitigation).

    Never raises -- returns [] on any failure (a broken reload degrades to
    "no prior context seeded", not a turn-breaking exception).

    Args:
        conversation_id: Conversation UUID to scope the reload to.
        user_id:         Authenticated user UUID; when provided, re-enforces
                          ownership at the application layer.

    Returns:
        List of JSON strings (one per row with a non-null result), oldest
        first.
    """
    try:
        supabase = await get_async_supabase()
        query = (
            supabase.table("audit_log")
            .select("result")
            .eq("conversation_id", conversation_id)
        )
        if user_id is not None:
            query = query.eq("user_id", user_id)
        result = await query.order("created_at").execute()
        rows = result.data or []
        return [
            json.dumps(row["result"])
            for row in rows
            if row.get("result") is not None
        ]
    except Exception:
        return []
