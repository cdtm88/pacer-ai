# tests/api/test_sessions.py
"""
Tests for the Phase 4 session, PMC, profile, and conversation endpoints
(UI-02, UI-04, UI-06, T-04-01, T-04-03).

Covers:
  - GET /sessions/today returns the mocked session row
  - GET /sessions/upcoming returns a sessions list
  - GET /pmc_history/latest returns a PMC row including tss_display_ready
  - GET /profiles/me returns 404 when no profile row exists
  - Unauthenticated request (no token) returns 401 on every new endpoint
  - POST /conversations/ creates a conversation and returns a conversation_id

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport

from tests.api.conftest import (
    TEST_JWT_SECRET,
    TEST_USER_ID,
    auth_headers,
    mock_supabase_factory,
)


def mock_supabase_factory_extended(return_rows: list):
    """
    Extended version of mock_supabase_factory that also chains .gte() and .limit().
    Required for the sessions endpoints which use these chain methods.
    """
    execute_result = MagicMock()
    execute_result.data = return_rows

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.insert.return_value = mock_client
    mock_client.upsert.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.limit.return_value = mock_client
    mock_client.execute = AsyncMock(return_value=execute_result)

    async def _get_mock_client():
        return mock_client

    return _get_mock_client


def _get_app():
    """Import app after fixtures are configured to avoid import-time env checks."""
    from backend.main import app
    return app


# ---------------------------------------------------------------------------
# GET /sessions/today
# ---------------------------------------------------------------------------


async def test_sessions_today_returns_row(monkeypatch):
    """
    GET /sessions/today returns today's session row for the authenticated user.
    """
    import backend.routes.sessions as sessions_module

    today = datetime.date.today().isoformat()
    session_row = {
        "id": "sess-001",
        "objective": "Zone 2 endurance",
        "structure": None,
        "targets": None,
        "duration_mins": 60,
        "duration_minutes": None,
        "status": "planned",
        "scheduled_date": today,
        "type": "endurance",
        "zone_targets": None,
        "power_targets": None,
        "rpe_target": None,
        "tss_target": 50.0,
        "calendar_event_id": None,
    }

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(
        sessions_module, "_get_async_supabase", mock_supabase_factory_extended([session_row])
    )

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/sessions/today", headers=auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "sess-001"
    assert data["scheduled_date"] == today


async def test_sessions_today_returns_404_when_no_session(monkeypatch):
    """
    GET /sessions/today returns 404 when no planned session is scheduled today.
    """
    import backend.routes.sessions as sessions_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(
        sessions_module, "_get_async_supabase", mock_supabase_factory_extended([])
    )

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/sessions/today", headers=auth_headers())

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /sessions/upcoming
# ---------------------------------------------------------------------------


async def test_sessions_upcoming_returns_list(monkeypatch):
    """
    GET /sessions/upcoming returns the planned sessions list for the user.
    """
    import backend.routes.sessions as sessions_module

    today = datetime.date.today()
    sessions_data = [
        {
            "id": "sess-002",
            "objective": "Interval session",
            "structure": None,
            "targets": None,
            "duration_mins": 45,
            "duration_minutes": None,
            "status": "planned",
            "scheduled_date": (today + datetime.timedelta(days=1)).isoformat(),
            "type": "interval",
            "zone_targets": None,
            "power_targets": None,
            "rpe_target": 7,
            "tss_target": 80.0,
            "calendar_event_id": None,
        },
        {
            "id": "sess-003",
            "objective": "Recovery",
            "structure": None,
            "targets": None,
            "duration_mins": 30,
            "duration_minutes": None,
            "status": "planned",
            "scheduled_date": (today + datetime.timedelta(days=3)).isoformat(),
            "type": "recovery",
            "zone_targets": None,
            "power_targets": None,
            "rpe_target": 3,
            "tss_target": 20.0,
            "calendar_event_id": None,
        },
    ]

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(
        sessions_module, "_get_async_supabase", mock_supabase_factory_extended(sessions_data)
    )

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/sessions/upcoming", headers=auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert "sessions" in data
    assert len(data["sessions"]) == 2
    assert data["sessions"][0]["id"] == "sess-002"


# ---------------------------------------------------------------------------
# GET /pmc_history/latest
# ---------------------------------------------------------------------------


async def test_pmc_latest_returns_tss_display_ready(monkeypatch):
    """
    GET /pmc_history/latest returns the most recent PMC row including tss_display_ready.
    """
    import backend.routes.sessions as sessions_module

    pmc_row = {
        "id": "pmc-001",
        "user_id": TEST_USER_ID,
        "date": "2026-06-19",
        "ctl": 42.5,
        "atl": 38.2,
        "tsb": 4.3,
        "tss_display_ready": True,
        "created_at": "2026-06-19T12:00:00Z",
    }

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(
        sessions_module, "_get_async_supabase", mock_supabase_factory_extended([pmc_row])
    )

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/pmc_history/latest", headers=auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["tss_display_ready"] is True
    assert data["ctl"] == 42.5
    assert data["tsb"] == 4.3


async def test_pmc_latest_returns_empty_when_no_data(monkeypatch):
    """
    GET /pmc_history/latest returns {} when no PMC data exists (cold-start).
    """
    import backend.routes.sessions as sessions_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(
        sessions_module, "_get_async_supabase", mock_supabase_factory_extended([])
    )

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/pmc_history/latest", headers=auth_headers())

    assert response.status_code == 200
    assert response.json() == {}


# ---------------------------------------------------------------------------
# GET /profiles/me
# ---------------------------------------------------------------------------


async def test_profile_me_returns_404_when_no_profile(monkeypatch):
    """
    GET /profiles/me returns 404 with structured error when no profile row exists.
    """
    import backend.routes.sessions as sessions_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(
        sessions_module, "_get_async_supabase", mock_supabase_factory_extended([])
    )

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/profiles/me", headers=auth_headers())

    assert response.status_code == 404
    data = response.json()
    assert data["detail"]["error"] == "profile_not_found"


async def test_profile_me_returns_profile_row(monkeypatch):
    """
    GET /profiles/me returns the profile row for the authenticated user.
    """
    import backend.routes.sessions as sessions_module

    profile_row = {
        "id": "prof-001",
        "user_id": TEST_USER_ID,
        "constraints": {"back_issues": False},
        "fitness_level": "beginner",
        "equipment": {"trainer": "wahoo_kickr_core"},
        "goals": {"primary": "general_fitness"},
        "back_status": "none",
        "weekly_hours": 5.0,
        "preferred_days": ["monday", "wednesday", "friday"],
        "rpe_baseline": "moderate",
        "lthr_estimate": None,
        "created_at": "2026-06-01T10:00:00Z",
    }

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(
        sessions_module, "_get_async_supabase", mock_supabase_factory_extended([profile_row])
    )

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/profiles/me", headers=auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["user_id"] == TEST_USER_ID
    assert data["fitness_level"] == "beginner"


# ---------------------------------------------------------------------------
# Unauthenticated rejection (T-04-01)
# ---------------------------------------------------------------------------


async def test_sessions_today_rejects_unauthenticated(monkeypatch):
    """
    Unauthenticated request (no Authorization header, no token) returns 401.
    T-04-01: all new endpoints reject requests without a valid JWT.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/sessions/today")

    assert response.status_code in (401, 403)


async def test_sessions_upcoming_rejects_unauthenticated(monkeypatch):
    """
    GET /sessions/upcoming returns 401 without a JWT.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/sessions/upcoming")

    assert response.status_code in (401, 403)


async def test_pmc_latest_rejects_unauthenticated(monkeypatch):
    """
    GET /pmc_history/latest returns 401 without a JWT.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/pmc_history/latest")

    assert response.status_code in (401, 403)


async def test_profiles_me_rejects_unauthenticated(monkeypatch):
    """
    GET /profiles/me returns 401 without a JWT.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/profiles/me")

    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# POST /conversations/
# ---------------------------------------------------------------------------


async def test_create_conversation_returns_id(monkeypatch):
    """
    POST /conversations/ creates a coaching conversation and returns its id.
    """
    import backend.routes.chat as chat_module
    import backend.routes.onboarding as onboarding_module

    conversation_id = "conv-00000000-0001"

    # Mock the create_conversation helper to return a known id.
    async def mock_create_conversation(user_id: str, context_type: str) -> str:
        assert context_type == "coaching", "context_type must be 'coaching'"
        return conversation_id

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(chat_module, "create_conversation", mock_create_conversation)

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/conversations/", headers=auth_headers())

    assert response.status_code == 200
    data = response.json()
    assert data["conversation_id"] == conversation_id


async def test_create_conversation_rejects_unauthenticated(monkeypatch):
    """
    POST /conversations/ returns 401 without a JWT.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/conversations/")

    assert response.status_code in (401, 403)
