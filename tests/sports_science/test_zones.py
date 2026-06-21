# tests/sports_science/test_zones.py
import pytest
from api.sports_science.zones import calculate_power_zones, calculate_hr_zones
from api.sports_science.types import ToolResult


def test_power_zones_ftp200():
    """TOOL-01: calculate_power_zones(200) returns 7 Coggan/Allen zones with correct boundaries."""
    result = calculate_power_zones(200.0)
    zones = result.value

    # Must return 7 zones
    assert len(zones) == 7

    # Each entry has required keys
    for z in zones:
        assert "zone" in z
        assert "name" in z
        assert "lower_watts" in z
        assert "upper_watts" in z

    # Z1 lower_watts = 0
    z1 = zones[0]
    assert z1["zone"] == 1
    assert z1["lower_watts"] == 0

    # Z7 upper_watts is None (open-ended top zone)
    z7 = zones[6]
    assert z7["zone"] == 7
    assert z7["upper_watts"] is None

    # Z4 (Threshold): lower=0.90*200=180, upper=1.05*200=210
    z4 = zones[3]
    assert z4["zone"] == 4
    assert z4["name"] == "Threshold"
    assert z4["lower_watts"] == 180
    assert z4["upper_watts"] == 210


@pytest.mark.parametrize("ftp,power,expected_zone", [
    (200, 100, 1),   # 50% FTP -> Z1 (100 >= 0, 100 < 110)
    (200, 110, 2),   # 55% FTP boundary -> Z2 (110 >= 110, 110 < 150); exact lower boundary of Z2
    (200, 150, 3),   # 75% FTP boundary -> Z3 (150 >= 150, 150 < 180); Z2 upper is exclusive (150 < 150 = false)
    (200, 151, 3),   # just above 75% FTP -> Z3
])
def test_zone_boundary_no_overlap(ftp, power, expected_zone):
    """TOOL-01: No watt value resolves to two zones. Exclusive upper bound."""
    result = calculate_power_zones(ftp)
    zones = result.value

    matched_zones = []
    for z in zones:
        lower = z["lower_watts"]
        upper = z["upper_watts"]
        if upper is None:
            # Z7: open ended -- >= lower only
            if power >= lower:
                matched_zones.append(z["zone"])
        else:
            # Exclusive upper bound: >= lower AND < upper
            if power >= lower and power < upper:
                matched_zones.append(z["zone"])

    # Every power value must belong to exactly one zone
    assert len(matched_zones) == 1, (
        f"{power}W at FTP={ftp} matched zones {matched_zones}, expected exactly zone {expected_zone}"
    )
    assert matched_zones[0] == expected_zone, (
        f"{power}W at FTP={ftp} matched zone {matched_zones[0]}, expected zone {expected_zone}"
    )


def test_hr_zones_lthr155():
    """TOOL-02: calculate_hr_zones(155) returns HR zones with boundaries and methodology."""
    result = calculate_hr_zones(155.0)
    zones = result.value

    # Must have zones (5-zone LTHR model)
    assert len(zones) > 0

    # Each zone has required fields
    for z in zones:
        assert "zone" in z
        assert "name" in z
        assert "lower_bpm" in z
        assert "upper_bpm" in z

    # Top zone upper_bpm must be None (open-ended)
    top_zone = zones[-1]
    assert top_zone["upper_bpm"] is None

    # Methodology must mention HR model
    assert "HR" in result.methodology or "LTHR" in result.methodology


def test_returns_tool_result():
    """TOOL-09: Both zone functions return a ToolResult with required keys."""
    power_result = calculate_power_zones(200.0)
    hr_result = calculate_hr_zones(155.0)

    # Must be ToolResult instances
    assert isinstance(power_result, ToolResult)
    assert isinstance(hr_result, ToolResult)

    # model_dump() must have the required keys
    power_dict = power_result.model_dump()
    assert set(["value", "unit", "methodology", "inputs"]).issubset(power_dict.keys())

    hr_dict = hr_result.model_dump()
    assert set(["value", "unit", "methodology", "inputs"]).issubset(hr_dict.keys())

    # Units
    assert power_result.unit == "watts"
    assert hr_result.unit == "bpm"

    # Inputs must capture the input parameter
    assert "ftp" in power_result.inputs
    assert power_result.inputs["ftp"] == 200.0
    assert "lthr" in hr_result.inputs
    assert hr_result.inputs["lthr"] == 155.0
