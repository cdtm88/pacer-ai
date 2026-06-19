# sports_science/metrics.py
import numpy as np
from .constants import (
    NP_SPIKE_MULTIPLIER,
    NP_SPIKE_FALLBACK_WATTS,
    NP_MIN_DURATION_SECS,
)
from .types import ToolResult


def _compute_np(power_array: list[float], ftp: float | None) -> float | None:
    """
    Normalized Power per TrainingPeaks definition.

    CRITICAL: Zeros MUST be included (coasting counts). Spike filter runs BEFORE rolling mean.

    Args:
        power_array: 1 Hz power samples (seconds of data). Zeros are valid.
        ftp: Rider's FTP in watts. If None/0, spike cap falls back to NP_SPIKE_FALLBACK_WATTS.

    Returns:
        NP in watts as float, or None if the array is shorter than the 30-sample window.
    """
    arr = np.array(power_array, dtype=float)

    # Spike filter: clip at FTP*3 (or fallback cap when no FTP available).
    # MUST run before rolling mean -- Pitfall 1.
    cap = ftp * NP_SPIKE_MULTIPLIER if ftp else NP_SPIKE_FALLBACK_WATTS
    arr = np.clip(arr, 0.0, cap)

    # 30-second rolling mean (assumes 1 Hz data).
    window = 30
    if len(arr) < window:
        return None

    rolling_mean = np.convolve(arr, np.ones(window) / window, mode="valid")

    # 4th power -> mean -> 4th root.
    return float(np.mean(rolling_mean**4) ** 0.25)


def compute_tss(
    power_array: list[float],
    duration_secs: int,
    ftp: float,
) -> ToolResult:
    """
    TOOL-04: Training Stress Score from a power-meter ride.

    Returns ToolResult with value=None for rides shorter than NP_MIN_DURATION_SECS (10 min).
    For valid rides returns value={tss, np_watts, if, warnings}.

    TSS formula: (duration_secs * NP * IF) / (FTP * 3600) * 100
    """
    if duration_secs < NP_MIN_DURATION_SECS:
        return ToolResult(
            value=None,
            unit="TSS",
            methodology=(
                f"TrainingPeaks TSS; ride too short (<{NP_MIN_DURATION_SECS // 60} min)"
            ),
            inputs={"duration_secs": duration_secs, "ftp": ftp},
        )

    np_watts = _compute_np(power_array, ftp)
    if np_watts is None:
        # Array too short for 30-sample rolling window (< 30 samples).
        return ToolResult(
            value=None,
            unit="TSS",
            methodology="NP unavailable: power array shorter than 30-sample rolling window",
            inputs={"duration_secs": duration_secs, "ftp": ftp,
                    "power_records": len(power_array)},
        )

    # Protect against division-by-zero on all-zero arrays (NP == 0).
    if np_watts == 0.0:
        return ToolResult(
            value={"tss": 0.0, "np_watts": 0.0, "if": 0.0, "warnings": []},
            unit="TSS",
            methodology="TrainingPeaks TSS = (duration * NP * IF) / (FTP * 3600) * 100",
            inputs={"duration_secs": duration_secs, "ftp": ftp,
                    "power_records": len(power_array)},
        )

    intensity_factor = np_watts / ftp
    tss = (duration_secs * np_watts * intensity_factor) / (ftp * 3600) * 100

    warnings: list[str] = []
    if duration_secs > 3600 and intensity_factor > 1.05:
        warnings.append(
            f"IF={intensity_factor:.2f} > 1.05 on ride > 60 min: possible stale FTP or data error"
        )

    return ToolResult(
        value={
            "tss": round(tss, 1),
            "np_watts": round(np_watts, 0),
            "if": round(intensity_factor, 3),
            "warnings": warnings,
        },
        unit="TSS",
        methodology="TrainingPeaks TSS = (duration * NP * IF) / (FTP * 3600) * 100",
        inputs={
            "duration_secs": duration_secs,
            "ftp": ftp,
            "power_records": len(power_array),
        },
    )
