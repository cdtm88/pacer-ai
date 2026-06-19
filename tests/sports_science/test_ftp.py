# tests/sports_science/test_ftp.py
import pytest
from sports_science.ftp import estimate_ftp_from_rides
from sports_science.types import ToolResult


# --------------------------------------------------------------------------- #
# TOOL-03: FTP estimation via 2-parameter CP model
# TOOL-10: Sparse-data and short-effort edge cases
# --------------------------------------------------------------------------- #


def test_insufficient_efforts_returns_none():
    """D-04: fewer than 4 quality efforts -> value=None, confidence=insufficient_data; never a fabricated number."""
    rides = [
        {"duration_secs": 300, "mean_power_watts": 200},
        {"duration_secs": 600, "mean_power_watts": 220},
        {"duration_secs": 900, "mean_power_watts": 210},
    ]
    result = estimate_ftp_from_rides(rides)
    assert result.value is None
    assert result.inputs["confidence"] == "insufficient_data"


def test_short_effort_not_quality():
    """D-03: A 120-second effort is below 3-minute minimum -- rejected even with high power."""
    short_efforts = [{"duration_secs": 120, "mean_power_watts": 300}] * 6
    result = estimate_ftp_from_rides(short_efforts)
    # All 6 efforts are < 180s -> 0 quality efforts -> insufficient data
    assert result.value is None
    assert result.inputs["confidence"] == "insufficient_data"


def test_sufficient_efforts_returns_estimate(sample_quality_efforts):
    """D-03: 4 quality efforts -> numeric FTP within physiological bounds [50, 500]."""
    result = estimate_ftp_from_rides(sample_quality_efforts)
    assert result.value is not None
    ftp = result.value["ftp"]
    assert 50 <= ftp <= 500


def test_confidence_low_at_4_efforts(sample_quality_efforts):
    """D-03: 4-6 quality efforts -> confidence='low'."""
    result = estimate_ftp_from_rides(sample_quality_efforts)
    assert result.value["confidence"] == "low"


def test_confidence_levels():
    """D-03: 7 efforts -> medium; 12+ efforts -> high."""
    medium_efforts = [
        {"duration_secs": 180 + i * 60, "mean_power_watts": 200 + i * 5}
        for i in range(7)
    ]
    result_medium = estimate_ftp_from_rides(medium_efforts)
    assert result_medium.value["confidence"] == "medium"

    high_efforts = [
        {"duration_secs": 180 + i * 60, "mean_power_watts": 200 + i * 5}
        for i in range(12)
    ]
    result_high = estimate_ftp_from_rides(high_efforts)
    assert result_high.value["confidence"] == "high"


def test_returns_tool_result(sample_quality_efforts):
    """TOOL-09: estimate_ftp_from_rides must return ToolResult."""
    result = estimate_ftp_from_rides(sample_quality_efforts)
    assert isinstance(result, ToolResult)


def test_insufficient_data_returns_tool_result():
    """TOOL-09: Even the sparse-data path returns ToolResult (not None directly)."""
    result = estimate_ftp_from_rides([])
    assert isinstance(result, ToolResult)
    assert result.value is None


def test_cp_and_wprime_present_on_success(sample_quality_efforts):
    """Successful fit includes cp and wprime in value dict."""
    result = estimate_ftp_from_rides(sample_quality_efforts)
    assert "cp" in result.value
    assert "wprime" in result.value


def test_methodology_string(sample_quality_efforts):
    """methodology must reference the CP model."""
    result = estimate_ftp_from_rides(sample_quality_efforts)
    assert "Critical Power" in result.methodology
