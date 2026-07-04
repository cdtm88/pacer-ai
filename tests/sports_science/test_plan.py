# tests/sports_science/test_plan.py
"""
PLAN-07: dedicated test home for generate_plan / _build_sessions / _is_true_beginner_ramp.

Covers D-07's CTL-gap-aware progression and preferred_days scheduling.
The inline generate_plan tests in tests/agent/test_tools_phase3.py remain
in place (harmless duplication of the pre-D-07 shape assertions); this file
is the dedicated home for the new PLAN-07 behaviors and future generate_plan
coverage per the tests/sports_science/ one-file-per-module convention.
"""
import pytest

from backend.sports_science.plan import generate_plan, _is_true_beginner_ramp
from backend.sports_science.types import ToolResult


# --------------------------------------------------------------------------- #
# _is_true_beginner_ramp unit cases
# --------------------------------------------------------------------------- #


def test_is_true_beginner_ramp_target_non_positive_is_false():
    """target <= 0 always returns False (no target to gap against)."""
    assert _is_true_beginner_ramp(10.0, {"recommended_ctl_target": 0}) is False
    assert _is_true_beginner_ramp(10.0, {"recommended_ctl_target": -5.0}) is False


def test_is_true_beginner_ramp_gap_ratio_half_is_true():
    """gap_ratio == 0.5 (current_ctl half of target) qualifies (boundary inclusive)."""
    assert _is_true_beginner_ramp(10.0, {"recommended_ctl_target": 20.0}) is True


def test_is_true_beginner_ramp_gap_ratio_small_is_false():
    """gap_ratio 0.1 (near-target) does not qualify as a true-beginner ramp."""
    assert _is_true_beginner_ramp(18.0, {"recommended_ctl_target": 20.0}) is False


def test_is_true_beginner_ramp_cold_start_always_true():
    """current_ctl <= 0 (cold start, brand-new user) always qualifies."""
    assert _is_true_beginner_ramp(0.0, {"recommended_ctl_target": 20.0}) is True
    assert _is_true_beginner_ramp(-1.0, {"recommended_ctl_target": 20.0}) is True


# --------------------------------------------------------------------------- #
# preferred_days scheduling
# --------------------------------------------------------------------------- #


def test_preferred_days_used_when_supplied():
    """Sessions are scheduled on the supplied preferred_days, not _DEFAULT_DAYS."""
    result = generate_plan(
        user_id="u1",
        weekly_hours=4.0,
        back_status="none",
        current_ctl=18.0,
        load_targets={"recommended_ctl_target": 20.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="insufficient_data",
        ftp_watts=None,
        preferred_days=["Monday", "Wednesday", "Friday", "Sunday"],
    )
    days_used = {s["day"] for s in result.value["sessions"]}
    assert days_used == {"Monday", "Wednesday", "Friday", "Sunday"}


def test_preferred_days_none_falls_back_to_default():
    """preferred_days=None falls back to _DEFAULT_DAYS."""
    from backend.sports_science.plan import _DEFAULT_DAYS

    result = generate_plan(
        user_id="u1",
        weekly_hours=4.0,
        back_status="none",
        current_ctl=18.0,
        load_targets={"recommended_ctl_target": 20.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="insufficient_data",
        ftp_watts=None,
        preferred_days=None,
    )
    days_used = {s["day"] for s in result.value["sessions"]}
    n_sessions = 4  # weekly_hours=4.0 -> 4 sessions/week
    assert days_used == set(_DEFAULT_DAYS[:n_sessions])


def test_preferred_days_empty_list_falls_back_to_default():
    """preferred_days=[] (empty, not None) also falls back to _DEFAULT_DAYS."""
    from backend.sports_science.plan import _DEFAULT_DAYS

    result = generate_plan(
        user_id="u1",
        weekly_hours=4.0,
        back_status="none",
        current_ctl=18.0,
        load_targets={"recommended_ctl_target": 20.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="insufficient_data",
        ftp_watts=None,
        preferred_days=[],
    )
    days_used = {s["day"] for s in result.value["sessions"]}
    n_sessions = 4
    assert days_used == set(_DEFAULT_DAYS[:n_sessions])


# --------------------------------------------------------------------------- #
# D-07 CTL-gap-aware progression
# --------------------------------------------------------------------------- #


def test_true_beginner_cold_start_flat_ramp_weeks_1_to_3_equal():
    """current_ctl=0 (cold start) -> weeks 1-3 have equal duration per day-slot."""
    result = generate_plan(
        user_id="u1",
        weekly_hours=4.0,
        back_status="none",
        current_ctl=0.0,
        load_targets={"recommended_ctl_target": 20.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="insufficient_data",
        ftp_watts=None,
        preferred_days=["Monday", "Wednesday", "Friday"],
    )
    sessions = result.value["sessions"]
    by_week = {
        week: next(s["duration_minutes"] for s in sessions if s["week"] == week and s["day"] == "Monday")
        for week in (1, 2, 3)
    }
    assert by_week[1] == by_week[2] == by_week[3], (
        f"Expected flat duration across weeks 1-3 for a true-beginner ramp, got {by_week}"
    )
    assert "ctl_gap_flat_ramp" in result.value["constraints_applied"]


def test_at_risk_beginner_week1_capped_below_30():
    """current_ctl=0 + back_status='moderate' -> week 1 duration capped tighter than 30."""
    result = generate_plan(
        user_id="u1",
        weekly_hours=4.0,
        back_status="moderate",
        current_ctl=0.0,
        load_targets={"recommended_ctl_target": 20.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="insufficient_data",
        ftp_watts=None,
        preferred_days=["Monday", "Wednesday", "Friday"],
    )
    sessions = result.value["sessions"]
    week1_durations = [s["duration_minutes"] for s in sessions if s["week"] == 1]
    for d in week1_durations:
        assert d < 30, f"Expected at-risk-beginner week 1 duration < 30, got {d}"

    # Weeks 1-3 remain flat under the same at-risk cap.
    by_week = {
        week: next(s["duration_minutes"] for s in sessions if s["week"] == week and s["day"] == "Monday")
        for week in (1, 2, 3)
    }
    assert by_week[1] == by_week[2] == by_week[3]
    assert "ctl_gap_flat_ramp" in result.value["constraints_applied"]
    assert "back_protective" in result.value["constraints_applied"]


def test_near_target_non_beginner_preserves_week2_3_full_template():
    """gap_ratio=0.1 (near-target) preserves today's week2/3-full-ramp behavior."""
    result = generate_plan(
        user_id="u1",
        weekly_hours=4.0,
        back_status="none",
        current_ctl=18.0,
        load_targets={"recommended_ctl_target": 20.0},
        hr_zones=[{"zone": 2, "lower_bpm": 120, "upper_bpm": 145}],
        ftp_confidence="insufficient_data",
        ftp_watts=None,
        preferred_days=["Monday", "Wednesday", "Friday"],
    )
    sessions = result.value["sessions"]
    by_week = {
        week: next(s["duration_minutes"] for s in sessions if s["week"] == week and s["day"] == "Monday")
        for week in (1, 2, 3)
    }
    # Week 1 stays conservative (<=45); weeks 2/3 are NOT forced equal to week 1
    # -- proving the flat-ramp change is conditional, not blanket.
    assert by_week[1] <= 45
    assert by_week[2] > by_week[1] or by_week[3] > by_week[1], (
        "Near-target non-beginner should ramp weeks 2/3 above week 1's conservative cap, "
        f"got flat durations {by_week}"
    )
    assert "ctl_gap_flat_ramp" not in result.value["constraints_applied"]


def test_generate_plan_returns_tool_result():
    """generate_plan must return a ToolResult (TOOL-09 contract)."""
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
    assert isinstance(result, ToolResult)
