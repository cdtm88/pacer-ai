# sports_science/capability_gap.py
"""
TOOL-08: Capability-gap logging sentinel.

Logs missing-tool events to the capability_gaps table and returns a generic,
user-safe fallback message. The internal method_name goes to the DB only
and must never appear in the user-facing response (GAP-03).

DB writes use the SERVICE_ROLE_KEY to bypass RLS (Pitfall 6, D-07).
Never use the anon key for backend writes. Never expose this key to frontend.
"""
import os
from supabase import create_client, Client
from .types import ToolResult


def _get_supabase() -> Client:
    """Return a Supabase client using the service-role key (bypasses RLS for backend writes)."""
    url = os.environ.get("SUPABASE_URL")
    # Service-role key is required for backend inserts that bypass RLS (Pitfall 6).
    # NEVER expose this key to any frontend or client-side code.
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
        )
    return create_client(url, key)


def log_capability_gap(
    method_name: str,
    context: dict,
    user_id: str | None = None,
) -> ToolResult:
    """
    TOOL-08: Log a capability gap to DB and return a user-safe fallback message.

    Args:
        method_name: Internal function name the agent tried to call (e.g. "estimate_vo2max").
                     Goes to DB only — never surfaced to user (GAP-03).
        context:     Contextual data at the time of the gap (e.g. ride metrics, user state).
                     Key names are recorded in the ToolResult.inputs; values stay in DB.
        user_id:     Optional user UUID. Nullable so gaps can be logged pre-auth.

    Returns:
        ToolResult with a generic user-facing message. The value["message"] must NOT
        contain method_name (GAP-03). This function never computes a physiological
        number — it only logs and returns a fallback (GAP-02).
    """
    try:
        supabase = _get_supabase()
        supabase.table("capability_gaps").insert({
            "user_id": user_id,
            "method_name": method_name,
            "description": f"Missing tool: {method_name}",
            "context": context,
        }).execute()
    except Exception:
        pass  # gap logging is best-effort; never block the fallback response

    # GAP-03: generic user-facing message; method_name goes to DB only.
    # This message is intentionally vague — it must not expose internal function names.
    user_message = (
        "I don't have a specialized tool for that calculation yet. "
        "I've logged it for the development team. "
        "I'll use a qualitative approach for now."
    )

    return ToolResult(
        value={"status": "logged", "message": user_message},
        unit="",
        methodology="capability_gap_log",
        # Only key names in inputs — never values or secrets (security: no data leakage)
        inputs={"context_keys": list(context.keys())},
    )
