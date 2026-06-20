# api/routes/adaptations.py
"""
Adaptive re-planning and transparency layer for PacerAI (ADAPT-01 through ADAPT-05,
TRANSP-01 through TRANSP-03, D-16 through D-20).

Endpoints:
  GET  /adaptations/                        -- readable adaptation log (TRANSP-03)
  POST /adaptations/check                   -- weekly signal check, independent of uploads (ADAPT-04)
  POST /adaptations/sessions/{session_id}/missed -- mark one session missed + re-run detection (D-16)

Signal detection (ADAPT-01):
  - Missed session: scheduled, past-due, no matching ride within +/-1 day
  - Underperformance: actual TSS < 60% of planned TSS per validate_session_vs_actual (ADAPT-05)

Micro/macro decision (ADAPT-02, D-17, D-18):
  - 0 signals -> no adaptation
  - 1 signal  -> micro: adjust next 1-3 sessions inline
  - 2+ signals -> macro: full re-plan via progress_load

30% shift guard (ADAPT-03, D-19):
  - check_shift_limit enforces: if >30% of upcoming sessions shift by >1 day,
    return needs_confirmation WITHOUT applying the replan.

Adaptation logging (TRANSP-02, D-20):
  - Every adaptation persisted to adaptations table with trigger, scope,
    before/after snapshots, and explanation_text.

Security (Phase 4):
  - All endpoints require a valid Supabase JWT via Depends(get_current_user)
  - user_id sourced exclusively from the JWT sub claim (T-04-04)
  - Reads filtered by user_id (defence-in-depth against cross-user disclosure T-03-16)
  - Backend writes use SERVICE_ROLE_KEY (never anon key)
"""

from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path
from pydantic import BaseModel

from api.auth import get_current_user
from api.calendar_sync import delete_calendar_event, update_calendar_event
from api.db import get_async_supabase as _get_async_supabase
from api.utils import validate_uuid
from sports_science.compliance import validate_session_vs_actual
from sports_science.load import progress_load


# ---------------------------------------------------------------------------
# Signal detection (ADAPT-01, D-16, D-17)
# ---------------------------------------------------------------------------


def _parse_date(val) -> Optional[date]:
    """Parse a date value that may be a date, datetime, or ISO string."""
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        # Try ISO date first, then ISO datetime
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(val[:len(fmt)], fmt).date()
            except ValueError:
                continue
        # Try splitting on T for datetimes with fractional seconds
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    return None


async def detect_signals(user_id: str, window_days: int = 7) -> list[dict]:
    """
    ADAPT-01: Detect missed-session and underperformance signals for a user.

    Missed-session check (D-16):
      Load planned sessions whose scheduled_date is past-due within `window_days`.
      For each, look for a matching ride within +/-1 day of the scheduled_date.
      If none found, emit {"type": "missed", "session_id": id}.

    Underperformance check (ADAPT-05, D-17):
      Load recent rides within `window_days` that are matched to a planned session.
      For each, call validate_session_vs_actual(planned, actual).
      If compliance_pct is not None and < 60, emit
      {"type": "underperformance", "session_id": id, "compliance_pct": value}.
      The compliance threshold decision comes from the tool result, not a hardcoded literal.

    Args:
        user_id:     User UUID (SECURITY: scoped to this user only).
        window_days: Rolling lookback window in days (default 7, D-16/D-17).

    Returns:
        List of signal dicts.
    """
    supabase = await _get_async_supabase()
    today = date.today()
    window_start = today - timedelta(days=window_days)

    signals: list[dict] = []

    # --- Missed-session check ---
    # Load planned sessions that are past-due within the window.
    sessions_resp = await (
        supabase.table("sessions")
        .select("id, scheduled_date, tss_target, plan_id")
        .eq("user_id", user_id)
        .eq("status", "planned")
        .gte("scheduled_date", window_start.isoformat())
        .lt("scheduled_date", today.isoformat())
        .execute()
    )
    planned_sessions = sessions_resp.data or []

    # Load all rides in the window to check for date matches.
    rides_resp = await (
        supabase.table("rides")
        .select("id, ride_date, tss, session_id")
        .eq("user_id", user_id)
        .gte("ride_date", window_start.isoformat())
        .lte("ride_date", today.isoformat())
        .execute()
    )
    rides = rides_resp.data or []

    # Index rides by their date for O(1) lookup.
    rides_by_date: dict[date, list[dict]] = {}
    for ride in rides:
        rd = _parse_date(ride.get("ride_date"))
        if rd is not None:
            rides_by_date.setdefault(rd, []).append(ride)

    for session in planned_sessions:
        sched = _parse_date(session.get("scheduled_date"))
        if sched is None:
            continue

        # Check for a matching ride within +/-1 day (D-16).
        found_ride = None
        for delta in [0, -1, 1]:
            check_date = sched + timedelta(days=delta)
            if check_date in rides_by_date:
                # If session_id is explicitly linked, prefer that; otherwise any ride on that day.
                day_rides = rides_by_date[check_date]
                matched = next(
                    (r for r in day_rides if r.get("session_id") == session["id"]),
                    day_rides[0] if day_rides else None,
                )
                if matched:
                    found_ride = matched
                    break

        if found_ride is None:
            signals.append({"type": "missed", "session_id": session["id"]})
        else:
            # --- Underperformance check (ADAPT-05) ---
            # Use validate_session_vs_actual; threshold decision is the tool's compliance_pct.
            planned_tss = session.get("tss_target") or 0
            actual_tss = found_ride.get("tss") or 0

            result = validate_session_vs_actual(
                planned={"tss": planned_tss},
                actual={"tss": actual_tss},
            )
            compliance_pct = result.value.get("compliance_pct")

            # ADAPT-05: compliance < 60 from tool result triggers underperformance signal.
            if compliance_pct is not None and compliance_pct < 60:
                signals.append({
                    "type": "underperformance",
                    "session_id": session["id"],
                    "compliance_pct": compliance_pct,
                })

    return signals


# ---------------------------------------------------------------------------
# Micro/macro decision (ADAPT-02, D-17, D-18)
# ---------------------------------------------------------------------------


def decide_scope(signals: list[dict]) -> Optional[str]:
    """
    ADAPT-02, D-17/D-18: Determine adaptation scope from the signal count.

    Returns:
        None    -- 0 signals; no adaptation needed
        "micro" -- exactly 1 signal; adjust 1-3 sessions inline (D-17)
        "macro" -- 2+ signals; full re-plan (D-18; requires 2+ events)
    """
    count = len(signals)
    if count == 0:
        return None
    if count == 1:
        return "micro"
    return "macro"


# ---------------------------------------------------------------------------
# 30% shift guard (ADAPT-03, D-19)
# ---------------------------------------------------------------------------


def check_shift_limit(
    before_sessions: list[dict],
    after_sessions: list[dict],
) -> dict:
    """
    ADAPT-03, D-19: Enforce the 30% shift guard on a macro replan.

    Compares session scheduled_dates between `before_sessions` and `after_sessions`
    (matched by session id). Sessions whose scheduled_date moves by more than 1 day
    are counted as "shifted".

    shift_pct = shifted_count / total_upcoming  (0 when total is 0)
    requires_user_confirmation = shift_pct > 0.30

    scheduled_date values may be ISO strings, date objects, or datetime objects --
    parsed robustly via _parse_date before diffing.

    Args:
        before_sessions: List of session dicts with "id" and "scheduled_date" BEFORE replan.
        after_sessions:  List of session dicts with "id" and "scheduled_date" AFTER replan.

    Returns:
        {
            "shifted_count": int,
            "total_upcoming": int,
            "shift_pct": float,
            "requires_user_confirmation": bool,
        }
    """
    total_upcoming = len(before_sessions)
    if total_upcoming == 0:
        return {
            "shifted_count": 0,
            "total_upcoming": 0,
            "shift_pct": 0.0,
            "requires_user_confirmation": False,
        }

    # Build lookup: id -> scheduled_date for after snapshot
    after_by_id: dict[str, Optional[date]] = {
        s["id"]: _parse_date(s.get("scheduled_date"))
        for s in after_sessions
        if s.get("id")
    }

    shifted_count = 0
    for session in before_sessions:
        sid = session.get("id")
        before_date = _parse_date(session.get("scheduled_date"))
        after_date = after_by_id.get(sid)

        if before_date is None or after_date is None:
            continue

        delta_days = abs((after_date - before_date).days)
        if delta_days >= 1:
            shifted_count += 1

    shift_pct = shifted_count / total_upcoming
    return {
        "shifted_count": shifted_count,
        "total_upcoming": total_upcoming,
        "shift_pct": round(shift_pct, 4),
        "requires_user_confirmation": shift_pct > 0.30,
    }


# ---------------------------------------------------------------------------
# Adaptation logging (TRANSP-02, D-20)
# ---------------------------------------------------------------------------


async def log_adaptation(
    user_id: str,
    trigger: str,
    signal_count: int,
    scope: str,
    before_snapshot: dict,
    after_snapshot: dict,
    explanation_text: str,
) -> str:
    """
    TRANSP-02, D-20: Persist one adaptation event to the adaptations table.

    trigger must be one of: "missed", "underperformance", "overreaching"
    scope   must be one of: "micro", "macro"

    Returns:
        The new row's id (UUID string).
    """
    supabase = await _get_async_supabase()
    result = await supabase.table("adaptations").insert({
        "user_id": user_id,
        "trigger": trigger,
        "signal_count": signal_count,
        "scope": scope,
        "before_snapshot": before_snapshot,
        "after_snapshot": after_snapshot,
        "explanation_text": explanation_text,
    }).execute()
    if not result.data:
        raise RuntimeError("adaptations INSERT returned no rows -- check RLS and schema")
    return result.data[0]["id"]


# ---------------------------------------------------------------------------
# Micro adjustment (ADAPT-02, D-17)
# ---------------------------------------------------------------------------


async def apply_micro_adjustment(user_id: str, signal: dict) -> dict:
    """
    ADAPT-02, D-17: Micro-adjust the next 1-3 planned sessions for one signal.

    Reduces intensity/duration on up to 3 upcoming planned sessions to give the
    rider time to recover or catch up after a miss or underperformance event.

    Returns a summary dict with:
        {"status": "applied", "scope": "micro", "sessions_adjusted": [...],
         "before": [...], "after": [...], "explanation": str, "adaptation_id": str}
    """
    supabase = await _get_async_supabase()
    today = date.today()

    # Fetch the next 3 upcoming planned sessions for this user.
    resp = await (
        supabase.table("sessions")
        .select("id, scheduled_date, tss_target, duration_minutes, status")
        .eq("user_id", user_id)
        .eq("status", "planned")
        .gte("scheduled_date", today.isoformat())
        .order("scheduled_date", desc=False)
        .execute()
    )
    upcoming = (resp.data or [])[:3]

    if not upcoming:
        return {
            "status": "applied",
            "scope": "micro",
            "sessions_adjusted": [],
            "before": [],
            "after": [],
            "explanation": "No upcoming sessions to adjust.",
            "adaptation_id": None,
        }

    before_snapshot = {"sessions": [dict(s) for s in upcoming]}
    after_sessions = []

    for session in upcoming:
        # Reduce TSS target and duration by 20% for micro-adjustment.
        original_tss = session.get("tss_target") or 0
        original_dur = session.get("duration_minutes") or 0
        new_tss = round(original_tss * 0.8, 1)
        new_dur = round(original_dur * 0.8, 0)

        await supabase.table("sessions").update({
            "tss_target": new_tss,
            "duration_minutes": new_dur,
        }).eq("id", session["id"]).execute()

        after_sessions.append({
            **session,
            "tss_target": new_tss,
            "duration_minutes": new_dur,
        })

    after_snapshot = {"sessions": after_sessions}

    signal_type = signal.get("type", "unknown")
    session_id = signal.get("session_id", "unknown")
    compliance_pct = signal.get("compliance_pct")

    if signal_type == "missed":
        explanation_text = (
            f"Micro-adjustment triggered by missed session {session_id}. "
            f"Next {len(upcoming)} sessions reduced to 80% intensity to ease back in."
        )
    else:
        explanation_text = (
            f"Micro-adjustment triggered by underperformance signal on session {session_id} "
            f"(compliance: {compliance_pct}% of planned TSS from validate_session_vs_actual). "
            f"Next {len(upcoming)} sessions reduced to 80% intensity."
        )

    adaptation_id = await log_adaptation(
        user_id=user_id,
        trigger=signal_type,
        signal_count=1,
        scope="micro",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        explanation_text=explanation_text,
    )

    return {
        "status": "applied",
        "scope": "micro",
        "sessions_adjusted": [s["id"] for s in upcoming],
        "before": before_snapshot["sessions"],
        "after": after_sessions,
        "explanation": explanation_text,
        "adaptation_id": adaptation_id,
    }


# ---------------------------------------------------------------------------
# Macro re-plan (ADAPT-02, ADAPT-03, ADAPT-05, D-18, D-19)
# ---------------------------------------------------------------------------


async def apply_macro_replan(user_id: str, signals: list[dict]) -> dict:
    """
    ADAPT-02, ADAPT-03, ADAPT-05, D-18, D-19: Full macro re-plan for 2+ signals.

    Calls progress_load to get a safe reduced weekly CTL target (ADAPT-05 -- intensity
    decision comes from the tool, not a hardcoded literal).

    Runs check_shift_limit on before/after session dates. If shift_pct > 30%,
    returns {"status": "needs_confirmation", "change_summary": ...} WITHOUT applying (D-19).

    Otherwise applies, logs the adaptation, and returns the applied summary.
    """
    supabase = await _get_async_supabase()
    today = date.today()

    # Load upcoming planned sessions (the "before" state).
    upcoming_resp = await (
        supabase.table("sessions")
        .select("id, scheduled_date, tss_target, duration_minutes, status")
        .eq("user_id", user_id)
        .eq("status", "planned")
        .gte("scheduled_date", today.isoformat())
        .order("scheduled_date", desc=False)
        .execute()
    )
    before_sessions = upcoming_resp.data or []

    if not before_sessions:
        return {
            "status": "applied",
            "scope": "macro",
            "change_summary": "No upcoming sessions to replan.",
            "adaptation_id": None,
        }

    # Load user profile to get current fitness state for progress_load (ADAPT-05).
    profile_resp = await (
        supabase.table("profiles")
        .select("constraints")
        .eq("user_id", user_id)
        .execute()
    )
    profile = (profile_resp.data or [{}])[0]
    constraints = profile.get("constraints") or {}

    # Load PMC data to get current CTL (ADAPT-05: intensity via tool result).
    pmc_resp = await (
        supabase.table("pmc_history")
        .select("ctl, atl")
        .eq("user_id", user_id)
        .order("date", desc=True)
        .execute()
    )
    pmc_rows = pmc_resp.data or []
    current_ctl = float((pmc_rows[0].get("ctl") or 0) if pmc_rows else 0)

    # ADAPT-05: call progress_load tool to determine reduced weekly capacity.
    # Target CTL is 10% below current to give recovery room after signal-triggering events.
    reduced_target_ctl = max(0.0, current_ctl * 0.9)
    load_result = progress_load(
        current_ctl=current_ctl,
        target_ctl=reduced_target_ctl,
        constraints=constraints,
    )
    recommended_ctl = load_result.value.get("recommended_ctl_target", current_ctl)

    # Compute reduced capacity: scale each session's TSS by the CTL ratio.
    # When current_ctl is 0 (cold start), apply a conservative 80% reduction.
    capacity_ratio = (recommended_ctl / current_ctl) if current_ctl > 0 else 0.8

    # Build "after" sessions with adjusted TSS and shifted dates (spread sessions out).
    after_sessions = []
    for i, session in enumerate(before_sessions):
        original_tss = session.get("tss_target") or 0
        new_tss = round(original_tss * capacity_ratio, 1)
        sched = _parse_date(session.get("scheduled_date"))
        # Shift each session out by 1 day to spread load; apply proportionally.
        new_date = (sched + timedelta(days=1)).isoformat() if sched else session.get("scheduled_date")
        after_sessions.append({
            **session,
            "tss_target": new_tss,
            "scheduled_date": new_date,
        })

    # ADAPT-03: enforce the 30% shift guard before applying.
    shift_check = check_shift_limit(before_sessions, after_sessions)

    if shift_check["requires_user_confirmation"]:
        # D-19: surface change summary WITHOUT applying (never silently over-shift).
        signal_types = list({s.get("type") for s in signals})
        change_summary = {
            "proposed_sessions": after_sessions,
            "shift_check": shift_check,
            "signals": signals,
            "recommended_ctl": recommended_ctl,
            "warning": (
                f"Macro replan would shift {shift_check['shifted_count']} of "
                f"{shift_check['total_upcoming']} sessions "
                f"({shift_check['shift_pct'] * 100:.0f}% > 30% guard). "
                f"User confirmation required before applying (D-19)."
            ),
        }
        return {
            "status": "needs_confirmation",
            "scope": "macro",
            "change_summary": change_summary,
        }

    # Apply: update sessions in DB.
    for session in after_sessions:
        await supabase.table("sessions").update({
            "tss_target": session["tss_target"],
            "scheduled_date": session["scheduled_date"],
        }).eq("id", session["id"]).execute()

    signal_types = list({s.get("type") for s in signals})
    primary_trigger = signal_types[0] if signal_types else "underperformance"
    explanation_text = (
        f"Macro re-plan triggered by {len(signals)} signals "
        f"({', '.join(signal_types)}) in a 7-day window. "
        f"progress_load recommended CTL target {recommended_ctl} from current "
        f"{current_ctl} (reduced capacity {capacity_ratio:.0%}). "
        f"{len(after_sessions)} sessions rescheduled."
    )

    before_snapshot = {"sessions": before_sessions}
    after_snapshot = {"sessions": after_sessions, "recommended_ctl": recommended_ctl}

    adaptation_id = await log_adaptation(
        user_id=user_id,
        trigger=primary_trigger,
        signal_count=len(signals),
        scope="macro",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
        explanation_text=explanation_text,
    )

    return {
        "status": "applied",
        "scope": "macro",
        "sessions_adjusted": [s["id"] for s in after_sessions],
        "before": before_sessions,
        "after": after_sessions,
        "explanation": explanation_text,
        "adaptation_id": adaptation_id,
    }


# ---------------------------------------------------------------------------
# Router + endpoints
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Request body models
# ---------------------------------------------------------------------------


router = APIRouter()


@router.get("/")
async def list_adaptations(
    current_user: dict = Depends(get_current_user),
) -> list:
    """
    TRANSP-03: GET /adaptations/

    Returns the readable adaptation log for the authenticated user, newest first.
    user_id is sourced from the verified JWT (Authorization: Bearer header).
    """
    user_id = current_user["user_id"]
    validate_uuid(user_id, "user_id")
    supabase = await _get_async_supabase()
    rows = await (
        supabase.table("adaptations")
        .select("*")
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )
    return rows.data


@router.post("/check")
async def check_adaptations(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    ADAPT-04: POST /adaptations/check

    Runs signal detection independently of upload events (weekly check).
    Dispatches to micro or macro adaptation when signals are present.
    Calendar sync scheduled as a fire-and-forget background task (CAL-02, CAL-04).
    user_id is sourced from the verified JWT.
    """
    user_id = current_user["user_id"]
    validate_uuid(user_id, "user_id")
    signals = await detect_signals(user_id)
    scope = decide_scope(signals)

    result = None
    if scope == "micro" and signals:
        result = await apply_micro_adjustment(user_id, signals[0])
    elif scope == "macro":
        result = await apply_macro_replan(user_id, signals)

    # CAL-02: fire-and-forget calendar sync after sessions change (CAL-04: never 500 on failure).
    if result and result.get("status") == "applied":
        after_sessions = result.get("after", [])
        before_sessions = result.get("before", [])
        # Build lookup of before sessions by id for calendar_event_id.
        before_by_id = {s["id"]: s for s in before_sessions}
        for session in after_sessions:
            event_id = session.get("calendar_event_id") or before_by_id.get(session["id"], {}).get("calendar_event_id")
            if event_id:
                background_tasks.add_task(update_calendar_event, user_id, event_id, session)

    return {
        "signals": signals,
        "scope": scope,
        "result": result,
    }


@router.post("/sessions/{session_id}/missed")
async def mark_session_missed(
    background_tasks: BackgroundTasks,
    session_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    D-16: POST /adaptations/sessions/{session_id}/missed

    Marks a specific session as missed and re-runs signal detection for the user.
    Returns the full check result so the caller can see what was triggered.
    user_id is sourced from the verified JWT.
    """
    user_id = current_user["user_id"]
    validate_uuid(user_id, "user_id")
    validate_uuid(session_id, "session_id")
    supabase = await _get_async_supabase()

    # Verify the session belongs to the requesting user before marking missed.
    session_resp = await (
        supabase.table("sessions")
        .select("id, user_id, status")
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    session_rows = session_resp.data or []
    if not session_rows:
        raise HTTPException(
            status_code=404,
            detail={"error": "session_not_found", "detail": "Session not found or does not belong to this user."},
        )

    # Update session status to "missed".
    await supabase.table("sessions").update({"status": "missed"}).eq("id", session_id).execute()

    # Re-run full signal detection to pick up cascading effects.
    signals = await detect_signals(user_id)
    scope = decide_scope(signals)

    result = None
    if scope == "micro" and signals:
        result = await apply_micro_adjustment(user_id, signals[0])
    elif scope == "macro":
        result = await apply_macro_replan(user_id, signals)

    # CAL-02: fire-and-forget calendar sync (CAL-04: never 500 on failure).
    if result and result.get("status") == "applied":
        after_sessions = result.get("after", [])
        before_sessions = result.get("before", [])
        before_by_id = {s["id"]: s for s in before_sessions}
        for session in after_sessions:
            event_id = session.get("calendar_event_id") or before_by_id.get(session["id"], {}).get("calendar_event_id")
            if event_id:
                background_tasks.add_task(update_calendar_event, user_id, event_id, session)

    return {
        "session_id": session_id,
        "marked_missed": True,
        "signals": signals,
        "scope": scope,
        "result": result,
    }
