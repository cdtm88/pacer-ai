# sports_science/load.py
from .types import ToolResult

CTL_RAMP_CEILING_PER_WEEK: float = 8.0  # max CTL points per week (standard safe ramp)


def progress_load(
    current_ctl: float,
    target_ctl: float,
    constraints: dict,
) -> ToolResult:
    """
    TOOL-06: Safe weekly load ramp target with back-protective caps (D-09).

    Applies the standard 8 pts/week CTL ramp ceiling and, when back_issues is True,
    further caps the increase at load_ramp_flag_threshold_pct% of current_ctl.
    """
    # Start from standard ceiling
    max_ctl_increase = CTL_RAMP_CEILING_PER_WEEK
    back_constraints_applied = bool(constraints.get("back_issues", False))

    if back_constraints_applied:
        ramp_threshold = constraints.get("load_ramp_flag_threshold_pct", 10) / 100
        # Back-protective cap: ramp_threshold% of current CTL (D-09)
        back_cap = current_ctl * ramp_threshold
        max_ctl_increase = min(max_ctl_increase, back_cap)

    recommended_ctl = min(current_ctl + max_ctl_increase, target_ctl)

    return ToolResult(
        value={
            "recommended_ctl_target": round(recommended_ctl, 1),
            "max_weekly_increase": round(max_ctl_increase, 1),
            "back_constraints_applied": back_constraints_applied,
        },
        unit="CTL",
        methodology="CTL ramp ceiling 8pts/week; back-protective JSONB constraints applied",
        inputs={
            "current_ctl": current_ctl,
            "target_ctl": target_ctl,
            "constraints": constraints,
        },
    )
