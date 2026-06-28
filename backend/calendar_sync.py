# api/calendar_sync.py
"""
Google Calendar sync helpers for PacerAI (CAL-01, CAL-02, CAL-04).

Provides three async helpers that wrap synchronous google-api-python-client
calls in asyncio.to_thread (Pitfall 4: google-auth is synchronous).

Each helper:
  - No-ops silently when the user has no google_tokens (CAL-04 guard).
  - Catches ALL exceptions internally so a calendar failure can never propagate
    to the adaptation or onboarding path (CAL-04, T-04-23).
  - Wraps the synchronous Google API call in asyncio.to_thread.
  - Never logs token values (CAL-03).

Additional helper:
  - push_all_sessions_to_calendar(user_id): loads all planned sessions for the
    user and pushes each to the calendar. Used by the onboarding path for the
    initial plan push (CAL-01).
"""

import asyncio
import datetime as _dt
import logging
import os
from datetime import timedelta
from typing import Optional

from backend.db import get_async_supabase as _get_async_supabase

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Credential loader
# ---------------------------------------------------------------------------


async def _load_credentials(user_id: str):
    """
    Load and decrypt a user's Google OAuth credentials from users.google_tokens.

    Returns a google.oauth2.credentials.Credentials instance, or None when the
    user has not connected Google Calendar.
    """
    try:
        from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]
        from cryptography.fernet import Fernet

        supabase = await _get_async_supabase()
        result = await (
            supabase.table("users")
            .select("google_tokens")
            .eq("id", user_id)
            .execute()
        )
        rows = result.data or []
        if not rows or not rows[0].get("google_tokens"):
            return None

        raw = rows[0]["google_tokens"]
        if isinstance(raw, str):
            raw = raw.encode()

        fernet_key = os.environ.get("CALENDAR_FERNET_KEY")
        if not fernet_key:
            logger.warning("CALENDAR_FERNET_KEY not set; cannot load calendar credentials")
            return None

        f = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
        credentials_json = f.decrypt(raw).decode()
        return Credentials.from_authorized_user_json(credentials_json)
    except Exception:
        logger.warning("Failed to load Google credentials for user %s", user_id, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# Calendar service builder
# ---------------------------------------------------------------------------


def _build_calendar_service(credentials):
    """Build a Google Calendar API service resource (synchronous)."""
    from googleapiclient.discovery import build  # type: ignore[import-untyped]
    return build("calendar", "v3", credentials=credentials)


# ---------------------------------------------------------------------------
# Event body builder
# ---------------------------------------------------------------------------


def _build_event_body(session: dict) -> dict:
    """
    Build a Google Calendar event body from a PacerAI session dict (CAL-01).

    Uses all-day events (start/end as {"date": ...}) per Open Question 3.
    Includes full session detail in the description body.
    """
    scheduled_date = session.get("scheduled_date") or session.get("date", "")
    objective = session.get("objective") or session.get("session_type") or "Training session"
    structure = session.get("structure") or ""
    targets = session.get("targets") or session.get("power_targets") or ""
    duration_min = session.get("duration_minutes") or session.get("duration_min") or ""

    description_parts = [f"PacerAI Session\n"]
    if objective:
        description_parts.append(f"Objective: {objective}")
    if structure:
        description_parts.append(f"Structure: {structure}")
    if targets:
        description_parts.append(f"Targets: {targets}")
    if duration_min:
        description_parts.append(f"Duration: {duration_min} min")

    sched_str = str(scheduled_date)
    try:
        end_date = (_dt.date.fromisoformat(sched_str) + timedelta(days=1)).isoformat()
    except ValueError:
        end_date = sched_str  # fall back on unparseable value

    return {
        "summary": f"PacerAI: {objective}",
        "description": "\n".join(description_parts),
        "start": {"date": sched_str},
        "end": {"date": end_date},
    }


# ---------------------------------------------------------------------------
# Public helpers (CAL-01, CAL-02, CAL-04)
# ---------------------------------------------------------------------------


async def push_session_to_calendar(user_id: str, session: dict) -> Optional[str]:
    """
    Push a planned session to Google Calendar as an all-day event (CAL-01).

    Args:
        user_id: User UUID.
        session: Session dict with at minimum scheduled_date and objective.

    Returns:
        The created Google Calendar event ID (to persist on sessions.calendar_event_id),
        or None when the user has no tokens or any error occurs (CAL-04).
    """
    try:
        credentials = await _load_credentials(user_id)
        if credentials is None:
            return None

        event_body = _build_event_body(session)

        def _insert() -> str:
            service = _build_calendar_service(credentials)
            result = service.events().insert(
                calendarId="primary",
                body=event_body,
            ).execute()
            return result.get("id", "")

        event_id = await asyncio.to_thread(_insert)
        return event_id or None
    except Exception:
        logger.warning(
            "push_session_to_calendar failed for user %s session %s",
            user_id,
            session.get("id"),
            exc_info=True,
        )
        return None


async def update_calendar_event(user_id: str, event_id: str, session: dict) -> None:
    """
    Update an existing Google Calendar event with new session data (CAL-02).

    No-ops silently if user has no tokens or any error occurs (CAL-04).
    """
    try:
        credentials = await _load_credentials(user_id)
        if credentials is None:
            return

        event_body = _build_event_body(session)

        def _update() -> None:
            service = _build_calendar_service(credentials)
            service.events().update(
                calendarId="primary",
                eventId=event_id,
                body=event_body,
            ).execute()

        await asyncio.to_thread(_update)
    except Exception:
        logger.warning(
            "update_calendar_event failed for user %s event %s",
            user_id,
            event_id,
            exc_info=True,
        )


async def delete_calendar_event(user_id: str, event_id: str) -> None:
    """
    Delete a Google Calendar event (CAL-02, plan change removes a session).

    No-ops silently if user has no tokens or any error occurs (CAL-04).
    """
    try:
        credentials = await _load_credentials(user_id)
        if credentials is None:
            return

        def _delete() -> None:
            service = _build_calendar_service(credentials)
            service.events().delete(
                calendarId="primary",
                eventId=event_id,
            ).execute()

        await asyncio.to_thread(_delete)
    except Exception:
        logger.warning(
            "delete_calendar_event failed for user %s event %s",
            user_id,
            event_id,
            exc_info=True,
        )


async def push_all_sessions_to_calendar(user_id: str) -> None:
    """
    Load all planned sessions for a user and push each to Google Calendar (CAL-01).

    Used by the post-onboarding path after initial plan generation so sessions
    appear in the calendar immediately after plan creation, not only on replan.

    Fire-and-forget: swallows all errors so plan generation is never blocked (CAL-04).
    """
    try:
        supabase = await _get_async_supabase()
        result = await (
            supabase.table("sessions")
            .select("id, scheduled_date, objective, structure, targets, duration_minutes")
            .eq("user_id", user_id)
            .eq("status", "planned")
            .execute()
        )
        sessions = result.data or []
        for session in sessions:
            event_id = await push_session_to_calendar(user_id, session)
            if event_id:
                # Persist event_id back onto the session row (CAL-01).
                await (
                    supabase.table("sessions")
                    .update({"calendar_event_id": event_id})
                    .eq("id", session["id"])
                    .execute()
                )
    except Exception:
        logger.warning(
            "push_all_sessions_to_calendar failed for user %s", user_id, exc_info=True
        )
