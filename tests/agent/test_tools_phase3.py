# tests/agent/test_tools_phase3.py
"""
Phase 3 tool registry and sports_science unit tests.

TRUST-02: TOOL_REGISTRY and TOOL_SCHEMAS must have the same name set and
exactly 10 entries after adding save_profile and generate_plan.

generate_plan unit tests: call the sync function directly (no mocking).
save_profile unit test: mock _get_async_supabase (async Supabase write).

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
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
