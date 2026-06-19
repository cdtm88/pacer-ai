# tests/sports_science/test_load.py
import pytest
from sports_science.load import progress_load, CTL_RAMP_CEILING_PER_WEEK
from sports_science.types import ToolResult


# --------------------------------------------------------------------------- #
# TOOL-06: Safe weekly load ramp with back-protective caps (D-09)
# --------------------------------------------------------------------------- #


def test_back_constraints_cap():
    """D-09: back_issues=True applies back-protective cap below standard 8pts/week ceiling."""
    result = progress_load(
        current_ctl=40.0,
        target_ctl=80.0,
        constraints={
            "back_issues": True,
            "max_initial_weekly_hours": 3.5,
            "load_ramp_flag_threshold_pct": 10,
        },
    )
    # 10% of current_ctl=40 -> max_increase=4.0 (less than standard 8.0)
    assert result.value["back_constraints_applied"] is True
    assert result.value["max_weekly_increase"] < CTL_RAMP_CEILING_PER_WEEK
    # recommended_ctl should be current + capped increase, not current + 8
    assert result.value["recommended_ctl_target"] == pytest.approx(44.0, abs=0.1)


def test_back_constraints_cap_specific_values():
    """D-09: With current_ctl=40, 10% ramp threshold -> max_increase=4.0."""
    result = progress_load(
        current_ctl=40.0,
        target_ctl=80.0,
        constraints={"back_issues": True, "load_ramp_flag_threshold_pct": 10},
    )
    assert result.value["max_weekly_increase"] == pytest.approx(4.0, abs=0.1)


def test_no_back_issues_default():
    """Standard ramp: back_issues=False uses 8pts/week ceiling."""
    result = progress_load(
        current_ctl=40.0,
        target_ctl=80.0,
        constraints={"back_issues": False},
    )
    assert result.value["back_constraints_applied"] is False
    assert result.value["max_weekly_increase"] == pytest.approx(CTL_RAMP_CEILING_PER_WEEK)
    assert result.value["recommended_ctl_target"] == pytest.approx(48.0, abs=0.1)


def test_target_ctl_caps_recommended():
    """Recommended CTL cannot exceed target_ctl even with full ramp."""
    result = progress_load(
        current_ctl=40.0,
        target_ctl=42.0,  # only 2 pts above current
        constraints={"back_issues": False},
    )
    assert result.value["recommended_ctl_target"] == pytest.approx(42.0, abs=0.1)


def test_returns_tool_result():
    """TOOL-09: progress_load must return ToolResult."""
    result = progress_load(40.0, 80.0, {"back_issues": False})
    assert isinstance(result, ToolResult)


def test_ctl_ramp_ceiling_module_constant():
    """CTL_RAMP_CEILING_PER_WEEK must be module-level constant = 8.0."""
    assert CTL_RAMP_CEILING_PER_WEEK == 8.0
