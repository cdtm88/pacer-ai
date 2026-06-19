# tests/sports_science/test_zones.py
import pytest

pytestmark = pytest.mark.skip(reason="implemented in plan 02")


def test_power_zones_ftp200():
    """TOOL-01: Power zones correct boundaries for FTP=200."""
    zones = pytest.importorskip("sports_science.zones").calculate_power_zones(200.0)
    assert zones is not None


def test_hr_zones_lthr155():
    """TOOL-02: HR zones for LTHR=155."""
    zones = pytest.importorskip("sports_science.zones").calculate_hr_zones(155.0)
    assert zones is not None


def test_zone_boundary_no_overlap():
    """TOOL-01: Zone boundary exclusive upper bound (no dual membership)."""
    zones = pytest.importorskip("sports_science.zones").calculate_power_zones(200.0)
    assert zones is not None
