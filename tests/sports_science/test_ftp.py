# tests/sports_science/test_ftp.py
import pytest

pytestmark = pytest.mark.skip(reason="implemented in plan 03")


def test_insufficient_efforts_returns_none():
    """TOOL-03: CP model refuses < 4 quality efforts."""
    ftp = pytest.importorskip("sports_science.ftp")
    result = ftp.estimate_ftp_from_rides([{"duration_secs": 300, "mean_power_watts": 200}])
    assert result.value is None


def test_short_effort_not_quality():
    """TOOL-03: Quality effort filter: 2 min effort rejected."""
    ftp = pytest.importorskip("sports_science.ftp")
    short_efforts = [{"duration_secs": 120, "mean_power_watts": 250}] * 6
    result = ftp.estimate_ftp_from_rides(short_efforts)
    assert result.value is None
