# sports_science/plan.py
"""
TOOL-09: 4-week mesocycle plan generator.

Pure computation only -- no DB calls, no imports of other sports_science tools
(trust model: the agent calls tools in sequence; tools never chain internally).

Generate a structured 4-week base mesocycle from interview data.
Week 1 is conservative (endurance only, zone 2, capped at 45 min).
Week 4 is a recovery week (40% volume reduction).
FTP-confidence gate: power_targets are None when ftp_confidence is
insufficient_data or low; populated otherwise.
"""
from .types import ToolResult

# Default day assignments when preferred_days is not specified or insufficient
_DEFAULT_DAYS = ["Tuesday", "Thursday", "Saturday", "Sunday"]

# Session count from weekly_hours
def _sessions_per_week(weekly_hours: float) -> int:
    if weekly_hours <= 1.0:
        return 2
    elif weekly_hours <= 3.0:
        return 3
    else:
        return 4


def _build_zone2_targets(hr_zones: list[dict]) -> dict:
    """Extract zone 2 bounds from hr_zones list."""
    for zone in hr_zones:
        if zone.get("zone") == 2:
            return {
                "zone": 2,
                "lower_bpm": zone.get("lower_bpm"),
                "upper_bpm": zone.get("upper_bpm"),
            }
    # Fallback if zone 2 not found
    return {"zone": 2, "lower_bpm": None, "upper_bpm": None}


def _build_power_targets(ftp_watts: float) -> dict:
    """Build zone 2 power targets from FTP (56-75% FTP)."""
    return {
        "zone": 2,
        "lower_watts": round(ftp_watts * 0.56),
        "upper_watts": round(ftp_watts * 0.75),
    }


def _build_sessions(
    weekly_hours: float,
    back_status: str,
    hr_zones: list[dict],
    ftp_confidence: str,
    ftp_watts: float | None,
) -> list[dict]:
    """Build the full 4-week session list."""
    n_sessions = _sessions_per_week(weekly_hours)
    zone2_targets = _build_zone2_targets(hr_zones)
    use_power = ftp_confidence not in ("insufficient_data", "low") and ftp_watts is not None
    is_back_moderate = back_status == "moderate"

    # Base duration per session from weekly_hours (distribute hours across sessions)
    # Convert weekly_hours to minutes, split across sessions
    total_weekly_minutes = weekly_hours * 60
    base_duration = int(total_weekly_minutes / n_sessions)
    # Clamp reasonable range
    base_duration = max(20, min(base_duration, 90))

    sessions = []
    # Preferred days cycling (use first n_sessions from default)
    days = _DEFAULT_DAYS[:n_sessions]

    for week in range(1, 5):
        for i, day in enumerate(days):
            duration = base_duration

            # Week 1: conservative policy
            if week == 1:
                duration = min(duration, 45)
                if is_back_moderate:
                    duration = min(duration, 30)
                session_type = "endurance"
                rpe = 3
                power_targets = None  # Week 1 always HR/RPE only
                obj = "Aerobic base building -- zone 2 steady effort, focus on breathing and cadence"
                structure = {
                    "warmup": {"duration_minutes": 5, "description": "Easy spin, HR building gradually"},
                    "main_set": {
                        "duration_minutes": duration - 10,
                        "description": "Zone 2 steady effort, maintain conversation pace",
                    },
                    "cooldown": {"duration_minutes": 5, "description": "Easy spin, let HR settle"},
                }

            # Week 2
            elif week == 2:
                if is_back_moderate:
                    duration = min(duration, 30)
                session_type = "endurance"
                rpe = 4
                power_targets = _build_power_targets(ftp_watts) if use_power else None
                obj = "Building aerobic endurance -- sustained zone 2 effort"
                structure = {
                    "warmup": {"duration_minutes": 5, "description": "Easy spin, gradual HR build"},
                    "main_set": {
                        "duration_minutes": duration - 10,
                        "description": "Zone 2 steady-state effort",
                    },
                    "cooldown": {"duration_minutes": 5, "description": "Easy spin"},
                }

            # Week 3
            elif week == 3:
                session_type = "endurance" if i % 2 == 0 else "strength"
                rpe = 5
                power_targets = _build_power_targets(ftp_watts) if use_power else None
                obj = (
                    "Aerobic endurance with muscular endurance elements"
                    if session_type == "strength"
                    else "Sustained aerobic effort"
                )
                structure = {
                    "warmup": {"duration_minutes": 8, "description": "Progressive warm-up"},
                    "main_set": {
                        "duration_minutes": duration - 13,
                        "description": (
                            "Low cadence work (60-70 rpm) for muscular endurance"
                            if session_type == "strength"
                            else "Zone 2 steady effort"
                        ),
                    },
                    "cooldown": {"duration_minutes": 5, "description": "Easy spin"},
                }

            # Week 4: recovery week (40% volume reduction)
            else:
                duration = int(duration * 0.6)
                session_type = "recovery"
                rpe = 3
                power_targets = _build_power_targets(ftp_watts) if use_power else None
                obj = "Active recovery -- very easy effort, flush fatigue"
                structure = {
                    "warmup": {"duration_minutes": 5, "description": "Very easy spin"},
                    "main_set": {
                        "duration_minutes": max(5, duration - 10),
                        "description": "Zone 1 easy effort, no pressure to push",
                    },
                    "cooldown": {"duration_minutes": 5, "description": "Easy spin"},
                }

            sessions.append({
                "week": week,
                "day": day,
                "type": session_type,
                "objective": obj,
                "duration_minutes": duration,
                "structure": structure,
                "zone_targets": zone2_targets,
                "power_targets": power_targets,
                "rpe_target": rpe,
            })

    return sessions


def _applied_constraints(back_status: str) -> list[str]:
    """Build the constraints_applied list."""
    constraints = ["week1_conservative", "week4_40pct_recovery"]
    if back_status == "moderate":
        constraints.append("back_protective")
    return constraints


def generate_plan(
    user_id: str,
    weekly_hours: float,
    back_status: str,
    current_ctl: float,
    load_targets: dict,
    hr_zones: list[dict],
    ftp_confidence: str,
    ftp_watts: float | None,
) -> ToolResult:
    """
    TOOL-09: Generate a structured 4-week base mesocycle plan.

    Pure computation -- no DB calls, no imports of other tools (trust model).
    The agent calls tools in sequence; this function never chains internally.

    Args:
        user_id:        User UUID.
        weekly_hours:   Available training hours per week.
        back_status:    "none" | "mild" | "moderate" (D-05 gate).
        current_ctl:    Current Chronic Training Load (from update_pmc).
        load_targets:   Output of progress_load tool (dict with recommended_ctl_target).
        hr_zones:       Output of calculate_hr_zones (list of zone dicts).
        ftp_confidence: "insufficient_data" | "low" | "medium" | "high" (D-25 gate).
        ftp_watts:      FTP in watts (None when ftp_confidence is insufficient_data).

    Returns:
        ToolResult with a 4-week session list and metadata.
    """
    sessions = _build_sessions(weekly_hours, back_status, hr_zones, ftp_confidence, ftp_watts)

    return ToolResult(
        value={
            "plan_id": None,
            "mesocycle_weeks": 4,
            "sessions": sessions,
            "week4_volume_reduction_pct": 40,
            "constraints_applied": _applied_constraints(back_status),
            "methodology": "4-week base mesocycle; Week 1 conservative; Week 4 -40% recovery",
        },
        unit="",
        methodology="mesocycle_plan_generation",
        inputs={
            "user_id": user_id,
            "weekly_hours": weekly_hours,
            "back_status": back_status,
            "ftp_confidence": ftp_confidence,
        },
    )
