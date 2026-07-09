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
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from httpx import ASGITransport

from tests.api.conftest import TEST_JWT_SECRET, TEST_USER_ID, auth_headers, mock_supabase_factory

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
        {
            "id": "sess-001",
            "scheduled_date": yesterday,
            "tss_target": 60,
            "plan_id": None,
            "status": "planned",
        }
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
        {
            "id": "sess-001",
            "scheduled_date": yesterday,
            "tss_target": 60,
            "plan_id": None,
            "status": "planned",
        }
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
# WR-05: ride query window widened by the +/-1 day match tolerance
# ---------------------------------------------------------------------------


async def test_ride_query_window_includes_match_tolerance(monkeypatch):
    """
    WR-05: the rides query lower bound must be window_start - 1 day so a ride
    the day before a session scheduled exactly on window_start is still loaded
    (otherwise the session is falsely flagged missed).
    """
    import backend.routes.adaptations as adapt_module

    today = datetime.date.today()
    window_days = 7
    expected_lower = (today - datetime.timedelta(days=window_days + 1)).isoformat()

    rides_gte_calls: list[tuple] = []

    empty = MagicMock()
    empty.data = []

    def _make_chain(record_gte=False):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.in_.return_value = chain
        chain.lte.return_value = chain
        if record_gte:
            def _capture_gte(field, value):
                rides_gte_calls.append((field, value))
                return chain
            chain.gte = MagicMock(side_effect=_capture_gte)
        else:
            chain.gte.return_value = chain
        chain.execute = AsyncMock(return_value=empty)
        return chain

    rides_chain = _make_chain(record_gte=True)
    other_chain = _make_chain()

    mock_client = MagicMock()
    mock_client.table = MagicMock(
        side_effect=lambda name: rides_chain if name == "rides" else other_chain
    )

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    await adapt_module.detect_signals(TEST_USER_ID, window_days=window_days)

    assert ("ride_date", expected_lower) in rides_gte_calls, (
        f"rides query must widen the window by the 1-day tolerance: {rides_gte_calls}"
    )


# ---------------------------------------------------------------------------
# CR-04: consumed-ids query only considers acted-on adaptations
# ---------------------------------------------------------------------------


async def test_consumed_ids_exclude_superseded_proposals(monkeypatch):
    """
    CR-04: the Pattern-5 consumed-ids pre-query must be scoped to
    status in ('applied', 'proposed'). A superseded proposal must release its
    trigger sessions so their signals can re-fire.
    """
    import backend.routes.adaptations as adapt_module

    today = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=2)).isoformat()

    sessions_data = [
        {
            "id": "sess-001",
            "scheduled_date": yesterday,
            "tss_target": 60,
            "plan_id": None,
            "status": "planned",
        }
    ]

    adaptations_in_calls: list[tuple] = []

    execute_consumed = MagicMock()
    # DB-side status filter applied -- the superseded row's ids are NOT returned.
    execute_consumed.data = []
    execute_sessions = MagicMock()
    execute_sessions.data = sessions_data
    execute_rides = MagicMock()
    execute_rides.data = []

    adaptations_chain = MagicMock()
    adaptations_chain.select.return_value = adaptations_chain
    adaptations_chain.eq.return_value = adaptations_chain

    def _capture_in(field, values):
        adaptations_in_calls.append((field, values))
        return adaptations_chain

    adaptations_chain.in_ = MagicMock(side_effect=_capture_in)
    adaptations_chain.execute = AsyncMock(return_value=execute_consumed)

    other_chain = MagicMock()
    other_chain.select.return_value = other_chain
    other_chain.eq.return_value = other_chain
    other_chain.in_.return_value = other_chain
    other_chain.gte.return_value = other_chain
    other_chain.lte.return_value = other_chain
    other_chain.execute = AsyncMock(side_effect=[execute_sessions, execute_rides])

    mock_client = MagicMock()
    mock_client.table = MagicMock(
        side_effect=lambda name: adaptations_chain if name == "adaptations" else other_chain
    )

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    signals = await adapt_module.detect_signals(TEST_USER_ID)

    # The consumed-ids query is status-scoped to acted-on adaptations only.
    assert ("status", ["applied", "proposed"]) in adaptations_in_calls, (
        f"consumed-ids query missing status scope: {adaptations_in_calls}"
    )
    # With the superseded proposal excluded, the session's missed signal re-fires.
    assert signals == [{"type": "missed", "session_id": "sess-001"}]


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
        {
            "id": "sess-next-1",
            "scheduled_date": today.isoformat(),
            "tss_target": 60,
            "duration_minutes": 60,
            "status": "planned",
        },
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
        _original_eq = chain.eq

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


async def test_apply_micro_adjustment_null_tss_target_not_zeroed(monkeypatch):
    """
    CR-01: a session with tss_target=NULL must NOT have 0.0 written over it by
    the micro adjustment -- TSS scaling is skipped, duration scaling still runs.
    """
    import backend.routes.adaptations as adapt_module

    today = datetime.date.today()

    upcoming = [
        {
            "id": "sess-null-tss",
            "scheduled_date": today.isoformat(),
            "tss_target": None,
            "duration_minutes": 60,
            "status": "planned",
        },
    ]
    execute_upcoming = MagicMock()
    execute_upcoming.data = upcoming
    execute_generic = MagicMock()
    execute_generic.data = [{"id": "adaptation-uuid-null-tss"}]

    update_payloads: list[dict] = []

    class _Chain:
        def eq(self, field, value):
            return self

        async def execute(self):
            return execute_generic

    mock_client = MagicMock()

    def _update(payload):
        update_payloads.append(payload)
        return _Chain()

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

    signal = _sig(type_="underperformance", session_id="sess-trigger", compliance_pct=40.0)
    result = await adapt_module.apply_micro_adjustment(TEST_USER_ID, signal)

    assert result["status"] == "applied"
    session_updates = [p for p in update_payloads if "duration_minutes" in p]
    assert len(session_updates) == 1
    assert "tss_target" not in session_updates[0], (
        f"NULL tss_target must not be scaled into a value: {session_updates[0]}"
    )
    assert session_updates[0]["duration_minutes"] == 48.0


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


def _macro_upcoming_sessions(today, n=7):
    """
    CR-03: the fixed generator shifts session i by i // 2 days, so the 30%
    guard only fires with 6+ upcoming sessions (shifted = n - 4 for n > 4).
    Default n=7 (3/7 = 43% > 30%) keeps the needs_confirmation tests valid;
    pass n <= 5 to exercise the auto-apply branch.
    """
    ids = ["sess-a", "sess-b", "sess-c", "sess-d", "sess-e", "sess-f", "sess-g"]
    return [
        {
            "id": ids[i],
            "scheduled_date": (today + datetime.timedelta(days=1 + 2 * i)).isoformat(),
            "tss_target": 60,
            "duration_minutes": 60,
            "status": "planned",
        }
        for i in range(n)
    ]


async def test_apply_macro_replan_shift_limit_fires(monkeypatch):
    """
    ADAPT-03, D-19: with 7 upcoming sessions the i // 2 spacing shifts 3 of 7
    (43% > 30%) so the guard fires. When it fires, needs_confirmation is
    returned and NO session rows are updated with tss_target/scheduled_date.
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


async def test_apply_macro_replan_small_shift_auto_applies(monkeypatch):
    """
    CR-03: a macro replan whose reschedule shifts <= 30% of sessions by more
    than 1 day must auto-apply (status='applied'), update the session rows,
    flip missed trigger sessions, and log an applied adaptation. With the old
    i + 2 spacing this branch was unreachable dead code.
    """
    import backend.routes.adaptations as adapt_module

    today = datetime.date.today()
    upcoming = _macro_upcoming_sessions(today, n=4)  # i // 2 shifts: 0,0,1,1 -> 0 shifted

    execute_sessions = MagicMock()
    execute_sessions.data = upcoming
    execute_profiles = MagicMock()
    execute_profiles.data = [{"constraints": {}}]
    execute_pmc = MagicMock()
    execute_pmc.data = [{"ctl": 50, "atl": 40}]
    execute_generic = MagicMock()
    execute_generic.data = [{"id": "adaptation-applied-001"}]

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.gte.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.update.return_value = mock_client
    mock_client.insert.return_value = mock_client
    mock_client.execute = AsyncMock(
        side_effect=[execute_sessions, execute_profiles, execute_pmc] + [execute_generic] * 12
    )

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    signals = [_sig("missed", "sess-a"), _sig("underperformance", "sess-b", 40.0)]
    result = await adapt_module.apply_macro_replan(TEST_USER_ID, signals)

    assert result["status"] == "applied", (
        f"Small-shift macro replan must auto-apply, got {result['status']}"
    )
    assert result["scope"] == "macro"
    assert result["adaptation_id"] == "adaptation-applied-001"
    assert result["sessions_adjusted"] == ["sess-a", "sess-b", "sess-c", "sess-d"]

    # Session rows were actually updated (the apply branch ran).
    session_update_calls = [
        c for c in mock_client.update.call_args_list if "scheduled_date" in c.args[0]
    ]
    assert len(session_update_calls) == 4, "expected one UPDATE per upcoming session"

    # The missed trigger session was flipped to status='missed' (Pattern 5).
    missed_flip_calls = [
        c for c in mock_client.update.call_args_list if c.args[0] == {"status": "missed"}
    ]
    assert len(missed_flip_calls) == 1

    # The adaptation was logged with default status 'applied' and consumed both triggers.
    applied_inserts = [
        c for c in mock_client.insert.call_args_list
        if isinstance(c.args[0], dict) and c.args[0].get("status") == "applied"
    ]
    assert len(applied_inserts) == 1
    assert applied_inserts[0].args[0]["trigger_session_ids"] == ["sess-a", "sess-b"]


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
    supersede_calls = [
        c for c in mock_client.update.call_args_list if c.args[0] == {"status": "superseded"}
    ]
    assert len(supersede_calls) == 1

    proposed_inserts = [
        c for c in mock_client.insert.call_args_list if c.args[0].get("status") == "proposed"
    ]
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
    import backend.routes.adaptations as adapt_module
    from backend.main import app

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
        {
            "id": "sess-underperf",
            "scheduled_date": yesterday,
            "tss_target": 80,
            "plan_id": None,
            "status": "completed",
        }
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
    assert len(call_log) >= 1, (
        "validate_session_vs_actual was not called -- "
        "compliance check bypassed (ADAPT-05 violation)"
    )
    assert call_log[0]["planned"]["tss"] == 80
    assert call_log[0]["actual"]["tss"] == 40.0

    # 50% compliance -> tool flags 'under_performed' (< 70%) -> signal present.
    assert len(signals) == 1
    assert signals[0]["type"] == "underperformance"
    assert signals[0]["compliance_pct"] == pytest.approx(50.0, abs=0.1)


async def test_underperformance_uses_tool_flag_threshold(monkeypatch):
    """
    WR-07: a 65%-compliance session is flagged under_performed by the tool
    (< 70%) and must produce a signal -- the old hardcoded route literal (< 60)
    silently ignored the tool's own decision.
    """
    import backend.routes.adaptations as adapt_module

    today = datetime.date.today()
    yesterday = (today - datetime.timedelta(days=1)).isoformat()

    sessions_data = [
        {
            "id": "sess-65pct",
            "scheduled_date": yesterday,
            "tss_target": 100,
            "plan_id": None,
            "status": "completed",
        }
    ]
    rides_data = [
        {"id": "ride-65", "ride_date": yesterday, "tss": 65.0, "session_id": "sess-65pct"}
    ]

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
    mock_client.lte.return_value = mock_client
    mock_client.execute = AsyncMock(side_effect=[execute_consumed, execute_sessions, execute_rides])

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    signals = await adapt_module.detect_signals(TEST_USER_ID)

    assert len(signals) == 1, (
        f"65% compliance is under_performed per the tool (< 70) and must signal: {signals}"
    )
    assert signals[0]["type"] == "underperformance"
    assert signals[0]["compliance_pct"] == pytest.approx(65.0, abs=0.1)


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
    import backend.routes.adaptations as adapt_module
    from backend.main import app

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


# ---------------------------------------------------------------------------
# CR-02 / D-16: POST /adaptations/sessions/{id}/missed synthesizes its signal
# ---------------------------------------------------------------------------


async def test_mark_missed_synthesizes_signal_for_marked_session(monkeypatch):
    """
    CR-02: the mark-missed endpoint flips the session to 'missed', which
    excludes it from detect_signals' planned/completed scan. The endpoint must
    synthesize the missed signal for the marked session so the manual report
    actually triggers an adaptation (here: micro, since it is the only signal).
    """
    import backend.routes.adaptations as adapt_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    session_id = "33333333-3333-3333-3333-333333333333"

    execute_session_lookup = MagicMock()
    execute_session_lookup.data = [{"id": session_id, "user_id": TEST_USER_ID, "status": "planned"}]
    execute_generic = MagicMock()
    execute_generic.data = []

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.in_.return_value = mock_client
    mock_client.update.return_value = mock_client
    # First execute: ownership lookup; all later ones (status flip, consumed
    # pre-query) return empty data.
    mock_client.execute = AsyncMock(
        side_effect=[execute_session_lookup, execute_generic, execute_generic]
    )

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    # detect_signals returns nothing -- the flipped session is invisible to it.
    monkeypatch.setattr(adapt_module, "detect_signals", AsyncMock(return_value=[]))

    micro_calls: list = []

    async def _capturing_micro(user_id, signal):
        micro_calls.append((user_id, signal))
        return {"status": "applied", "scope": "micro", "after": [], "before": [],
                "sessions_adjusted": [], "explanation": "x", "adaptation_id": "a-1"}

    monkeypatch.setattr(adapt_module, "apply_micro_adjustment", _capturing_micro)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/adaptations/sessions/{session_id}/missed",
            headers=auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["marked_missed"] is True
    assert data["signals"] == [{"type": "missed", "session_id": session_id}], (
        f"Expected the marked session's synthesized missed signal: {data['signals']}"
    )
    assert data["scope"] == "micro"
    assert len(micro_calls) == 1
    assert micro_calls[0][1] == {"type": "missed", "session_id": session_id}


async def test_mark_missed_skips_synthesis_when_already_consumed(monkeypatch):
    """
    CR-02 + Pattern 5: if a prior adaptation already consumed the session,
    marking it missed again must NOT re-fire a signal.
    """
    import backend.routes.adaptations as adapt_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    session_id = "44444444-4444-4444-4444-444444444444"

    execute_session_lookup = MagicMock()
    execute_session_lookup.data = [{"id": session_id, "user_id": TEST_USER_ID, "status": "planned"}]
    execute_flip = MagicMock()
    execute_flip.data = []
    execute_consumed = MagicMock()
    execute_consumed.data = [{"trigger_session_ids": [session_id]}]

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.in_.return_value = mock_client
    mock_client.update.return_value = mock_client
    mock_client.execute = AsyncMock(
        side_effect=[execute_session_lookup, execute_flip, execute_consumed]
    )

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)
    monkeypatch.setattr(adapt_module, "detect_signals", AsyncMock(return_value=[]))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/adaptations/sessions/{session_id}/missed",
            headers=auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data["signals"] == [], "consumed session must not re-fire a synthesized signal"
    assert data["scope"] is None
    assert data["result"] is None


async def test_confirm_macro_applies_stored_snapshot(monkeypatch):
    """
    Pattern 6: confirming a proposed macro replan applies the STORED after_snapshot
    sessions verbatim (not a freshly recomputed one) and flips the adaptation's
    status to 'applied'.
    """
    import backend.routes.adaptations as adapt_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    adaptation_id = "11111111-1111-1111-1111-111111111111"
    proposal_row = {
        "id": adaptation_id,
        "user_id": TEST_USER_ID,
        "status": "proposed",
        "after_snapshot": {
            "sessions": [
                {"id": "sess-x", "tss_target": 42.0, "scheduled_date": "2026-07-10"},
            ],
        },
    }

    execute_select = MagicMock()
    execute_select.data = [proposal_row]
    execute_session_update = MagicMock()
    execute_session_update.data = [{"id": "sess-x"}]
    execute_status_update = MagicMock()
    execute_status_update.data = [{"id": adaptation_id, "status": "applied"}]

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.update.return_value = mock_client
    mock_client.execute = AsyncMock(
        side_effect=[execute_select, execute_session_update, execute_status_update]
    )

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/adaptations/{adaptation_id}/confirm",
            headers=auth_headers(),
        )

    assert response.status_code == 200
    data = response.json()
    assert data == {"status": "applied", "adaptation_id": adaptation_id}

    # The applied session payload matches the STORED snapshot verbatim.
    session_update_calls = [
        c for c in mock_client.update.call_args_list if "tss_target" in c.args[0]
    ]
    assert len(session_update_calls) == 1
    assert session_update_calls[0].args[0] == {"tss_target": 42.0, "scheduled_date": "2026-07-10"}

    # The adaptation row itself flips to 'applied'.
    status_update_calls = [
        c for c in mock_client.update.call_args_list if c.args[0] == {"status": "applied"}
    ]
    assert len(status_update_calls) == 1


async def test_confirm_macro_idor_returns_404(monkeypatch):
    """
    T-06-04: an adaptation id that does not resolve under the id+user_id+status='proposed'
    dual-filter (foreign owner, missing, or already applied/superseded) returns 404
    proposal_not_found -- nothing is applied.
    """
    import backend.routes.adaptations as adapt_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    foreign_adaptation_id = "22222222-2222-2222-2222-222222222222"

    execute_select = MagicMock()
    execute_select.data = []  # dual-filter matched nothing for this user

    mock_client = MagicMock()
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.update.return_value = mock_client
    mock_client.execute = AsyncMock(return_value=execute_select)

    async def _mock_supabase():
        return mock_client

    monkeypatch.setattr(adapt_module, "_get_async_supabase", _mock_supabase)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/adaptations/{foreign_adaptation_id}/confirm",
            headers=auth_headers(),
        )

    assert response.status_code == 404
    assert response.json()["detail"]["error"] == "proposal_not_found"
    assert mock_client.update.call_args_list == [], "no update must occur on a 404 proposal lookup"
