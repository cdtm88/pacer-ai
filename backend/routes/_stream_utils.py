# backend/routes/_stream_utils.py
"""
Pure, dependency-free utilities for Phase 11 (Ride Analysis Dashboard).

detect_presence() and downsample() operate on the aligned per-second rows
produced by parse_fit_stream (backend/routes/rides.py). Both functions are
stdlib-only -- no imports beyond typing -- so they carry zero I/O or
framework coupling and stay trivially unit-testable.

NP/TSS/zone maths are always computed from the FULL series before
downsampling runs; downsample fidelity only affects what the chart renders,
never a physiological number (TRUST-01 is unaffected by this module).
"""
from typing import Optional


def detect_presence(channel_values: list[Optional[float]]) -> bool:
    """A channel is 'present' iff it has more than one distinct non-null
    value (D-11-03). A channel with 0 or 1 distinct non-null values (e.g.
    all-None, or a flat constant) is reported absent -- this is what hides
    elevation/GPS charts on indoor Zwift rides with no elevation sensor."""
    return len({v for v in channel_values if v is not None}) > 1


def downsample(
    series: list[dict],
    target_interval_secs: int = 3,
    max_points: int = 4000,
) -> list[dict]:
    """
    Stride-sample a per-second-aligned series to ~1 point per
    target_interval_secs, capped at max_points so no payload exceeds
    ~4000 points (D-11-04).

    Preserves the first record (stride sampling always includes index 0).
    Returns the input unchanged when empty.
    """
    n = len(series)
    if n == 0:
        return series
    # Effective interval: widen further if target_interval_secs alone would
    # still exceed the cap (ceil division so the cap is always respected).
    interval = max(target_interval_secs, -(-n // max_points))
    return series[::interval]
