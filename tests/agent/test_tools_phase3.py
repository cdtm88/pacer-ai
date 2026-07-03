# tests/agent/test_tools_phase3.py
"""
Phase 3 tool registry and sports_science unit tests.

TRUST-02: TOOL_REGISTRY and TOOL_SCHEMAS must have the same name set and
exactly 10 entries after adding save_profile and generate_plan.

generate_plan unit tests: call the sync function directly (no mocking).
save_profile unit test: mock _get_async_supabase (async Supabase write).

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
import json
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# TRUST-02: registry/schema invariant check
# ---------------------------------------------------------------------------


def test_trust02_still_passes_after_new_tools():
    """
    TRUST-02: TOOL_REGISTRY and TOOL_SCHEMAS must have exactly the same names.
    After Wave 1, both must have 10 entries: 8 original + save_profile + generate_plan.
    """
    from backend.agent.tools import TOOL_REGISTRY, TOOL_SCHEMAS

    schema_names = {s["name"] for s in TOOL_SCHEMAS}
    registry_names = set(TOOL_REGISTRY)

    assert schema_names == registry_names, (
        f"TRUST-02: schema names {schema_names} != registry keys {registry_names}"
    )
    assert len(TOOL_REGISTRY) == 10, (
        f"Expected 10 tools in TOOL_REGISTRY, got {len(TOOL_REGISTRY)}"
    )
    assert len(TOOL_SCHEMAS) == 10, (
        f"Expected 10 schemas in TOOL_SCHEMAS, got {len(TOOL_SCHEMAS)}"
    )
    assert "save_profile" in registry_names
    assert "generate_plan" in registry_names


# ---------------------------------------------------------------------------
# generate_plan unit tests (sync, no DB, no mocking)
# ---------------------------------------------------------------------------


def test_generate_plan():
    """Basic generate_plan call returns 4-week mesocycle with correct shape."""
    from backend.sports_science.plan import generate_plan

    result = generate_plan(
        user_id="u1",
        weekly_hours=3.0,
        back_status="none",
        current_ctl=0.0,
        load_targets={"recommended_ctl_target": 8.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="medium",
        ftp_watts=200.0,
    )

    assert result.value["mesocycle_weeks"] == 4
    assert result.value["plan_id"] is None
    assert result.value["week4_volume_reduction_pct"] == 40
    assert isinstance(result.value["sessions"], list)
    assert len(result.value["sessions"]) > 0
    assert result.methodology == "mesocycle_plan_generation"


def test_cold_start_hr_only():
    """Cold-start plan (ftp_confidence=insufficient_data) has no power targets and uses HR zones."""
    from backend.sports_science.plan import generate_plan

    result = generate_plan(
        user_id="u1",
        weekly_hours=3.0,
        back_status="none",
        current_ctl=0.0,
        load_targets={"recommended_ctl_target": 8.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="insufficient_data",
        ftp_watts=None,
    )

    for session in result.value["sessions"]:
        assert session.get("zone_targets") is not None, (
            "Cold-start sessions must have zone_targets (HR-based)"
        )


def test_power_targets_cold_start():
    """All sessions in a cold-start plan have power_targets == None (D-07)."""
    from backend.sports_science.plan import generate_plan

    result = generate_plan(
        user_id="u1",
        weekly_hours=3.0,
        back_status="none",
        current_ctl=0.0,
        load_targets={"recommended_ctl_target": 8.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="insufficient_data",
        ftp_watts=None,
    )

    for session in result.value["sessions"]:
        assert session["power_targets"] is None, (
            f"Week {session['week']} session should have power_targets=None in cold start, "
            f"got {session['power_targets']}"
        )


def test_session_schema():
    """Each session has the required keys: week, day, type, objective, duration_minutes, structure, zone_targets, power_targets, rpe_target."""
    from backend.sports_science.plan import generate_plan

    result = generate_plan(
        user_id="u1",
        weekly_hours=2.0,
        back_status="none",
        current_ctl=0.0,
        load_targets={"recommended_ctl_target": 8.0},
        hr_zones=[{"zone": 2, "lower_bpm": 115, "upper_bpm": 140}],
        ftp_confidence="insufficient_data",
        ftp_watts=None,
    )

    required_keys = {
        "week", "day", "type", "objective", "duration_minutes",
        "structure", "zone_targets", "power_targets", "rpe_target",
    }
    for session in result.value["sessions"]:
        missing = required_keys - set(session.keys())
        assert not missing, f"Session missing keys: {missing}, session: {session}"
        # Structure must have warmup, main_set, cooldown
        assert "warmup" in session["structure"]
        assert "main_set" in session["structure"]
        assert "cooldown" in session["structure"]


def test_back_constraints():
    """
    back_status='moderate' applies back-protective constraints:
    - Weeks 1-2: duration_minutes <= 30
    - Week 1: no session with type == 'strength'
    """
    from backend.sports_science.plan import generate_plan

    result = generate_plan(
        user_id="u1",
        weekly_hours=3.0,
        back_status="moderate",
        current_ctl=0.0,
        load_targets={"recommended_ctl_target": 8.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="insufficient_data",
        ftp_watts=None,
    )

    sessions = result.value["sessions"]

    # D-05: weeks 1-2 must be capped at 30 minutes for moderate back_status
    for session in sessions:
        if session["week"] in (1, 2):
            assert session["duration_minutes"] <= 30, (
                f"Week {session['week']} session duration {session['duration_minutes']} "
                f"exceeds 30-minute cap for moderate back_status"
            )

    # D-05: no strength sessions in week 1
    week1_sessions = [s for s in sessions if s["week"] == 1]
    for session in week1_sessions:
        assert session["type"] != "strength", (
            f"Week 1 should have no 'strength' sessions with moderate back_status, "
            f"got type={session['type']}"
        )

    # constraints_applied should include back_protective
    assert "back_protective" in result.value["constraints_applied"], (
        "constraints_applied must include 'back_protective' for moderate back_status"
    )


def test_generate_plan_sessions_have_tss_target():
    """
    CR-01: every generated session must carry a positive, tool-derived
    tss_target so downstream detection/compliance/adjustment paths work.
    """
    from backend.sports_science.plan import generate_plan

    result = generate_plan(
        user_id="u1",
        weekly_hours=3.0,
        back_status="none",
        current_ctl=0.0,
        load_targets={"recommended_ctl_target": 8.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="medium",
        ftp_watts=200.0,
    )

    for session in result.value["sessions"]:
        assert session.get("tss_target") is not None, (
            f"Week {session['week']} {session['day']} session has no tss_target"
        )
        assert session["tss_target"] > 0

    # Recovery sessions (zone 1) must have a lower TSS-per-minute than
    # endurance sessions (zone 2) -- the IF mapping must actually discriminate.
    endurance = next(s for s in result.value["sessions"] if s["type"] == "endurance")
    recovery = next(s for s in result.value["sessions"] if s["type"] == "recovery")
    assert (recovery["tss_target"] / recovery["duration_minutes"]) < (
        endurance["tss_target"] / endurance["duration_minutes"]
    )


# ---------------------------------------------------------------------------
# save_profile unit test (async, mocked Supabase)
# ---------------------------------------------------------------------------


async def test_save_profile_upserts(monkeypatch):
    """
    save_profile upserts to the profiles table and returns ToolResult with saved=True.
    Supabase client is mocked -- no real DB connection.
    """
    import backend.sports_science.profile as profile_module

    mock_client = MagicMock()
    mock_client.table.return_value.upsert.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "profile-uuid-001"}])
    )
    monkeypatch.setattr(profile_module, "_supabase_client", mock_client)

    from backend.sports_science.profile import save_profile

    result = await save_profile(
        user_id="u1",
        fitness_goals="weight loss and general fitness",
        weekly_hours=3.0,
        preferred_days=["Tuesday", "Thursday", "Saturday"],
        back_status="none",
        equipment={"trainer": "Wahoo Kickr Core", "platform": "Zwift"},
        rpe_baseline="beginner",
        lthr_estimate=None,
    )

    assert result.value["saved"] is True
    assert result.value["profile_id"] == "profile-uuid-001"
    assert result.methodology == "profile_persistence"


def test_week1_rollforward_avoids_week2_collision():
    """
    WR-02: a Week-1 session whose weekday precedes confirm_date rolls +7 days,
    which would land exactly on the Week-2 session for that weekday. The
    resolver must place it on the earliest free date on/after confirm_date
    instead -- no two sessions may ever share a scheduled_date.
    """
    import datetime
    from backend.agent.tools import _resolve_all_scheduled_dates

    confirm = datetime.date(2026, 7, 1)  # a Wednesday
    sessions = [
        {"week": 1, "day": "Tuesday"},   # 2026-06-30 < confirm -> rolls to 07-07
        {"week": 1, "day": "Thursday"},  # 2026-07-02, no roll
        {"week": 2, "day": "Tuesday"},   # 2026-07-07 (the collision slot)
        {"week": 2, "day": "Thursday"},  # 2026-07-09
    ]

    dates = _resolve_all_scheduled_dates(confirm, sessions)

    assert len(set(dates)) == len(dates), f"duplicate scheduled_dates: {dates}"
    # No Week-1 session in the past.
    for session, d in zip(sessions, dates):
        if session["week"] == 1:
            assert d >= confirm, f"Week-1 session scheduled in the past: {d}"
    # The Week-2 Tuesday keeps its slot; the rolled Week-1 Tuesday moved elsewhere.
    assert dates[2] == datetime.date(2026, 7, 7)
    assert dates[0] != datetime.date(2026, 7, 7)


def test_resolve_all_dates_no_roll_matches_single_resolver():
    """WR-02 regression: sessions needing no roll keep _resolve_scheduled_date's result."""
    import datetime
    from backend.agent.tools import _resolve_all_scheduled_dates, _resolve_scheduled_date

    confirm = datetime.date(2026, 6, 29)  # a Monday -- nothing rolls
    sessions = [
        {"week": w, "day": d}
        for w in (1, 2, 3, 4)
        for d in ("Tuesday", "Thursday", "Saturday")
    ]

    dates = _resolve_all_scheduled_dates(confirm, sessions)

    for session, resolved in zip(sessions, dates):
        assert resolved == _resolve_scheduled_date(confirm, session["week"], session["day"])
    assert len(set(dates)) == len(dates)


class _FakeToolUseBlock:
    """Minimal stand-in for an Anthropic tool_use content block."""

    def __init__(self, name: str, input: dict, id: str = "toolu_test"):
        self.name = name
        self.input = input
        self.id = id


def _generate_plan_inputs(user_id_in_llm_input: str = "user_supplied_should_be_ignored") -> dict:
    return {
        "user_id": user_id_in_llm_input,
        "weekly_hours": 3.0,
        "back_status": "none",
        "current_ctl": 0.0,
        "load_targets": {"recommended_ctl_target": 8.0},
        "hr_zones": [{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        "ftp_confidence": "medium",
        "ftp_watts": 200.0,
    }


def _mock_persistence_supabase(plan_id: str, session_id_prefix: str = "sess"):
    """
    Mock Supabase client whose plans/sessions inserts return fixed ids.
    Distinguishes plans vs sessions inserts by inspecting the table name.
    """
    class _MockQuery:
        def __init__(self, table_name):
            self._table_name = table_name
            self._payload = None

        def insert(self, payload):
            self._payload = payload
            return self

        async def execute(self):
            if self._table_name == "plans":
                return MagicMock(data=[{"id": plan_id}])
            # sessions: one row per inserted session, in order
            rows = [
                {"id": f"{session_id_prefix}-{i}"} for i in range(len(self._payload))
            ]
            return MagicMock(data=rows)

    class _MockClient:
        def table(self, name):
            return _MockQuery(name)

    return _MockClient()


async def test_dispatch_tool_persists_generate_plan(monkeypatch):
    """
    T-06-02 (happy path): dispatching a generate_plan tool_use block persists
    a plans row and sessions rows via a mocked Supabase client, and rewrites
    result.value['plan_id'] to the mocked plan UUID.
    """
    import backend.agent.tools as tools_module

    mock_client = _mock_persistence_supabase(plan_id="mock-plan-uuid-001")

    async def _mock_get_async_supabase():
        return mock_client

    monkeypatch.setattr(tools_module, "_get_async_supabase", _mock_get_async_supabase)

    block = _FakeToolUseBlock("generate_plan", _generate_plan_inputs())
    audit_log: list = []

    tool_result = await tools_module.dispatch_tool(
        block, audit_log, user_id="00000000-0000-0000-0000-000000000042"
    )

    assert tool_result["is_error"] is False
    payload = json.loads(tool_result["content"][0]["text"])
    assert payload["value"]["plan_id"] == "mock-plan-uuid-001"
    assert len(payload["value"]["sessions"]) > 0
    for session in payload["value"]["sessions"]:
        assert session.get("id", "").startswith("sess-")


async def test_persist_generated_plan_writes_tss_target(monkeypatch):
    """
    CR-01 regression: _persist_generated_plan must include a non-NULL positive
    tss_target in every inserted sessions row.
    """
    import backend.agent.tools as tools_module

    captured_session_rows: list = []

    class _MockQuery:
        def __init__(self, table_name):
            self._table_name = table_name
            self._payload = None

        def insert(self, payload):
            self._payload = payload
            if self._table_name == "sessions":
                captured_session_rows.extend(payload)
            return self

        async def execute(self):
            if self._table_name == "plans":
                return MagicMock(data=[{"id": "mock-plan-uuid-tss"}])
            rows = [{"id": f"sess-{i}"} for i in range(len(self._payload))]
            return MagicMock(data=rows)

    class _MockClient:
        def table(self, name):
            return _MockQuery(name)

    async def _mock_get_async_supabase():
        return _MockClient()

    monkeypatch.setattr(tools_module, "_get_async_supabase", _mock_get_async_supabase)

    block = _FakeToolUseBlock("generate_plan", _generate_plan_inputs())
    audit_log: list = []

    tool_result = await tools_module.dispatch_tool(
        block, audit_log, user_id="00000000-0000-0000-0000-000000000042"
    )

    assert tool_result["is_error"] is False
    assert len(captured_session_rows) > 0
    for row in captured_session_rows:
        assert row.get("tss_target") is not None, (
            f"sessions insert row missing tss_target: {row}"
        )
        assert row["tss_target"] > 0


async def test_dispatch_tool_generate_plan_uses_injected_user_id(monkeypatch):
    """
    T-06-02 (regression): the persisted user_id must be the dispatch-injected
    identity, never the user_id the LLM supplied in tool_use_block.input.
    """
    import backend.agent.tools as tools_module

    captured_user_ids: list = []

    class _MockQuery:
        def __init__(self, table_name):
            self._table_name = table_name
            self._payload = None

        def insert(self, payload):
            self._payload = payload
            if self._table_name == "plans":
                captured_user_ids.append(payload["user_id"])
            elif self._table_name == "sessions":
                for row in payload:
                    captured_user_ids.append(row["user_id"])
            return self

        async def execute(self):
            if self._table_name == "plans":
                return MagicMock(data=[{"id": "mock-plan-uuid-002"}])
            rows = [{"id": f"sess-{i}"} for i in range(len(self._payload))]
            return MagicMock(data=rows)

    class _MockClient:
        def table(self, name):
            return _MockQuery(name)

    async def _mock_get_async_supabase():
        return _MockClient()

    monkeypatch.setattr(tools_module, "_get_async_supabase", _mock_get_async_supabase)

    injected_user_id = "00000000-0000-0000-0000-000000000042"
    llm_supplied_user_id = "attacker-supplied-user-id"
    block = _FakeToolUseBlock("generate_plan", _generate_plan_inputs(llm_supplied_user_id))
    audit_log: list = []

    await tools_module.dispatch_tool(block, audit_log, user_id=injected_user_id)

    assert len(captured_user_ids) > 0
    assert all(uid == injected_user_id for uid in captured_user_ids), (
        f"Expected every persisted user_id to be the injected identity "
        f"{injected_user_id}, got {captured_user_ids}"
    )
    assert llm_supplied_user_id not in captured_user_ids


async def test_dispatch_tool_fails_closed_without_server_identity():
    """
    WR-01: save_profile/generate_plan dispatched with user_id=None must fail
    closed with an is_error tool_result -- an LLM-supplied user_id must never
    reach a service-role write.
    """
    import backend.agent.tools as tools_module

    for tool_name, tool_inputs in [
        ("generate_plan", _generate_plan_inputs("llm-injected-user")),
        ("save_profile", {
            "user_id": "llm-injected-user",
            "fitness_goals": "x",
            "weekly_hours": 3.0,
            "preferred_days": ["Tuesday"],
            "back_status": "none",
            "equipment": {},
            "rpe_baseline": "beginner",
        }),
    ]:
        block = _FakeToolUseBlock(tool_name, tool_inputs)
        audit_log: list = []

        tool_result = await tools_module.dispatch_tool(block, audit_log, user_id=None)

        assert tool_result["is_error"] is True, (
            f"{tool_name} with user_id=None must fail closed, got {tool_result}"
        )
        assert "server identity required" in tool_result["content"][0]["text"]
        assert audit_log and "error" in audit_log[0]


async def test_dispatch_tool_save_profile_unaffected_by_persistence_branch(monkeypatch):
    """save_profile dispatch is unaffected by the generate_plan persistence branch."""
    import backend.agent.tools as tools_module

    mock_client = MagicMock()
    mock_client.table.return_value.upsert.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[{"id": "profile-uuid-dispatch"}])
    )
    monkeypatch.setattr(
        __import__("backend.sports_science.profile", fromlist=["_supabase_client"]),
        "_supabase_client",
        mock_client,
    )

    block = _FakeToolUseBlock(
        "save_profile",
        {
            "user_id": "u1",
            "fitness_goals": "weight loss",
            "weekly_hours": 3.0,
            "preferred_days": ["Tuesday", "Thursday"],
            "back_status": "none",
            "equipment": {},
            "rpe_baseline": "beginner",
        },
    )
    audit_log: list = []

    tool_result = await tools_module.dispatch_tool(
        block, audit_log, user_id="00000000-0000-0000-0000-000000000042"
    )

    assert tool_result["is_error"] is False
    payload = json.loads(tool_result["content"][0]["text"])
    assert payload["value"]["saved"] is True


async def test_save_profile_moderate_back_constraints(monkeypatch):
    """
    save_profile with back_status='moderate' passes the correct constraints JSONB
    to the Supabase upsert.
    """
    import backend.sports_science.profile as profile_module

    upsert_calls = []

    class _MockTable:
        def upsert(self, data, on_conflict=None):
            upsert_calls.append(data)
            return self

        async def execute(self):
            return MagicMock(data=[{"id": "profile-moderate-001"}])

    mock_client = MagicMock()
    mock_client.table.return_value = _MockTable()
    monkeypatch.setattr(profile_module, "_supabase_client", mock_client)

    from backend.sports_science.profile import save_profile

    result = await save_profile(
        user_id="u2",
        fitness_goals="rehab and fitness",
        weekly_hours=2.0,
        preferred_days=["Tuesday", "Saturday"],
        back_status="moderate",
        equipment={},
        rpe_baseline="beginner",
        lthr_estimate=155.0,
    )

    assert result.value["saved"] is True
    assert len(upsert_calls) == 1
    constraints = upsert_calls[0]["constraints"]
    assert constraints["back_issues"] is True
    assert constraints.get("load_ramp_flag_threshold_pct") == 10
