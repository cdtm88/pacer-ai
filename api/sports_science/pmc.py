# sports_science/pmc.py
import numpy as np
from .constants import CTL_TC, ATL_TC, PMC_MIN_DAYS
from .types import ToolResult

# Module-level decay alphas derived from Banister time constants (D-05).
# CTL (Chronic Training Load): 42-day time constant -> alpha ~0.0235
# ATL (Acute Training Load):  7-day time constant  -> alpha ~0.1331
CTL_ALPHA: float = 1 - np.exp(-1 / CTL_TC)
ATL_ALPHA: float = 1 - np.exp(-1 / ATL_TC)


def update_pmc(
    prev_ctl: float,
    prev_atl: float,
    tss: float,
    days_of_data: int,
) -> ToolResult:
    """
    TOOL-05: One-step Banister PMC EWMA update.

    Computes the new CTL, ATL, and TSB from the previous day's values and today's TSS.
    D-06 cold-start guard: tss_display_ready is False until days_of_data >= PMC_MIN_DAYS (28).

    Args:
        prev_ctl: Yesterday's CTL (Chronic Training Load) in TSS units.
        prev_atl: Yesterday's ATL (Acute Training Load) in TSS units.
        tss: Today's Training Stress Score.
        days_of_data: Total days of TSS data accumulated (used for cold-start guard).

    Returns:
        ToolResult with value={ctl, atl, tsb, tss_display_ready}.
    """
    new_ctl = prev_ctl + CTL_ALPHA * (tss - prev_ctl)
    new_atl = prev_atl + ATL_ALPHA * (tss - prev_atl)
    # TSB = "form today" = yesterday's CTL minus yesterday's ATL
    tsb = prev_ctl - prev_atl
    ready = days_of_data >= PMC_MIN_DAYS

    return ToolResult(
        value={
            "ctl": round(new_ctl, 2),
            "atl": round(new_atl, 2),
            "tsb": round(tsb, 2),
            "tss_display_ready": ready,
        },
        unit="TSS",
        methodology="Banister PMC EWMA CTL_TC=42 ATL_TC=7",
        inputs={
            "prev_ctl": prev_ctl,
            "prev_atl": prev_atl,
            "tss": tss,
            "days_of_data": days_of_data,
        },
    )
