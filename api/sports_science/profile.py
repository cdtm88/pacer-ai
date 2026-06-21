# sports_science/profile.py
"""
TOOL-10: User profile persistence.

Persists onboarding interview data to the profiles table via Supabase.
Uses the same async singleton pattern as capability_gap.py (WR-04).
Uses SERVICE_ROLE_KEY to bypass RLS -- never expose to frontend.

D-03 gate: The LLM schema description for save_profile mandates that this
tool is only called after the user has explicitly approved the summary.
This function does not enforce the gate -- it is enforced by the schema
description and the agent's tool-calling discipline.
"""
import os
from typing import Optional
from supabase import acreate_client, AsyncClient
from .types import ToolResult

# WR-04: Module-level cached client. None until first call; then reused.
# Avoids creating a new httpx.AsyncClient on every save_profile call.
_supabase_client: Optional[AsyncClient] = None


async def _get_async_supabase() -> AsyncClient:
    """
    Return a cached async Supabase client using the service-role key (bypasses RLS).

    WR-04: Creates the client once and reuses it across calls to avoid
    leaking httpx connection pools.
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


async def save_profile(
    user_id: str,
    fitness_goals: str,
    weekly_hours: float,
    preferred_days: list[str],
    back_status: str,
    equipment: dict,
    rpe_baseline: str,
    lthr_estimate: float | None = None,
) -> ToolResult:
    """
    TOOL-10: Persist onboarding interview data to the profiles table.

    Maps back_status to a constraints JSONB object:
      moderate -> {"back_issues": True, "load_ramp_flag_threshold_pct": 10}
      mild     -> {"back_issues": True}
      none     -> {"back_issues": False}

    Upserts on conflict with user_id (profiles_user_id_unique constraint).

    Args:
        user_id:        User UUID.
        fitness_goals:  User's stated fitness goals (free text).
        weekly_hours:   Available training hours per week.
        preferred_days: Preferred training days (e.g. ["Tuesday", "Thursday"]).
        back_status:    "none" | "mild" | "moderate" (D-05 gate).
        equipment:      Training equipment dict (e.g. {"trainer": "Wahoo Kickr Core"}).
        rpe_baseline:   Self-reported RPE baseline (e.g. "beginner").
        lthr_estimate:  Lactate Threshold Heart Rate estimate in bpm (optional).

    Returns:
        ToolResult with profile_id and saved=True.
    """
    # Map back_status to constraints JSONB (D-05)
    if back_status == "moderate":
        constraints = {"back_issues": True, "load_ramp_flag_threshold_pct": 10}
    elif back_status == "mild":
        constraints = {"back_issues": True}
    else:
        constraints = {"back_issues": False}

    supabase = await _get_async_supabase()
    result = await supabase.table("profiles").upsert(
        {
            "user_id": user_id,
            "fitness_goals": fitness_goals,
            "weekly_hours": weekly_hours,
            "preferred_days": preferred_days,
            "back_status": back_status,
            "equipment": equipment,
            "rpe_baseline": rpe_baseline,
            "lthr_estimate": lthr_estimate,
            "constraints": constraints,
        },
        on_conflict="user_id",
    ).execute()

    return ToolResult(
        value={"profile_id": result.data[0]["id"], "saved": True},
        unit="",
        methodology="profile_persistence",
        inputs={
            "user_id": user_id,
            "back_status": back_status,
            "weekly_hours": weekly_hours,
        },
    )
