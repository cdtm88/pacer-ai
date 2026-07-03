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
  - Underperformance: validate_session_vs_actual flags 'under_performed'
    (tool-owned threshold: compliance < 70%) (ADAPT-05)

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

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel

from backend.auth import get_current_user
from backend.calendar_sync import delete_calendar_event, update_calendar_event
from backend.db import get_async_supabase as _get_async_supabase
from backend.utils import validate_uuid
from backend.sports_science.compliance import validate_session_vs_actual
from backend.sports_science.load import progress_load

logger = logging.getLogger(__name__)


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
        # WR-03: the previous strptime loop sliced val by len(fmt) (the format
        # string's length, not the length of a value that format would
        # produce), so every attempt raised ValueError and only this fallback
        # ever actually parsed a value. Drop the dead loop and parse directly.
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _find_matching_ride(session_id: str, sched: date, rides_by_date: dict) -> Optional[dict]:
    """Find a ride within +/-1 day of `sched`, preferring an explicit session_id link."""
    for delta in [0, -1, 1]:
        check_date = sched + timedelta(days=delta)
        if check_date in rides_by_date:
            day_rides = rides_by_date[check_date]
            matched = next(
                (r for r in day_rides if r.get("session_id") == session_id),
                day_rides[0] if day_rides else None,
            )
            if matched:
                return matched
    return None


async def _get_consumed_session_ids(supabase, user_id: str) -> set[str]:
    """
    Pattern 5 consumed-ids lookup: session ids recorded in
    adaptations.trigger_session_ids for this user. A consumed session must
    never re-fire a signal.

    CR-04: only adaptations that were actually acted on consume their trigger
    sessions -- 'applied' rows and the currently-pending 'proposed' row.
    Superseded proposals release their sessions so an ignored or replaced
    macro proposal's signals can re-fire instead of being lost forever.
    """
    consumed_resp = await (
        supabase.table("adaptations")
        .select("trigger_session_ids")
        .eq("user_id", user_id)
        .in_("status", ["applied", "proposed"])
        .execute()
    )
    consumed_ids: set[str] = set()
    for row in (consumed_resp.data or []):
        consumed_ids.update(row.get("trigger_session_ids") or [])
    return consumed_ids


async def detect_signals(user_id: str, window_days: int = 7) -> list[dict]:
    """
    ADAPT-01: Detect missed-session and underperformance signals for a user.

    Idempotency (Pattern 5): a session id already present in any
    `adaptations.trigger_session_ids` array for this user is skipped -- it has
    already been consumed by a prior adaptation and must not re-fire.

    Missed-session check (D-16):
      Load planned sessions whose scheduled_date is past-due within `window_days`.
      For each, look for a matching ride within +/-1 day of the scheduled_date.
      If none found, emit {"type": "missed", "session_id": id}.

    Underperformance check (ADAPT-05, D-17):
      Load completed sessions within `window_days` that have a matching ride.
      For each, call validate_session_vs_actual(planned, actual).
      If the tool result carries the 'under_performed' flag (tool-owned
      threshold: compliance < 70%), emit
      {"type": "underperformance", "session_id": id, "compliance_pct": value}.
      WR-07: the threshold decision is the tool's flag -- no route-level literal.

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

    # --- Consumed-ids pre-query (Pattern 5, T-06-05): scoped to this user only. ---
    consumed_ids = await _get_consumed_session_ids(supabase, user_id)

    # --- Load candidate sessions: both still-planned and already-completed. ---
    sessions_resp = await (
        supabase.table("sessions")
        .select("id, scheduled_date, tss_target, plan_id, status")
        .eq("user_id", user_id)
        .in_("status", ["planned", "completed"])
        .gte("scheduled_date", window_start.isoformat())
        .lte("scheduled_date", today.isoformat())
        .execute()
    )
    candidate_sessions = sessions_resp.data or []

    # Load all rides in the window to check for date matches.
    # WR-05: widen the lower bound by the +/-1 day match tolerance of
    # _find_matching_ride -- a session scheduled exactly on window_start whose
    # ride happened the day before would otherwise be falsely flagged missed.
    rides_resp = await (
        supabase.table("rides")
        .select("id, ride_date, tss, session_id")
        .eq("user_id", user_id)
        .gte("ride_date", (window_start - timedelta(days=1)).isoformat())
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

    for session in candidate_sessions:
        if session["id"] in consumed_ids:
            # Already consumed by a prior adaptation -- never re-emit (Pattern 5).
            continue

        sched = _parse_date(session.get("scheduled_date"))
        if sched is None:
            continue

        status = session.get("status")

        if status == "planned":
            if sched >= today:
                # Not yet due -- no signal.
                continue
            found_ride = _find_matching_ride(session["id"], sched, rides_by_date)
            if found_ride is None:
                signals.append({"type": "missed", "session_id": session["id"]})
            # If a ride exists but the session is still 'planned' (not yet flipped to
            # 'completed' by the upload pipeline), don't double-signal here.

        elif status == "completed":
            found_ride = _find_matching_ride(session["id"], sched, rides_by_date)
            if found_ride is None:
                continue

            # --- Underperformance check (ADAPT-05) ---
            # Use validate_session_vs_actual; threshold decision is the tool's compliance_pct.
            planned_tss = session.get("tss_target") or 0
            actual_tss = found_ride.get("tss") or 0

            result = validate_session_vs_actual(
                planned={"tss": planned_tss},
                actual={"tss": actual_tss},
            )
            compliance_pct = result.value.get("compliance_pct")

            # ADAPT-05 / WR-07: the tool's own 'under_performed' flag is the
            # decision source (fires at < 70% in compliance.py) -- the route
            # never re-implements the threshold as a literal.
            if "under_performed" in (result.value.get("flags") or []):
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
        if delta_days > 1:  # "more than 1 day" as per docstring
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
    status: str = "applied",
    trigger_session_ids: Optional[list] = None,
) -> str:
    """
    TRANSP-02, D-20: Persist one adaptation event to the adaptations table.

    trigger must be one of: "missed", "underperformance", "overreaching"
    scope   must be one of: "micro", "macro"
    status  must be one of: "applied", "proposed", "superseded" (Pattern 5/6)
    trigger_session_ids records the specific sessions consumed by this adaptation
    so detect_signals can skip them on future checks (Pattern 5, T-06-05).

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
        "status": status,
        "trigger_session_ids": trigger_session_ids or [],
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
        .select("id, scheduled_date, tss_target, duration_minutes, status, calendar_event_id")
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
        # CR-01: skip TSS scaling when tss_target is NULL -- writing 0.0 over
        # NULL would permanently zero the column and disable future compliance.
        original_tss = session.get("tss_target")
        original_dur = session.get("duration_minutes") or 0
        new_tss = round(original_tss * 0.8, 1) if original_tss is not None else None
        new_dur = round(original_dur * 0.8, 0)

        update_payload: dict = {
            "duration_minutes": new_dur,
            "duration_mins": new_dur,  # keep legacy column in sync
        }
        if new_tss is not None:
            update_payload["tss_target"] = new_tss

        await (
            supabase.table("sessions")
            .update(update_payload)
            .eq("id", session["id"])
            .eq("user_id", user_id)
            .execute()
        )

        after_sessions.append({
            **session,
            "tss_target": new_tss,
            "duration_minutes": new_dur,
        })

    after_snapshot = {"sessions": after_sessions}

    signal_type = signal.get("type", "unknown")
    session_id = signal.get("session_id")
    compliance_pct = signal.get("compliance_pct")

    if signal_type == "missed":
        explanation_text = (
            f"Micro-adjustment triggered by missed session {session_id}. "
            f"Next {len(upcoming)} sessions reduced to 80% intensity to ease back in."
        )
        if session_id:
            # Flip the triggering session's status so detect_signals stops matching it
            # via the 'planned' scan (Pattern 5). Dual-filtered for defence-in-depth.
            await (
                supabase.table("sessions")
                .update({"status": "missed"})
                .eq("id", session_id)
                .eq("user_id", user_id)
                .execute()
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
        trigger_session_ids=[session_id] if session_id else [],
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
        .select("id, scheduled_date, tss_target, duration_minutes, status, calendar_event_id")
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
    # CR-03: progressive spacing shifts session i by i // 2 days, so the first
    # four sessions stay within check_shift_limit's 1-day tolerance and only
    # longer replans (6+ upcoming sessions) cross the 30% guard. The previous
    # i + 2 spacing shifted EVERY session by >1 day, making shift_pct always
    # 1.0 and the auto-apply branch unreachable (inverting ADAPT-03/D-19: the
    # guard must discriminate large shifts from small ones, not fire always).
    after_sessions = []
    for i, session in enumerate(before_sessions):
        # CR-01: keep NULL tss_target as None -- never scale it into 0.0.
        original_tss = session.get("tss_target")
        new_tss = round(original_tss * capacity_ratio, 1) if original_tss is not None else None
        sched = _parse_date(session.get("scheduled_date"))
        new_date = (sched + timedelta(days=i // 2)).isoformat() if sched else session.get("scheduled_date")
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

        # OQ1: auto-supersede any prior pending proposal for this user before persisting
        # the new one -- the simplest correct behaviour for staleness (RESEARCH A2),
        # no separate rejection/expiry endpoint needed.
        await (
            supabase.table("adaptations")
            .update({"status": "superseded"})
            .eq("user_id", user_id)
            .eq("status", "proposed")
            .execute()
        )

        primary_trigger = signal_types[0] if signal_types else "underperformance"
        adaptation_id = await log_adaptation(
            user_id=user_id,
            trigger=primary_trigger,
            signal_count=len(signals),
            scope="macro",
            before_snapshot={"sessions": before_sessions},
            after_snapshot={"sessions": after_sessions, "recommended_ctl": recommended_ctl},
            explanation_text=change_summary["warning"],
            status="proposed",
            trigger_session_ids=[s["session_id"] for s in signals if s.get("session_id")],
        )

        return {
            "status": "needs_confirmation",
            "scope": "macro",
            "adaptation_id": adaptation_id,
            "change_summary": change_summary,
        }

    # Apply: update sessions in DB.
    for session in after_sessions:
        update_payload: dict = {"scheduled_date": session["scheduled_date"]}
        # CR-01: never write a scaled-from-NULL 0.0 over a NULL tss_target.
        if session.get("tss_target") is not None:
            update_payload["tss_target"] = session["tss_target"]
        await (
            supabase.table("sessions")
            .update(update_payload)
            .eq("id", session["id"])
            .eq("user_id", user_id)
            .execute()
        )

    # Flip every 'missed' signal's triggering session to status='missed' (Pattern 5),
    # dual-filtered for defence-in-depth.
    for sig in signals:
        if sig.get("type") == "missed" and sig.get("session_id"):
            await (
                supabase.table("sessions")
                .update({"status": "missed"})
                .eq("id", sig["session_id"])
                .eq("user_id", user_id)
                .execute()
            )

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
        trigger_session_ids=[s["session_id"] for s in signals if s.get("session_id")],
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
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    ADAPT-04: POST /adaptations/check

    Runs signal detection independently of upload events (weekly check).
    Dispatches to micro or macro adaptation when signals are present.
    Calendar sync is inline-awaited before responding (Vercel serverless
    constraint: no BackgroundTasks, which Vercel freezes/kills after the
    response is sent); CAL-04: a calendar failure never breaks this endpoint,
    and the underlying Google API calls are timeout-bounded (CAL-02).
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

    # CAL-02: calendar sync after sessions change (CAL-04: never 500 on failure).
    if result and result.get("status") == "applied":
        after_sessions = result.get("after", [])
        before_sessions = result.get("before", [])
        # Build lookup of before sessions by id for calendar_event_id.
        before_by_id = {s["id"]: s for s in before_sessions}
        for session in after_sessions:
            event_id = session.get("calendar_event_id") or before_by_id.get(session["id"], {}).get("calendar_event_id")
            if event_id:
                # --- update_calendar_event inline-awaited (Vercel serverless
                #     constraint: no BackgroundTasks, which Vercel freezes/kills
                #     after the response is sent) ---
                await update_calendar_event(user_id, event_id, session)

    return {
        "signals": signals,
        "scope": scope,
        "result": result,
    }


@router.post("/{adaptation_id}/confirm")
async def confirm_macro_replan(
    adaptation_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    D-19, Pattern 6: POST /adaptations/{adaptation_id}/confirm

    Applies a stored 'proposed' macro-replan proposal exactly as it was persisted
    (not a freshly recomputed version, which could differ if state changed in
    between) and flips the adaptation's status to 'applied'.

    T-06-04: dual-filters id + user_id + status='proposed' before any apply so a
    foreign or non-proposed adaptation id can never be confirmed (IDOR mitigation).
    user_id is sourced from the verified JWT.
    """
    user_id = current_user["user_id"]
    validate_uuid(user_id, "user_id")
    validate_uuid(adaptation_id, "adaptation_id")
    supabase = await _get_async_supabase()

    row_resp = await (
        supabase.table("adaptations")
        .select("*")
        .eq("id", adaptation_id)
        .eq("user_id", user_id)
        .eq("status", "proposed")
        .execute()
    )
    rows = row_resp.data or []
    if not rows:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "proposal_not_found",
                "detail": "No pending macro-replan proposal for this id.",
            },
        )

    proposal = rows[0]
    proposed_sessions = (proposal.get("after_snapshot") or {}).get("sessions") or []

    for session in proposed_sessions:
        await (
            supabase.table("sessions")
            .update({
                "tss_target": session.get("tss_target"),
                "scheduled_date": session.get("scheduled_date"),
            })
            .eq("id", session["id"])
            .eq("user_id", user_id)
            .execute()
        )

    await (
        supabase.table("adaptations")
        .update({"status": "applied"})
        .eq("id", adaptation_id)
        .eq("user_id", user_id)
        .execute()
    )

    # CAL-02: calendar sync after sessions change (CAL-04: never 500 on failure).
    # WR-01: confirm_macro_replan applies proposed_sessions but, unlike
    # check_adaptations/mark_session_missed, previously never synced the
    # calendar -- mirror those call sites using proposed_sessions'
    # calendar_event_id (present once CR-02's select fix ships).
    for session in proposed_sessions:
        event_id = session.get("calendar_event_id")
        if event_id:
            # --- update_calendar_event inline-awaited (Vercel serverless
            #     constraint: no BackgroundTasks, which Vercel freezes/kills
            #     after the response is sent) ---
            await update_calendar_event(user_id, event_id, session)

    return {"status": "applied", "adaptation_id": adaptation_id}


@router.post("/sessions/{session_id}/missed")
async def mark_session_missed(
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
    # Errors here must not 500 the response — the miss was already recorded.
    signals: list = []
    result = None
    scope = None
    try:
        signals = await detect_signals(user_id)

        # CR-02: detect_signals only scans status in ('planned', 'completed'),
        # so the session just flipped to 'missed' can never appear in its
        # output. Synthesize its missed signal explicitly so a manual mark
        # actually triggers an adaptation -- unless a prior adaptation already
        # consumed this session (Pattern 5).
        if session_id not in {s.get("session_id") for s in signals}:
            consumed_ids = await _get_consumed_session_ids(supabase, user_id)
            if session_id not in consumed_ids:
                signals.append({"type": "missed", "session_id": session_id})

        scope = decide_scope(signals)

        if scope == "micro" and signals:
            result = await apply_micro_adjustment(user_id, signals[0])
        elif scope == "macro":
            result = await apply_macro_replan(user_id, signals)

        # CAL-02: calendar sync (CAL-04: never 500 on failure).
        if result and result.get("status") == "applied":
            after_sessions = result.get("after", [])
            before_sessions = result.get("before", [])
            before_by_id = {s["id"]: s for s in before_sessions}
            for session in after_sessions:
                event_id = session.get("calendar_event_id") or before_by_id.get(session["id"], {}).get("calendar_event_id")
                if event_id:
                    # --- update_calendar_event inline-awaited (Vercel serverless
                    #     constraint: no BackgroundTasks, which Vercel freezes/kills
                    #     after the response is sent) ---
                    await update_calendar_event(user_id, event_id, session)
    except Exception:
        logger.warning(
            "Signal detection/adaptation failed for session %s (non-fatal)", session_id, exc_info=True
        )

    return {
        "session_id": session_id,
        "marked_missed": True,
        "signals": signals,
        "scope": scope,
        "result": result,
    }
