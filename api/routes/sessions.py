# api/routes/sessions.py
"""
Session, PMC history, and profile read endpoints for PacerAI Phase 4
(UI-02, UI-04, UI-06, T-04-01, T-04-03).

All endpoints require a valid Supabase JWT via Depends(get_current_user).
user_id is sourced exclusively from the JWT sub claim -- never from a query
param or request body (T-04-01).

Endpoints:
  GET /sessions/today         -- today's session for the authenticated user
  GET /sessions/upcoming      -- next 14 planned sessions (scheduled_date >= today)
  GET /pmc_history/latest     -- most recent PMC row (ctl, atl, tsb, tss_display_ready)
  GET /profiles/me            -- user profile row or 404 when none exists

Router mounting in main.py: app.include_router(sessions_router) with no prefix
so each handler path below is the final URL.
"""

import datetime

from fastapi import APIRouter, Depends, HTTPException

from api.auth import get_current_user
from api.db import get_async_supabase as _get_async_supabase
from api.utils import validate_uuid


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()

# Columns the UI needs from the sessions table
_SESSION_COLUMNS = (
    "id, objective, structure, targets, duration_mins, duration_minutes, "
    "status, scheduled_date, type, zone_targets, power_targets, rpe_target, "
    "tss_target, calendar_event_id"
)


# ---------------------------------------------------------------------------
# GET /sessions/today
# ---------------------------------------------------------------------------


@router.get("/sessions/today")
async def today_session(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    GET /sessions/today

    Returns today's session row for the authenticated user, or an empty dict
    when no session is scheduled for today.

    user_id comes from the verified JWT sub claim (T-04-01). The query filters
    by both user_id and scheduled_date so a user can never read another user's
    sessions (T-04-03).
    """
    user_id = current_user["user_id"]
    today = datetime.date.today().isoformat()
    supabase = await _get_async_supabase()

    result = await (
        supabase.table("sessions")
        .select(_SESSION_COLUMNS)
        .eq("user_id", user_id)
        .eq("scheduled_date", today)
        .execute()
    )

    if result.data:
        return result.data[0]
    return {}


# ---------------------------------------------------------------------------
# GET /sessions/upcoming
# ---------------------------------------------------------------------------


@router.get("/sessions/upcoming")
async def upcoming_sessions(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    GET /sessions/upcoming

    Returns the next 14 planned sessions for the authenticated user,
    ordered by scheduled_date ascending.

    Filters: status = 'planned', scheduled_date >= today.
    """
    user_id = current_user["user_id"]
    today = datetime.date.today().isoformat()
    supabase = await _get_async_supabase()

    result = await (
        supabase.table("sessions")
        .select(_SESSION_COLUMNS)
        .eq("user_id", user_id)
        .eq("status", "planned")
        .gte("scheduled_date", today)
        .order("scheduled_date", desc=False)
        .limit(14)
        .execute()
    )

    return {"sessions": result.data}


# ---------------------------------------------------------------------------
# GET /pmc_history/latest
# ---------------------------------------------------------------------------


@router.get("/pmc_history/latest")
async def latest_pmc(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    GET /pmc_history/latest

    Returns the most recent PMC history row for the authenticated user,
    including tss_display_ready, ctl, atl, tsb, and date.
    Returns an empty dict when no PMC data exists yet (cold-start state).
    """
    user_id = current_user["user_id"]
    supabase = await _get_async_supabase()

    result = await (
        supabase.table("pmc_history")
        .select("id, user_id, date, ctl, atl, tsb, tss_display_ready, created_at")
        .eq("user_id", user_id)
        .order("date", desc=True)
        .limit(1)
        .execute()
    )

    if result.data:
        return result.data[0]
    return {}


# ---------------------------------------------------------------------------
# GET /pmc_history/
# ---------------------------------------------------------------------------


@router.get("/pmc_history/")
async def list_pmc_history(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    GET /pmc_history/

    Returns up to 30 most recent PMC history rows for the authenticated user,
    ordered by date ascending (oldest first) for sparkline rendering.
    Returns empty list when no PMC data exists yet.

    Added in plan 04-06 (Rule 2): required for CtlSparkline CTL trend display.
    """
    user_id = current_user["user_id"]
    supabase = await _get_async_supabase()

    result = await (
        supabase.table("pmc_history")
        .select("id, user_id, date, ctl, atl, tsb, tss_display_ready, created_at")
        .eq("user_id", user_id)
        .order("date", desc=True)
        .limit(30)
        .execute()
    )

    # Reverse to ascending order for sparkline chart
    rows = list(reversed(result.data)) if result.data else []
    return {"history": rows}


# ---------------------------------------------------------------------------
# GET /profiles/me
# ---------------------------------------------------------------------------


@router.get("/profiles/me")
async def profile_me(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    GET /profiles/me

    Returns the profile row for the authenticated user.
    Raises HTTP 404 with structured error when no profile exists (first-run gate).
    """
    user_id = current_user["user_id"]
    supabase = await _get_async_supabase()

    result = await (
        supabase.table("profiles")
        .select("*")
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "profile_not_found", "detail": "No profile for user"},
        )

    return result.data[0]


# ---------------------------------------------------------------------------
# PATCH /sessions/{session_id}
# ---------------------------------------------------------------------------


@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    PATCH /sessions/{session_id}

    Sets the session status to 'completed' for the authenticated user.

    user_id is sourced from the verified JWT sub claim (T-04-01) -- never from
    a path, query, or request body param. The update filters by both id and
    user_id so a user can never complete another user's session (T-04-03).

    Returns the updated session row on success.
    Raises HTTP 400 if session_id is not a valid UUID.
    Raises HTTP 404 when no session matches (non-existent or wrong user).
    """
    user_id = current_user["user_id"]
    validate_uuid(session_id, "session_id")
    supabase = await _get_async_supabase()

    result = await (
        supabase.table("sessions")
        .update({"status": "completed"})
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "session_not_found",
                "detail": "No session found for this user with the given id",
            },
        )

    return result.data[0]
