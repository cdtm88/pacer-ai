# tests/api/test_adaptations.py
"""
Adaptation route and signal detection tests (Wave 4, ADAPT-01 through ADAPT-05,
TRANSP-02, TRANSP-03).

Tests cover:
  - detect_signals: missed-session and underperformance signal detection (ADAPT-01)
  - decide_scope: micro/macro branching (ADAPT-02)
  - check_shift_limit: 30% guard boundary (ADAPT-03)
  - POST /adaptations/check: weekly check endpoint independent of uploads (ADAPT-04)
  - validate_session_vs_actual call in detect_signals (ADAPT-05)
  - log_adaptation: DB insert with required fields (TRANSP-02)
  - GET /adaptations/: readable log + 422 on missing user_id (TRANSP-03)

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
Pure functions (decide_scope, check_shift_limit) are called directly (no mock needed).
DB-dependent functions (detect_signals, log_adaptation) use monkeypatched _get_async_supabase.
"""
import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from httpx import ASGITransport

from tests.api.conftest import TEST_USER_ID, mock_supabase_factory

# ---------------------------------------------------------------------------
# Pure function helpers
# ---------------------------------------------------------------------------


def _sig(type_="missed", session_id="sess-001", compliance_pct=None):
    """Build a signal dict for test use."""
    s = {"type": type_, "session_id": session_id}
    if compliance_pct is not None:
        s["compliance_pct"] = compliance_pct
    return s


# ---------------------------------------------------------------------------
# ADAPT-01: test_missed_detection
# ---------------------------------------------------------------------------


async def test_missed_detection(monkeypatch):
    """
    ADAPT-01: detect_signals identifies a missed session when a past-due planned
    session has no matching ride within +/-1 day.
    """
    import api.routes.adaptations as adapt_module

    today = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=2)).isoformat()

    # The sessions table returns one past-due planned session.
    sessions_data = [
        {"id": "sess-001", "scheduled_date": yesterday, "tss_target": 60, "plan_id": None}
    ]
    # The rides table returns no rides (empty -- so no match).
    rides_data: list = []

    # Mock the chained Supabase query. Two execute() calls in detect_signals:
    # first for sessions, second for rides.
    execute_sessions = MagicMock()
    execute_sessions.data = sessions_data

    execute_rides = MagicMock()
    execute_rides.data = rides_data

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.lt.return_value = mock_client
    mock_client.lte.return_value = mock_client
    mock_client.order.return_value = mock_client
    # Side effects: first call returns sessions, second returns rides.
    mock_client.execute = AsyncMock(side_effect=[execute_sessions, execute_rides])

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    signals = await adapt_module.detect_signals(TEST_USER_ID)
    assert len(signals) == 1
    assert signals[0]["type"] == "missed"
    assert signals[0]["session_id"] == "sess-001"


# ---------------------------------------------------------------------------
# ADAPT-02: test_micro_macro_branch
# ---------------------------------------------------------------------------


def test_micro_macro_branch():
    """
    ADAPT-02: decide_scope returns correct scope for 0, 1, and 2+ signals.
    """
    from api.routes.adaptations import decide_scope

    assert decide_scope([]) is None
    assert decide_scope([_sig()]) == "micro"
    assert decide_scope([_sig(), _sig("underperformance", "sess-002", 45.0)]) == "macro"
    # 3+ signals also macro
    assert decide_scope([_sig(), _sig(), _sig()]) == "macro"


# ---------------------------------------------------------------------------
# ADAPT-03: test_shift_limit
# ---------------------------------------------------------------------------


def test_shift_limit():
    """
    ADAPT-03: check_shift_limit enforces the 30% boundary.

    Case 1: >30% of sessions shift by >1 day -> requires_user_confirmation True.
    Case 2: <=30% shift -> requires_user_confirmation False.
    """
    from api.routes.adaptations import check_shift_limit

    # Case 1: 2 of 3 sessions (67%) shift by more than 1 day.
    before = [
        {"id": "s1", "scheduled_date": "2026-06-20"},
        {"id": "s2", "scheduled_date": "2026-06-22"},
        {"id": "s3", "scheduled_date": "2026-06-24"},
    ]
    after_over = [
        {"id": "s1", "scheduled_date": "2026-06-27"},  # +7 days (shifted)
        {"id": "s2", "scheduled_date": "2026-06-29"},  # +7 days (shifted)
        {"id": "s3", "scheduled_date": "2026-06-24"},  # same (not shifted)
    ]
    result_over = check_shift_limit(before, after_over)
    assert result_over["requires_user_confirmation"] is True
    assert result_over["shifted_count"] == 2
    assert result_over["shift_pct"] > 0.30

    # Case 2: 0 of 3 sessions shift (all within 1 day tolerance).
    after_under = [
        {"id": "s1", "scheduled_date": "2026-06-21"},  # +1 day (boundary -- not >1)
        {"id": "s2", "scheduled_date": "2026-06-22"},  # same
        {"id": "s3", "scheduled_date": "2026-06-24"},  # same
    ]
    result_under = check_shift_limit(before, after_under)
    assert result_under["requires_user_confirmation"] is False
    assert result_under["shifted_count"] == 0

    # Case 3: exactly 1 of 4 sessions shifts (25% < 30%).
    before4 = [
        {"id": "a", "scheduled_date": "2026-06-20"},
        {"id": "b", "scheduled_date": "2026-06-22"},
        {"id": "c", "scheduled_date": "2026-06-24"},
        {"id": "d", "scheduled_date": "2026-06-26"},
    ]
    after4 = [
        {"id": "a", "scheduled_date": "2026-06-25"},  # +5 days (shifted)
        {"id": "b", "scheduled_date": "2026-06-22"},  # same
        {"id": "c", "scheduled_date": "2026-06-24"},  # same
        {"id": "d", "scheduled_date": "2026-06-26"},  # same
    ]
    result4 = check_shift_limit(before4, after4)
    assert result4["requires_user_confirmation"] is False
    assert result4["shifted_count"] == 1
    assert result4["shift_pct"] == pytest.approx(0.25, abs=0.001)


# ---------------------------------------------------------------------------
# ADAPT-04: test_weekly_check
# ---------------------------------------------------------------------------


async def test_weekly_check(monkeypatch):
    """
    ADAPT-04: POST /adaptations/check returns signals and scope independently of uploads.
    When no signals are detected, response is {"signals": [], "scope": None, "result": None}.
    """
    from api.main import app
    import api.routes.adaptations as adapt_module

    # detect_signals returns empty list -- no sessions in DB.
    execute_result = MagicMock()
    execute_result.data = []

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.lt.return_value = mock_client
    mock_client.lte.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.execute = AsyncMock(return_value=execute_result)

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            "/adaptations/check",
            json={"user_id": TEST_USER_ID},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["signals"] == []
    assert data["scope"] is None
    assert data["result"] is None


# ---------------------------------------------------------------------------
# ADAPT-05: test_intensity_from_tools
# ---------------------------------------------------------------------------


async def test_intensity_from_tools(monkeypatch):
    """
    ADAPT-05: detect_signals invokes validate_session_vs_actual to determine
    underperformance. The compliance decision comes from the tool, not a literal.
    """
    import api.routes.adaptations as adapt_module
    from sports_science.compliance import validate_session_vs_actual

    today = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=1)).isoformat()

    # A session with planned TSS 80; the ride only achieved 40 (50% compliance -> underperformance).
    sessions_data = [
        {"id": "sess-underperf", "scheduled_date": yesterday, "tss_target": 80, "plan_id": None}
    ]
    rides_data = [
        {"id": "ride-001", "ride_date": yesterday, "tss": 40.0, "session_id": "sess-underperf"}
    ]

    execute_sessions = MagicMock()
    execute_sessions.data = sessions_data
    execute_rides = MagicMock()
    execute_rides.data = rides_data

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.lt.return_value = mock_client
    mock_client.lte.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.execute = AsyncMock(side_effect=[execute_sessions, execute_rides])

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    # Capture calls to validate_session_vs_actual to confirm it was invoked.
    call_log: list[dict] = []
    original_fn = validate_session_vs_actual

    def capturing_validate(planned, actual):
        call_log.append({"planned": planned, "actual": actual})
        return original_fn(planned, actual)

    monkeypatch.setattr(adapt_module, "validate_session_vs_actual", capturing_validate)

    signals = await adapt_module.detect_signals(TEST_USER_ID)

    # validate_session_vs_actual must have been called at least once.
    assert len(call_log) >= 1, "validate_session_vs_actual was not called -- compliance check bypassed (ADAPT-05 violation)"
    assert call_log[0]["planned"]["tss"] == 80
    assert call_log[0]["actual"]["tss"] == 40.0

    # 50% compliance < 60 threshold -> underperformance signal present.
    assert len(signals) == 1
    assert signals[0]["type"] == "underperformance"
    assert signals[0]["compliance_pct"] == pytest.approx(50.0, abs=0.1)


# ---------------------------------------------------------------------------
# TRANSP-02: test_log_persisted
# ---------------------------------------------------------------------------


async def test_log_persisted(monkeypatch):
    """
    TRANSP-02: log_adaptation inserts a row into the adaptations table with
    required fields: trigger, scope, explanation_text (and before/after snapshots).
    """
    import api.routes.adaptations as adapt_module

    inserted_rows: list[dict] = []

    execute_result = MagicMock()
    execute_result.data = [{"id": "adaptation-uuid-001"}]

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client

    def _capturing_insert(row):
        inserted_rows.append(row)
        return mock_client

    mock_client.insert = _capturing_insert
    mock_client.execute = AsyncMock(return_value=execute_result)

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    adaptation_id = await adapt_module.log_adaptation(
        user_id=TEST_USER_ID,
        trigger="missed",
        signal_count=1,
        scope="micro",
        before_snapshot={"sessions": [{"id": "s1"}]},
        after_snapshot={"sessions": [{"id": "s1", "tss_target": 48}]},
        explanation_text="Micro-adjustment triggered by missed session s1.",
    )

    assert adaptation_id == "adaptation-uuid-001"
    assert len(inserted_rows) == 1
    row = inserted_rows[0]
    assert row["user_id"] == TEST_USER_ID
    assert row["trigger"] == "missed"
    assert row["scope"] == "micro"
    assert "explanation_text" in row
    assert "before_snapshot" in row
    assert "after_snapshot" in row


# ---------------------------------------------------------------------------
# TRANSP-03: test_get_adaptations + test_get_adaptations_requires_user_id
# ---------------------------------------------------------------------------


async def test_get_adaptations(monkeypatch):
    """
    TRANSP-03: GET /adaptations/?user_id=... returns a list of adaptation records.
    """
    from api.main import app
    import api.routes.adaptations as adapt_module

    mock_rows = [
        {
            "id": "adapt-001",
            "user_id": TEST_USER_ID,
            "trigger": "missed",
            "scope": "micro",
            "signal_count": 1,
            "explanation_text": "Micro-adjustment triggered by missed session sess-001.",
            "before_snapshot": {},
            "after_snapshot": {},
            "created_at": "2026-06-20T09:00:00Z",
        }
    ]
    monkeypatch.setattr(adapt_module, "_get_async_supabase", mock_supabase_factory(mock_rows))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/adaptations/",
            params={"user_id": TEST_USER_ID},
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "adapt-001"
    assert data[0]["trigger"] == "missed"


async def test_get_adaptations_requires_user_id():
    """
    TRANSP-03: GET /adaptations/ without user_id returns 422 (missing required query param).
    """
    from api.main import app

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/adaptations/")

    assert response.status_code == 422
