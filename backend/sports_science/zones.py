# sports_science/zones.py
from .constants import HR_ZONE_BOUNDARIES, LTHR_FROM_MAX_HR_RATIO, POWER_ZONE_BOUNDARIES
from .types import ToolResult


def calculate_power_zones(ftp: float) -> ToolResult:
    """TOOL-01: Coggan/Allen 7-zone power zones from FTP.

    Zone membership rule (Pitfall 4): >= lower AND < upper for Z1-Z6;
    >= lower only for Z7. Upper bound is exclusive to prevent dual membership.
    """
    zones = []
    for z in POWER_ZONE_BOUNDARIES:
        lower_watts = round(z["lower"] * ftp)
        upper_watts = round(z["upper"] * ftp) if z["upper"] is not None else None
        zones.append({
            "zone": z["zone"],
            "name": z["name"],
            "lower_watts": lower_watts,
            "upper_watts": upper_watts,
        })

    return ToolResult(
        value=zones,
        unit="watts",
        methodology="Coggan/Allen 7-zone power model",
        inputs={"ftp": ftp},
    )


def calculate_hr_zones(max_hr_or_lthr: float) -> ToolResult:
    """TOOL-02: Coggan/Allen 5-zone HR model from LTHR.

    Zone membership rule: >= lower AND < upper for Z1-Z4;
    >= lower only for Z5. Upper bound is exclusive to prevent dual membership.
    """
    zones = []
    for z in HR_ZONE_BOUNDARIES:
        lower_bpm = round(z["lower"] * max_hr_or_lthr)
        upper_bpm = round(z["upper"] * max_hr_or_lthr) if z["upper"] is not None else None
        zones.append({
            "zone": z["zone"],
            "name": z["name"],
            "lower_bpm": lower_bpm,
            "upper_bpm": upper_bpm,
        })

    return ToolResult(
        value=zones,
        unit="bpm",
        methodology="Coggan/Allen HR zones from LTHR",
        inputs={"lthr": max_hr_or_lthr},
    )


def estimate_lthr_from_max_hr(max_hr: float) -> ToolResult:
    """D-05/ONBD-05: rough LTHR estimate from a user-reported max HR.

    Pure function (no DB, no Anthropic import -- TRUST-01 boundary preserved).
    Low-confidence estimate: a measured lactate-threshold test is more
    accurate. The ratio lives in constants.py so it is auditable and
    methodology-tagged, never invented by the LLM.
    """
    lthr = round(max_hr * LTHR_FROM_MAX_HR_RATIO)

    return ToolResult(
        value={"lthr": lthr},
        unit="bpm",
        methodology=(
            f"LTHR estimated as {LTHR_FROM_MAX_HR_RATIO} of max HR "
            "(rough estimate; a measured lactate-threshold test is more accurate)"
        ),
        inputs={"max_hr": max_hr},
    )
