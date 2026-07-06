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


def _rough_ftp_estimate(efforts: list[dict]) -> float | None:
    """Fit the CP model to a loose (duration-only) effort set and return the
    fitted CP as a rough estimate, or None if the fit doesn't converge.

    First-pass helper for the two-pass quality-effort filter (D-03): the
    rough estimate anchors the second-pass 85% ratio threshold to the
    rider's own power level instead of the flat, beginner-excluding
    QUALITY_EFFORT_FALLBACK_WATTS floor.
    """
    durations = np.array([e["duration_secs"] for e in efforts], dtype=float)
    mean_powers = np.array([e["mean_power_watts"] for e in efforts], dtype=float)
    try:
        popt, _ = curve_fit(
            _cp_model,
            durations,
            mean_powers,
            p0=[200.0, 20000.0],
            bounds=([50.0, 1000.0], [500.0, 100000.0]),
            maxfev=5000,
        )
    except (RuntimeError, ValueError):
        return None
    return float(popt[0])


def estimate_ftp_from_rides(rides: list[dict]) -> ToolResult:
    """
    TOOL-03: Estimate FTP via 2-parameter Critical Power model (Morton 1996).

    D-04: Returns value=None with confidence='insufficient_data' when fewer than
    MIN_QUALITY_EFFORTS (4) quality efforts are available -- never fabricates a number
    from sparse data.

    Confidence levels (D-03):
      insufficient_data: < 4 quality efforts
      low:  4-6 efforts
      medium: 7-11 efforts
      high: 12+ efforts

    Two-pass quality-effort filter (D-03, gap closure 01-06): a loose
    duration-only first pass produces a rough CP estimate, which then
    anchors the 85% ratio threshold for a second-pass re-filter. This
    makes the ratio branch of _is_quality_effort reachable -- without it,
    every rider was filtered against a flat 150W floor that a
    deconditioned-beginner effort set could never clear.
    """
    # First pass: loose, duration-only filter (each ride IS an effort dict).
    loose_efforts = [
        e for e in rides if e.get("duration_secs", 0) >= QUALITY_EFFORT_MIN_DURATION_SECS
    ]

    if len(loose_efforts) < MIN_QUALITY_EFFORTS:
        return ToolResult(
            value=None,
            unit="watts",
            methodology="2-parameter Critical Power model (Morton 1996)",
            inputs={
                "quality_efforts": len(loose_efforts),
                "required": MIN_QUALITY_EFFORTS,
                "confidence": "insufficient_data",
            },
        )

    # Second pass: rough CP estimate anchors the 85% ratio re-filter.
    # If the rough fit fails to converge, degrade gracefully by keeping the
    # duration-qualified efforts rather than returning null.
    rough = _rough_ftp_estimate(loose_efforts)
    if rough is not None:
        quality_efforts = [
            e for e in loose_efforts if _is_quality_effort(e, best_ftp_estimate=rough)
        ]
    else:
        quality_efforts = loose_efforts

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

    try:
        popt, _ = curve_fit(
            _cp_model,
            durations,
            mean_powers,
            p0=[200.0, 20000.0],                         # initial guess: CP=200W, W'=20kJ
            bounds=([50.0, 1000.0], [500.0, 100000.0]),  # physiological bounds (Assumption A4)
            maxfev=5000,
        )
    except (RuntimeError, ValueError):
        return ToolResult(
            value=None,
            unit="watts",
            methodology="2-parameter Critical Power model (Morton 1996) -- convergence failed",
            inputs={
                "quality_efforts": len(quality_efforts),
                "required": MIN_QUALITY_EFFORTS,
                "confidence": "insufficient_data",
            },
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
