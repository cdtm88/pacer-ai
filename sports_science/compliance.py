# sports_science/compliance.py
from .types import ToolResult


def validate_session_vs_actual(planned: dict, actual: dict) -> ToolResult:
    """
    TOOL-07: Compliance percentage and qualitative delta flags.

    Returns compliance_pct=None when planned_tss=0 to avoid division by zero (T-01-07).
    Flags: 'under_performed' if pct < 70, 'over_performed' if pct > 130.
    """
    planned_tss = planned.get("tss", 0)
    actual_tss = actual.get("tss", 0)

    # T-01-07: guard against zero-division
    compliance_pct = (actual_tss / planned_tss * 100) if planned_tss else None
    delta_tss = actual_tss - planned_tss

    flags: list[str] = []
    if compliance_pct is not None:
        if compliance_pct < 70:
            flags.append("under_performed")
        elif compliance_pct > 130:
            flags.append("over_performed")

    return ToolResult(
        value={
            "compliance_pct": round(compliance_pct, 1) if compliance_pct is not None else None,
            "delta_tss": round(delta_tss, 1),
            "flags": flags,
        },
        unit="%",
        methodology="Session compliance: actual TSS / planned TSS * 100",
        inputs={"planned": planned, "actual": actual},
    )
