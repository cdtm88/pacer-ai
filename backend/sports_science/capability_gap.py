# sports_science/capability_gap.py
"""
TOOL-08: Capability-gap logging sentinel.

Logs missing-tool events to the capability_gaps table and returns a generic,
user-safe fallback message. The internal method_name goes to the DB only
and must never appear in the user-facing response (GAP-03).

DB writes use the SERVICE_ROLE_KEY to bypass RLS.
Never use the anon key for backend writes. Never expose this key to frontend.

Phase 2 upgrade: async Supabase client via acreate_client (D-06, TRUST-05).
WR-04: module-level singleton client to avoid creating a new connection pool
on every log_capability_gap call (connection leak fix).
"""
import logging
import os
from typing import Optional

from supabase import AsyncClient, acreate_client

from .types import ToolResult

logger = logging.getLogger(__name__)

# WR-04: Module-level cached client. None until first call; then reused.
# This avoids creating a new httpx.AsyncClient (and connection pool) on
# every log_capability_gap invocation. The long-term fix (Phase 3) is to
# initialize this in the FastAPI lifespan and inject it.
_supabase_client: Optional[AsyncClient] = None


def _reset_client_for_tests() -> None:
    """Test-only seam: clear the module-level client cache.

    Without this, a client cached by an earlier test (e.g. a working mock)
    is returned instead of a later test's freshly-patched client, making
    DB-failure regression tests order-dependent and non-exercising. Invoked
    from an autouse conftest fixture before (and after) each test.
    """
    global _supabase_client
    _supabase_client = None


async def _get_async_supabase() -> AsyncClient:
    """
    Return a cached async Supabase client using the service-role key (bypasses RLS).

    WR-04: Creates the client once and reuses it across calls to avoid
    leaking httpx connection pools. The singleton is module-level and is
    never explicitly closed (acceptable for a long-lived server process;
    the OS reclaims connections on process exit).
    """
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client

    url = os.environ.get("SUPABASE_URL")
    # Service-role key is required for backend inserts that bypass RLS.
    # NEVER expose this key to any frontend or client-side code.
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
        )
    _supabase_client = await acreate_client(url, key)
    return _supabase_client


async def log_capability_gap(
    method_name: str,
    context: dict,
    user_id: str | None = None,
) -> ToolResult:
    """
    TOOL-08: Log a capability gap to DB and return a user-safe fallback message.

    Args:
        method_name: Internal function name the agent tried to call.
                     Goes to DB only -- never surfaced to user (GAP-03).
        context:     Contextual data at the time of the gap.
                     Key names are recorded in the ToolResult.inputs; values stay in DB.
        user_id:     Optional user UUID. Nullable so gaps can be logged pre-auth.

    Returns:
        ToolResult with a generic user-facing message. The value["message"] must NOT
        contain method_name (GAP-03). This function never computes a physiological
        number -- it only logs and returns a fallback (GAP-02).
    """
    try:
        supabase = await _get_async_supabase()
        await supabase.table("capability_gaps").insert({
            "user_id": user_id,
            "method_name": method_name,
            "description": f"Missing tool: {method_name}",
            "context": context,
        }).execute()
    except Exception:
        # Gap logging is best-effort; never re-raise or block the fallback
        # response. But a swallowed DB failure must still be observable as
        # backend telemetry (GAP-01) -- method_name in this log line is
        # backend-only and never reaches value["message"] (GAP-03).
        logger.exception(
            "log_capability_gap: DB insert failed for method_name=%s", method_name
        )

    # GAP-03: generic user-facing message; method_name goes to DB only.
    # This message is intentionally vague -- it must not expose internal function names.
    user_message = (
        "I don't have a specialized tool for that calculation yet. "
        "I've logged it for the development team. "
        "I'll use a qualitative approach for now."
    )

    return ToolResult(
        value={"status": "logged", "message": user_message},
        unit="",
        methodology="capability_gap_log",
        # Only key names in inputs -- never values or secrets (security: no data leakage)
        inputs={"context_keys": list(context.keys())},
    )
