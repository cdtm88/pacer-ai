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


def time_in_hr_zones(hr_array: list[float], lthr: float) -> ToolResult:
    """RIDE-04: time-in-zone seconds/pct for a ride's HR samples.

    D-11-02 / TRUST-01: boundaries are sourced exclusively from
    calculate_hr_zones(lthr) -- never re-derived here -- so there is exactly
    one definition of an HR zone in the codebase. Zone membership mirrors
    calculate_hr_zones: >= lower AND < upper (except the top zone, which is
    >= lower only, open-ended).
    """
    zones = calculate_hr_zones(lthr).value
    total = len(hr_array)
    counts = [0] * len(zones)

    for hr in hr_array:
        for i, z in enumerate(zones):
            lower_bpm = z["lower_bpm"]
            upper_bpm = z["upper_bpm"]
            if upper_bpm is None:
                if hr >= lower_bpm:
                    counts[i] += 1
                    break
            elif lower_bpm <= hr < upper_bpm:
                counts[i] += 1
                break

    rows = [
        {
            "zone": z["zone"],
            "name": z["name"],
            "seconds": counts[i],
            "pct": round(100 * counts[i] / total, 1) if total else 0.0,
        }
        for i, z in enumerate(zones)
    ]

    return ToolResult(
        value=rows,
        unit="seconds",
        methodology="Coggan/Allen time-in-zone from LTHR-derived HR-zone boundaries",
        inputs={"lthr": lthr, "total_seconds": total},
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
