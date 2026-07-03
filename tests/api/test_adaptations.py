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

from tests.api.conftest import TEST_USER_ID, mock_supabase_factory, TEST_JWT_SECRET, auth_headers

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
    import backend.routes.adaptations as adapt_module

    today = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=2)).isoformat()

    # The sessions table returns one past-due planned session.
    sessions_data = [
        {"id": "sess-001", "scheduled_date": yesterday, "tss_target": 60, "plan_id": None, "status": "planned"}
    ]
    # The rides table returns no rides (empty -- so no match).
    rides_data: list = []

    # No prior adaptations rows for this user -- nothing already consumed.
    execute_consumed = MagicMock()
    execute_consumed.data = []

    # Mock the chained Supabase query. Three execute() calls in detect_signals:
    # consumed-ids pre-query, then sessions, then rides.
    execute_sessions = MagicMock()
    execute_sessions.data = sessions_data

    execute_rides = MagicMock()
    execute_rides.data = rides_data

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.in_.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.lt.return_value = mock_client
    mock_client.lte.return_value = mock_client
    mock_client.order.return_value = mock_client
    # Side effects: consumed-ids, then sessions, then rides.
    mock_client.execute = AsyncMock(side_effect=[execute_consumed, execute_sessions, execute_rides])

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    signals = await adapt_module.detect_signals(TEST_USER_ID)
    assert len(signals) == 1
    assert signals[0]["type"] == "missed"
    assert signals[0]["session_id"] == "sess-001"


# ---------------------------------------------------------------------------
# Pattern 5: test_detect_signals_idempotent
# ---------------------------------------------------------------------------


async def test_detect_signals_idempotent(monkeypatch):
    """
    Pattern 5: a second detect_signals call over the same unchanged state emits
    no signal for a session already recorded in some adaptations.trigger_session_ids.
    """
    import backend.routes.adaptations as adapt_module

    today = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=2)).isoformat()

    sessions_data = [
        {"id": "sess-001", "scheduled_date": yesterday, "tss_target": 60, "plan_id": None, "status": "planned"}
    ]
    rides_data: list = []

    # A prior adaptation already consumed sess-001.
    execute_consumed = MagicMock()
    execute_consumed.data = [{"trigger_session_ids": ["sess-001"]}]

    execute_sessions = MagicMock()
    execute_sessions.data = sessions_data
    execute_rides = MagicMock()
    execute_rides.data = rides_data

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.in_.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.lt.return_value = mock_client
    mock_client.lte.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.execute = AsyncMock(side_effect=[execute_consumed, execute_sessions, execute_rides])

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    signals = await adapt_module.detect_signals(TEST_USER_ID)
    assert signals == [], "session already in trigger_session_ids must not re-emit a signal"


# ---------------------------------------------------------------------------
# Pattern 5: test_apply_micro_adjustment_missed_status_value
# ---------------------------------------------------------------------------


async def test_apply_micro_adjustment_missed_status_value(monkeypatch):
    """
    A 'missed' signal consumed by apply_micro_adjustment must issue a sessions
    UPDATE whose status payload is exactly 'missed' (schema-legal after migration 0005),
    dual-filtered by id and user_id.
    """
    import backend.routes.adaptations as adapt_module

    today = datetime.date.today()

    upcoming = [
        {"id": "sess-next-1", "scheduled_date": today.isoformat(), "tss_target": 60, "duration_minutes": 60, "status": "planned"},
    ]
    execute_upcoming = MagicMock()
    execute_upcoming.data = upcoming
    execute_generic = MagicMock()
    execute_generic.data = [{"id": "adaptation-uuid-002"}]

    update_calls: list[dict] = []

    class _Chain:
        def __init__(self, client):
            self._client = client
            self._filters: dict = {}

        def eq(self, field, value):
            self._filters[field] = value
            return self

        async def execute(self):
            return execute_generic

    mock_client = MagicMock()

    def _update(payload):
        update_calls.append({"payload": payload, "filters": {}})
        chain = _Chain(mock_client)
        original_eq = chain.eq

        def _tracking_eq(field, value):
            update_calls[-1]["filters"][field] = value
            return chain

        chain.eq = _tracking_eq
        return chain

    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.insert.return_value = mock_client
    mock_client.update = _update
    mock_client.execute = AsyncMock(return_value=execute_upcoming)

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    signal = _sig(type_="missed", session_id="sess-missed-001")
    result = await adapt_module.apply_micro_adjustment(TEST_USER_ID, signal)

    missed_updates = [c for c in update_calls if c["payload"].get("status") == "missed"]
    assert len(missed_updates) == 1, "expected exactly one status='missed' UPDATE"
    assert missed_updates[0]["filters"].get("id") == "sess-missed-001"
    assert missed_updates[0]["filters"].get("user_id") == TEST_USER_ID
    assert result["status"] == "applied"


# ---------------------------------------------------------------------------
# ADAPT-02: test_micro_macro_branch
# ---------------------------------------------------------------------------


def test_micro_macro_branch():
    """
    ADAPT-02: decide_scope returns correct scope for 0, 1, and 2+ signals.
    """
    from backend.routes.adaptations import decide_scope

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
    from backend.routes.adaptations import check_shift_limit

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
# ADAPT-03/D-19: test_apply_macro_replan_shift_limit_fires + supersede
# ---------------------------------------------------------------------------


def _macro_upcoming_sessions(today):
    return [
        {"id": "sess-a", "scheduled_date": (today + datetime.timedelta(days=1)).isoformat(), "tss_target": 60, "duration_minutes": 60, "status": "planned"},
        {"id": "sess-b", "scheduled_date": (today + datetime.timedelta(days=3)).isoformat(), "tss_target": 60, "duration_minutes": 60, "status": "planned"},
        {"id": "sess-c", "scheduled_date": (today + datetime.timedelta(days=5)).isoformat(), "tss_target": 60, "duration_minutes": 60, "status": "planned"},
    ]


async def test_apply_macro_replan_shift_limit_fires(monkeypatch):
    """
    ADAPT-03, D-19: the fixed progressive-spacing generator produces a shift wide
    enough for check_shift_limit's guard to fire. When it fires, needs_confirmation
    is returned and NO session rows are updated with tss_target/scheduled_date.
    """
    import backend.routes.adaptations as adapt_module

    today = datetime.date.today()
    upcoming = _macro_upcoming_sessions(today)

    execute_sessions = MagicMock()
    execute_sessions.data = upcoming
    execute_profiles = MagicMock()
    execute_profiles.data = [{"constraints": {}}]
    execute_pmc = MagicMock()
    execute_pmc.data = [{"ctl": 50, "atl": 40}]
    execute_supersede = MagicMock()
    execute_supersede.data = []
    execute_insert = MagicMock()
    execute_insert.data = [{"id": "adaptation-macro-001"}]

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.update.return_value = mock_client
    mock_client.insert.return_value = mock_client
    mock_client.execute = AsyncMock(side_effect=[
        execute_sessions, execute_profiles, execute_pmc, execute_supersede, execute_insert,
    ])

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    signals = [_sig("missed", "sess-a"), _sig("missed", "sess-b")]
    result = await adapt_module.apply_macro_replan(TEST_USER_ID, signals)

    assert result["status"] == "needs_confirmation"
    assert result["scope"] == "macro"
    assert result["adaptation_id"] == "adaptation-macro-001"
    assert result["change_summary"]["shift_check"]["requires_user_confirmation"] is True

    # No sessions update call (tss_target/scheduled_date) was ever issued -- nothing applied.
    session_update_calls = [
        c for c in mock_client.update.call_args_list
        if "tss_target" in c.args[0] and "scheduled_date" in c.args[0]
    ]
    assert session_update_calls == [], "guard fired -- sessions must not be updated"


async def test_apply_macro_replan_supersedes_prior_proposal(monkeypatch):
    """
    OQ1: before persisting a new proposed macro replan, any prior status='proposed'
    rows for this user are superseded.
    """
    import backend.routes.adaptations as adapt_module

    today = datetime.date.today()
    upcoming = _macro_upcoming_sessions(today)

    execute_sessions = MagicMock()
    execute_sessions.data = upcoming
    execute_profiles = MagicMock()
    execute_profiles.data = [{"constraints": {}}]
    execute_pmc = MagicMock()
    execute_pmc.data = [{"ctl": 50, "atl": 40}]
    execute_supersede = MagicMock()
    execute_supersede.data = []
    execute_insert = MagicMock()
    execute_insert.data = [{"id": "adaptation-macro-002"}]

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.update.return_value = mock_client
    mock_client.insert.return_value = mock_client
    mock_client.execute = AsyncMock(side_effect=[
        execute_sessions, execute_profiles, execute_pmc, execute_supersede, execute_insert,
    ])

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    signals = [_sig("missed", "sess-a"), _sig("missed", "sess-b")]
    result = await adapt_module.apply_macro_replan(TEST_USER_ID, signals)

    assert result["status"] == "needs_confirmation"

    # A supersede UPDATE (status='superseded') happened before the new proposal's insert.
    supersede_calls = [c for c in mock_client.update.call_args_list if c.args[0] == {"status": "superseded"}]
    assert len(supersede_calls) == 1

    proposed_inserts = [c for c in mock_client.insert.call_args_list if c.args[0].get("status") == "proposed"]
    assert len(proposed_inserts) == 1
    assert proposed_inserts[0].args[0]["trigger_session_ids"] == ["sess-a", "sess-b"]


# ---------------------------------------------------------------------------
# ADAPT-04: test_weekly_check
# ---------------------------------------------------------------------------


async def test_weekly_check(monkeypatch):
    """
    ADAPT-04: POST /adaptations/check returns signals and scope independently of uploads.
    When no signals are detected, response is {"signals": [], "scope": None, "result": None}.
    Phase 4: request requires a valid JWT in the Authorization: Bearer header.
    """
    from backend.main import app
    import backend.routes.adaptations as adapt_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    # detect_signals returns empty list -- no sessions in DB.
    execute_result = MagicMock()
    execute_result.data = []

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.in_.return_value = mock_client
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
            headers=auth_headers(),
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
    import backend.routes.adaptations as adapt_module
    from backend.sports_science.compliance import validate_session_vs_actual

    today = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=1)).isoformat()

    # A session with planned TSS 80; the ride only achieved 40 (50% compliance -> underperformance).
    # Status 'completed' because the ride-upload pipeline flips a matched session to
    # 'completed' before an underperformance signal can fire (Pattern 5).
    sessions_data = [
        {"id": "sess-underperf", "scheduled_date": yesterday, "tss_target": 80, "plan_id": None, "status": "completed"}
    ]
    rides_data = [
        {"id": "ride-001", "ride_date": yesterday, "tss": 40.0, "session_id": "sess-underperf"}
    ]

    # No prior adaptations rows for this user -- nothing already consumed.
    execute_consumed = MagicMock()
    execute_consumed.data = []

    execute_sessions = MagicMock()
    execute_sessions.data = sessions_data
    execute_rides = MagicMock()
    execute_rides.data = rides_data

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.in_.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.lt.return_value = mock_client
    mock_client.lte.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.execute = AsyncMock(side_effect=[execute_consumed, execute_sessions, execute_rides])

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
    import backend.routes.adaptations as adapt_module

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
    TRANSP-03: GET /adaptations/ returns a list of adaptation records for the authenticated user.
    Phase 4: user_id comes from the JWT; no user_id query param needed.
    """
    from backend.main import app
    import backend.routes.adaptations as adapt_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

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
            headers=auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "adapt-001"
    assert data[0]["trigger"] == "missed"


async def test_get_adaptations_requires_auth():
    """
    TRANSP-03 (Phase 4): GET /adaptations/ without a JWT returns 401.
    Previously tested for 422 (missing user_id query param); now tests for 401 (no auth).
    """
    from backend.main import app

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/adaptations/")

    assert response.status_code == 401
