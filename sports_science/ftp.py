# sports_science/ftp.py
import numpy as np
from scipy.optimize import curve_fit
from .constants import (
    QUALITY_EFFORT_MIN_DURATION_SECS,
    QUALITY_EFFORT_MIN_POWER_RATIO,
    QUALITY_EFFORT_FALLBACK_WATTS,
    MIN_QUALITY_EFFORTS,
)
from .types import ToolResult


def _is_quality_effort(effort: dict, best_ftp_estimate: float | None) -> bool:
    """True if the effort meets the duration and power threshold for CP model inclusion (D-03)."""
    duration = effort.get("duration_secs", 0)
    mean_power = effort.get("mean_power_watts", 0)
    threshold = (
        best_ftp_estimate * QUALITY_EFFORT_MIN_POWER_RATIO
        if best_ftp_estimate
        else QUALITY_EFFORT_FALLBACK_WATTS
    )
    return duration >= QUALITY_EFFORT_MIN_DURATION_SECS and mean_power >= threshold


def _cp_model(t: np.ndarray, cp: float, wprime: float) -> np.ndarray:
    """2-parameter Critical Power model: P(t) = CP + W'/t (Morton 1996)."""
    return cp + wprime / t


def estimate_ftp_from_rides(rides: list[dict]) -> ToolResult:
    """
    TOOL-03: Estimate FTP via 2-parameter Critical Power model (Morton 1996).

    D-04: Returns value=None with confidence='insufficient_data' when fewer than
    MIN_QUALITY_EFFORTS (4) quality efforts are available -- never fabricates a number
    from sparse data.

    Confidence levels (D-03):
      insufficient_data: < 4 quality efforts
      low:  4-6 efforts
      medium: 7-12 efforts
      high: 12+ efforts
    """
    # Extract all efforts from rides list (each ride IS an effort dict)
    # rides can be a list of effort dicts with duration_secs and mean_power_watts
    quality_efforts = [e for e in rides if _is_quality_effort(e, best_ftp_estimate=None)]

    if len(quality_efforts) < MIN_QUALITY_EFFORTS:
        return ToolResult(
            value=None,
            unit="watts",
            methodology="2-parameter Critical Power model (Morton 1996)",
            inputs={
                "quality_efforts": len(quality_efforts),
                "required": MIN_QUALITY_EFFORTS,
                "confidence": "insufficient_data",
            },
        )

    # Fit CP model
    durations = np.array([e["duration_secs"] for e in quality_efforts], dtype=float)
    mean_powers = np.array([e["mean_power_watts"] for e in quality_efforts], dtype=float)

    popt, _ = curve_fit(
        _cp_model,
        durations,
        mean_powers,
        p0=[200.0, 20000.0],                         # initial guess: CP=200W, W'=20kJ
        bounds=([50.0, 1000.0], [500.0, 100000.0]),  # physiological bounds (Assumption A4)
        maxfev=5000,
    )
    cp, wprime = popt

    # FTP is approximately equal to CP for the CP2 model
    ftp = float(cp)

    # Confidence by effort count (D-03): low=4-6, medium=7-11, high=12+
    n = len(quality_efforts)
    if n <= 6:
        confidence = "low"
    elif n < 12:
        confidence = "medium"
    else:
        confidence = "high"

    return ToolResult(
        value={
            "ftp": round(ftp, 1),
            "cp": round(float(cp), 1),
            "wprime": round(float(wprime), 0),
            "confidence": confidence,
        },
        unit="watts",
        methodology="2-parameter Critical Power model (Morton 1996)",
        inputs={
            "quality_efforts": n,
            "required": MIN_QUALITY_EFFORTS,
            "confidence": confidence,
        },
    )
