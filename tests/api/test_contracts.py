# tests/api/test_contracts.py
"""
D-01: backend response-shape contract guards for rides/sessions/profile.

These tests exist to catch the class of bug that shipped in Phases 6-9:
a backend field gets renamed (or a route's response wrapper shape changes)
and the frontend silently breaks because nothing asserts the two stay in
sync. Each test hits the real route via httpx.AsyncClient(ASGITransport),
mocks only the Supabase layer, and asserts (by field NAME, not value) that
the exact fields frontend/src/lib/api.ts dereferences are present in the
response.

Uses subset assertions (`required <= set(body.keys())`), never exact
equality, so the backend can add columns without breaking this guard --
only a DROPPED field should ever fail these tests.

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
from unittest.mock import AsyncMock, MagicMock

import httpx
from httpx import ASGITransport

from tests.api.conftest import TEST_JWT_SECRET, TEST_USER_ID, auth_headers


def _mock_supabase_factory_extended(return_rows: list):
    """
    Async-callable mock Supabase client supporting the full chain used by
    rides/sessions/profiles routes: table/select/insert/upsert/eq/gte/
    order/limit/execute. Mirrors tests/api/test_sessions.py's
    mock_supabase_factory_extended (kept local here so this file stays a
    self-contained contract-test module per D-01).
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
# GET /rides/ contract
# ---------------------------------------------------------------------------


async def test_rides_contract(monkeypatch):
    """
    GET /rides/ returns {"rides": [...]} where each ride has, at minimum, the
    fields frontend/src/lib/api.ts's getRides() reads: id, ride_date,
    duration_secs, avg_power, np_watts, tss, compliance_pct.
    """
    import backend.routes.rides as rides_module

    ride_row = {
        "id": "ride-001",
        "user_id": TEST_USER_ID,
        "tss": 65.0,
        "np_watts": 190.0,
        "intensity_factor": 0.85,
        "duration_secs": 3600,
        "ride_date": "2026-07-01",
        "avg_power": 180.0,
        "avg_hr": 145.0,
        "avg_cadence": 88.0,
        "ftp_used": 210.0,
        "session_id": None,
        "compliance_pct": 90.0,
    }

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(
        rides_module, "_get_async_supabase", _mock_supabase_factory_extended([ride_row])
    )

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/rides/", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    ride = body["rides"][0]

    required = {
        "id", "ride_date", "duration_secs", "avg_power", "np_watts", "tss", "compliance_pct",
    }
    assert required <= set(ride.keys())


# ---------------------------------------------------------------------------
# GET /sessions/today contract
# ---------------------------------------------------------------------------


async def test_sessions_today_contract(monkeypatch):
    """
    GET /sessions/today returns a single session object with, at minimum,
    the fields frontend code actually reads: id, objective, structure,
    type, duration_mins, scheduled_date, rpe_target.
    """
    import datetime

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
        "rpe_target": 4,
        "tss_target": 50.0,
        "calendar_event_id": None,
    }

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(
        sessions_module, "_get_async_supabase", _mock_supabase_factory_extended([session_row])
    )

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/sessions/today", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()

    required = {
        "id", "objective", "structure", "type", "duration_mins", "scheduled_date", "rpe_target",
    }
    assert required <= set(body.keys())


# ---------------------------------------------------------------------------
# GET /profiles/me contract
# ---------------------------------------------------------------------------


async def test_profile_me_contract(monkeypatch):
    """
    GET /profiles/me returns the profile row with, at minimum, "ftp" --
    the one field DuringSessionScreen.tsx reads (DuringSessionScreen.tsx:554).
    """
    import backend.routes.sessions as sessions_module

    profile_row = {
        "id": "prof-001",
        "user_id": TEST_USER_ID,
        "ftp": 210.0,
        "constraints": {"back_issues": False},
        "equipment": {"trainer": "wahoo_kickr_core"},
        "goals": "general_fitness",
        "back_status": "none",
        "weekly_hours": 5.0,
        "preferred_days": ["monday", "wednesday", "friday"],
        "rpe_baseline": "moderate",
        "lthr_estimate": None,
        "created_at": "2026-06-01T10:00:00Z",
    }

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(
        sessions_module, "_get_async_supabase", _mock_supabase_factory_extended([profile_row])
    )

    app = _get_app()
    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/profiles/me", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()

    required = {"ftp"}
    assert required <= set(body.keys())
