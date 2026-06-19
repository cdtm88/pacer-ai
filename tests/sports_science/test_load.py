# tests/sports_science/test_load.py
import pytest

pytestmark = pytest.mark.skip(reason="implemented in plan 04")


def test_back_constraints_cap():
    """TOOL-06: Back constraints apply weekly hour cap."""
    load = pytest.importorskip("sports_science.load")
    result = load.progress_load(
        20.0,
        40.0,
        {"back_issues": True, "max_initial_weekly_hours": 3.5, "load_ramp_flag_threshold_pct": 10},
    )
    assert result is not None
