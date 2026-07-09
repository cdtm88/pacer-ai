# tests/sports_science/test_zones.py
import pytest

from backend.sports_science.types import ToolResult
from backend.sports_science.zones import (
    calculate_hr_zones,
    calculate_power_zones,
    estimate_lthr_from_max_hr,
    time_in_hr_zones,
)


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
    (200, 150, 3),   # 75% FTP boundary -> Z3 (150 >= 150, 150 < 180);
                     # Z2 upper is exclusive (150 < 150 = false)
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
        f"{power}W at FTP={ftp} matched zones {matched_zones}, "
        f"expected exactly zone {expected_zone}"
    )
    assert matched_zones[0] == expected_zone, (
        f"{power}W at FTP={ftp} matched zone {matched_zones[0]}, expected zone {expected_zone}"
    )


@pytest.mark.parametrize("lthr,bpm,expected_zone", [
    (200, 100, 1),   # well below Z1 upper (136) -> Z1
    (200, 136, 2),   # 0.68 LTHR boundary -> Z2 (136 >= 136, 136 < 166); exact lower boundary of Z2
    (200, 165, 2),   # just below Z2 upper (166) -> still Z2
    (200, 166, 3),   # 0.83 LTHR boundary -> Z3 (166 >= 166, 166 < 188); Z2 upper is exclusive
    (200, 188, 4),   # 0.94 LTHR boundary -> Z4 (188 >= 188, 188 < 210)
    (200, 210, 5),   # 1.05 LTHR boundary -> Z5 (open-ended top zone)
])
def test_hr_zone_boundary_no_overlap(lthr, bpm, expected_zone):
    """D-06: No bpm value resolves to two HR zones. Corrected 0.68/0.83/0.94/1.05
    fractions of LTHR (mirrors test_zone_boundary_no_overlap for power zones)."""
    result = calculate_hr_zones(lthr)
    zones = result.value

    matched_zones = []
    for z in zones:
        lower = z["lower_bpm"]
        upper = z["upper_bpm"]
        if upper is None:
            # Z5: open ended -- >= lower only
            if bpm >= lower:
                matched_zones.append(z["zone"])
        else:
            # Exclusive upper bound: >= lower AND < upper
            if bpm >= lower and bpm < upper:
                matched_zones.append(z["zone"])

    assert len(matched_zones) == 1, (
        f"{bpm}bpm at LTHR={lthr} matched zones {matched_zones}, "
        f"expected exactly zone {expected_zone}"
    )
    assert matched_zones[0] == expected_zone, (
        f"{bpm}bpm at LTHR={lthr} matched zone {matched_zones[0]}, expected zone {expected_zone}"
    )


def test_hr_zone2_ceiling_is_beginner_safe():
    """D-06 beginner-safety regression guard: Zone 2 (Endurance) upper_bpm must
    reflect 0.83*LTHR, not the old mislabeled 0.90*LTHR. This test would fail
    against the pre-fix (0.81/0.90) HR_ZONE_BOUNDARIES."""
    result = calculate_hr_zones(200.0)
    zones = result.value

    zone2 = next(z for z in zones if z["zone"] == 2)
    assert zone2["name"] == "Endurance"
    assert zone2["upper_bpm"] == round(0.83 * 200.0) == 166


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


def test_estimate_lthr_from_max_hr():
    """D-05/ONBD-05: estimate_lthr_from_max_hr(185) returns round(185*0.875)=162 bpm
    as a methodology-tagged ToolResult -- the LLM never derives this number itself."""
    result = estimate_lthr_from_max_hr(185)

    assert isinstance(result, ToolResult)
    result_dict = result.model_dump()
    assert set(["value", "unit", "methodology", "inputs"]).issubset(result_dict.keys())

    assert result.unit == "bpm"
    assert result.inputs["max_hr"] == 185

    lthr = result.value.get("lthr") if isinstance(result.value, dict) else None
    assert lthr == 162, f"expected round(185*0.875)=162, got {result.value}"

    assert "max hr" in result.methodology.lower() or "max_hr" in result.methodology.lower()


# RIDE-04 / D-11-02 / TRUST-01: time_in_hr_zones must reuse calculate_hr_zones
# for boundaries -- lthr=160 yields (via calculate_hr_zones):
#   Z1 [0,109)  Z2 [109,133)  Z3 [133,150)  Z4 [150,168)  Z5 [168, None)
# These boundaries are computed here from the same 0.68/0.83/0.94/1.05 ratios
# in HR_ZONE_BOUNDARIES, hand-verified against calculate_hr_zones(160).value
# in test_time_in_hr_zones_boundaries_match_calculate_hr_zones below.

_LTHR_160_HAND_CHECKED_HR_ARRAY = [
    # Z1 [0,109) -- 4 samples
    80, 90, 100, 105,
    # Z2 [109,133) -- 4 samples; 109 is the exact lower boundary
    109, 115, 125, 130,
    # Z3 [133,150) -- 4 samples; 133 is the exact lower boundary (Z2's exclusive upper)
    133, 138, 142, 148,
    # Z4 [150,168) -- 4 samples; 150 is the exact lower boundary (Z3's exclusive upper)
    150, 155, 160, 165,
    # Z5 [168, None) -- 4 samples; 168 is the exact lower boundary (Z4's exclusive upper)
    168, 175, 185, 195,
]


def test_time_in_hr_zones_boundaries_match_calculate_hr_zones():
    """Sanity check: the hand-checked boundaries used in this test module for
    lthr=160 match what calculate_hr_zones(160) actually returns (D-11-02)."""
    zones = calculate_hr_zones(160.0).value
    expected = [
        (1, 0, 109),
        (2, 109, 133),
        (3, 133, 150),
        (4, 150, 168),
        (5, 168, None),
    ]
    actual = [(z["zone"], z["lower_bpm"], z["upper_bpm"]) for z in zones]
    assert actual == expected, f"boundary assumption stale: {actual}"


def test_time_in_hr_zones_hand_checked():
    """RIDE-04: time_in_hr_zones(hr_array, 160) returns exact per-zone seconds
    and pct for a hand-checked hr_array with 4 samples in each of the 5 zones
    (20 total), including one sample on each zone's exact lower boundary."""
    result = time_in_hr_zones(_LTHR_160_HAND_CHECKED_HR_ARRAY, 160.0)
    rows = result.value

    assert len(rows) == 5

    by_zone = {row["zone"]: row for row in rows}
    for zone in range(1, 6):
        assert by_zone[zone]["seconds"] == 4, f"zone {zone} seconds: {by_zone[zone]}"
        assert by_zone[zone]["pct"] == 20.0, f"zone {zone} pct: {by_zone[zone]}"

    total_seconds = sum(row["seconds"] for row in rows)
    total_pct = sum(row["pct"] for row in rows)
    assert total_seconds == len(_LTHR_160_HAND_CHECKED_HR_ARRAY) == 20
    assert abs(total_pct - 100.0) <= 0.2


def test_time_in_hr_zones_boundary_exclusive_upper():
    """Membership is exclusive-upper: a sample exactly equal to a zone's
    upper_bpm belongs to the NEXT zone up, never both (mirrors
    calculate_hr_zones). 109/133/150/168 are each simultaneously the
    exclusive upper bound of one zone and the inclusive lower bound of the
    next; every one of them must land in the higher zone."""
    hr_array = [109, 133, 150, 168]
    result = time_in_hr_zones(hr_array, 160.0)
    rows = result.value
    by_zone = {row["zone"]: row for row in rows}

    assert by_zone[1]["seconds"] == 0
    assert by_zone[2]["seconds"] == 1  # 109 -> Z2, not Z1
    assert by_zone[3]["seconds"] == 1  # 133 -> Z3, not Z2
    assert by_zone[4]["seconds"] == 1  # 150 -> Z4, not Z3
    assert by_zone[5]["seconds"] == 1  # 168 -> Z5, not Z4

    total_seconds = sum(row["seconds"] for row in rows)
    assert total_seconds == len(hr_array) == 4


def test_time_in_hr_zones_toolresult_contract():
    """time_in_hr_zones returns the standard ToolResult(value, unit,
    methodology, inputs) contract consumed by 11-03's route."""
    hr_array = [100, 120, 140, 160, 180]
    result = time_in_hr_zones(hr_array, 160.0)

    assert isinstance(result, ToolResult)
    assert len(result.value) == 5
    assert result.unit == "seconds"
    assert "time-in-zone" in result.methodology
    assert result.inputs["lthr"] == 160.0
    assert result.inputs["total_seconds"] == len(hr_array) == 5


def test_time_in_hr_zones_empty_array():
    """Empty hr_array: every zone seconds == 0 and pct == 0.0, no
    ZeroDivisionError."""
    result = time_in_hr_zones([], 160.0)
    rows = result.value

    assert len(rows) == 5
    for row in rows:
        assert row["seconds"] == 0
        assert row["pct"] == 0.0

    assert result.inputs["total_seconds"] == 0
