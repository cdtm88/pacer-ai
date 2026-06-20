# agent/tools.py
"""
Tool registry and dispatcher for the PacerAI agent.

TOOL_SCHEMAS: 8 manual Anthropic tool schema dicts (D-03). One dict per
sports_science export. No programmatic signature inspection — schemas are
explicit and auditable.

TOOL_REGISTRY: maps tool name -> sports_science callable. Must be in 1:1
correspondence with TOOL_SCHEMAS (TRUST-02 invariant asserted at module
import time).

dedup_key: Computes (name, sha256(json.dumps(inputs, sort_keys=True)))
for per-turn deduplication (D-13).

dispatch_tool: Dispatches one tool_use block. Runs sync functions in a
thread (asyncio.to_thread), awaits async log_capability_gap directly
(asyncio.iscoroutinefunction branch — D-06). Surfaces failures as
is_error tool_result blocks and appends an audit entry per call (TRUST-04).
"""

import asyncio
import hashlib
import json

from sports_science import (
    calculate_power_zones,
    calculate_hr_zones,
    estimate_ftp_from_rides,
    compute_tss,
    update_pmc,
    progress_load,
    validate_session_vs_actual,
    log_capability_gap,
)
from sports_science.types import ToolResult  # noqa: F401 – referenced in type hints below

# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

TOOL_REGISTRY: dict = {
    "calculate_power_zones": calculate_power_zones,
    "calculate_hr_zones": calculate_hr_zones,
    "estimate_ftp_from_rides": estimate_ftp_from_rides,
    "compute_tss": compute_tss,
    "update_pmc": update_pmc,
    "progress_load": progress_load,
    "validate_session_vs_actual": validate_session_vs_actual,
    "log_capability_gap": log_capability_gap,
}

# ---------------------------------------------------------------------------
# Tool Schemas (D-03: explicit, auditable; no introspection)
# ---------------------------------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "calculate_power_zones",
        "description": (
            "Returns Coggan/Allen 7-zone power zones from FTP. "
            "Use this whenever the user needs power zone targets, zone boundaries, "
            "or zone-based training intensities — never derive zone numbers directly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "ftp": {
                    "type": "number",
                    "description": "Functional Threshold Power in watts.",
                },
            },
            "required": ["ftp"],
        },
    },
    {
        "name": "calculate_hr_zones",
        "description": (
            "Returns Coggan/Allen 5-zone heart-rate zones from LTHR (Lactate Threshold "
            "Heart Rate). Use this whenever HR zone targets are needed — never invent "
            "heart-rate zone boundaries."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "max_hr_or_lthr": {
                    "type": "number",
                    "description": "Lactate Threshold Heart Rate (or max HR) in bpm.",
                },
            },
            "required": ["max_hr_or_lthr"],
        },
    },
    {
        "name": "estimate_ftp_from_rides",
        "description": (
            "Estimates FTP via the 2-parameter Critical Power model (Morton 1996) from "
            "a list of ride efforts. Use this whenever an FTP estimate is needed from "
            "ride history — never guess or interpolate FTP from training data directly."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "rides": {
                    "type": "array",
                    "description": (
                        "List of ride effort objects. Each object must have "
                        "'duration_secs' (int) and 'mean_power_watts' (float)."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "duration_secs": {"type": "integer"},
                            "mean_power_watts": {"type": "number"},
                        },
                        "required": ["duration_secs", "mean_power_watts"],
                    },
                },
            },
            "required": ["rides"],
        },
    },
    {
        "name": "compute_tss",
        "description": (
            "Computes Training Stress Score (TSS), Normalized Power (NP), and "
            "Intensity Factor (IF) for a power-meter ride. Use this whenever TSS "
            "needs to be calculated — never compute TSS or NP manually."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "power_array": {
                    "type": "array",
                    "description": "1 Hz power samples in watts (one value per second). Zeros for coasting are valid.",
                    "items": {"type": "number"},
                },
                "duration_secs": {
                    "type": "integer",
                    "description": "Total ride duration in seconds.",
                },
                "ftp": {
                    "type": "number",
                    "description": "Rider's Functional Threshold Power in watts.",
                },
            },
            "required": ["power_array", "duration_secs", "ftp"],
        },
    },
    {
        "name": "update_pmc",
        "description": (
            "Performs one-step Banister PMC EWMA update to compute new CTL, ATL, and TSB. "
            "Use this whenever CTL, ATL, or TSB values need to be updated — never compute "
            "Chronic Training Load or Acute Training Load manually."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "prev_ctl": {
                    "type": "number",
                    "description": "Yesterday's Chronic Training Load (CTL) in TSS units.",
                },
                "prev_atl": {
                    "type": "number",
                    "description": "Yesterday's Acute Training Load (ATL) in TSS units.",
                },
                "tss": {
                    "type": "number",
                    "description": "Today's Training Stress Score.",
                },
                "days_of_data": {
                    "type": "integer",
                    "description": "Total days of TSS data accumulated (used for cold-start guard).",
                },
            },
            "required": ["prev_ctl", "prev_atl", "tss", "days_of_data"],
        },
    },
    {
        "name": "progress_load",
        "description": (
            "Calculates a safe weekly CTL ramp target respecting the 8 pts/week "
            "standard ceiling and optional back-protective constraints. Use this whenever "
            "a progressive training load increase is being planned — never determine load "
            "ramp rates manually."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "current_ctl": {
                    "type": "number",
                    "description": "Rider's current Chronic Training Load (CTL).",
                },
                "target_ctl": {
                    "type": "number",
                    "description": "Desired target CTL to progress toward.",
                },
                "constraints": {
                    "type": "object",
                    "description": (
                        "Rider constraints. Supported keys: 'back_issues' (boolean), "
                        "'load_ramp_flag_threshold_pct' (number, percentage of current CTL)."
                    ),
                },
            },
            "required": ["current_ctl", "target_ctl", "constraints"],
        },
    },
    {
        "name": "validate_session_vs_actual",
        "description": (
            "Computes compliance percentage and qualitative delta flags by comparing "
            "a planned session against the actual session. Use this whenever session "
            "compliance or training adherence needs to be evaluated."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "planned": {
                    "type": "object",
                    "description": "Planned session object. Must include 'tss' (number).",
                },
                "actual": {
                    "type": "object",
                    "description": "Actual session object. Must include 'tss' (number).",
                },
            },
            "required": ["planned", "actual"],
        },
    },
    {
        "name": "log_capability_gap",
        "description": (
            "Call this when a quantitative physiological method or calculation is needed "
            "but is not covered by any other tool in this registry. This logs the gap for "
            "the development team and returns a user-safe qualitative fallback message. "
            "Do NOT improvise or estimate a physiological number directly — call this "
            "tool instead and use qualitative language in your response (TRUST-05)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "method_name": {
                    "type": "string",
                    "description": "The internal name of the missing method or calculation.",
                },
                "context": {
                    "type": "object",
                    "description": "Contextual data at the time of the gap (key-value pairs).",
                },
            },
            "required": ["method_name", "context"],
        },
    },
]

# ---------------------------------------------------------------------------
# TRUST-02 invariant: schema name set must equal registry key set.
# Asserted at import time so misconfiguration is caught immediately.
# ---------------------------------------------------------------------------

_schema_names = {s["name"] for s in TOOL_SCHEMAS}
_registry_names = set(TOOL_REGISTRY)
assert _schema_names == _registry_names, (
    f"TRUST-02 violation: TOOL_SCHEMAS names {_schema_names} "
    f"!= TOOL_REGISTRY keys {_registry_names}"
)


# ---------------------------------------------------------------------------
# Deduplication key (D-13)
# ---------------------------------------------------------------------------


def dedup_key(name: str, inputs: dict) -> tuple:
    """
    Returns (name, sha256_hex) where the hash is derived from
    json.dumps(inputs, sort_keys=True). Key ordering does not affect the hash.
    """
    digest = hashlib.sha256(
        json.dumps(inputs, sort_keys=True).encode()
    ).hexdigest()
    return (name, digest)


# ---------------------------------------------------------------------------
# Tool dispatcher (D-04, D-06, D-14, TRUST-04)
# ---------------------------------------------------------------------------


async def dispatch_tool(tool_use_block, audit_log: list) -> dict:
    """
    Dispatch one tool_use block and return an Anthropic tool_result content block.

    - Unknown tool name: appends audit error entry, returns is_error block.
    - Sync function (all compute tools): runs via asyncio.to_thread (D-06).
    - Async function (log_capability_gap): awaited directly (asyncio.iscoroutinefunction).
    - Exception: appends audit error entry, returns is_error block (D-14: never swallowed).
    - Success: appends audit entry with result.model_dump(), returns is_error=False block.
    """
    name = tool_use_block.name
    inputs = tool_use_block.input
    tool_use_id = tool_use_block.id

    fn = TOOL_REGISTRY.get(name)
    if fn is None:
        audit_log.append({
            "tool_use_id": tool_use_id,
            "name": name,
            "error": f"unknown tool '{name}'",
        })
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [{"type": "text", "text": f"Error: unknown tool '{name}'"}],
            "is_error": True,
        }

    try:
        if asyncio.iscoroutinefunction(fn):
            # log_capability_gap (and any future async tool) is awaited directly.
            result: ToolResult = await fn(**inputs)
        else:
            # Sync compute functions run in a thread to avoid blocking the event loop.
            result: ToolResult = await asyncio.to_thread(fn, **inputs)

        audit_log.append({
            "tool_use_id": tool_use_id,
            "name": name,
            "result": result.model_dump(),
        })
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [{"type": "text", "text": json.dumps(result.to_tool_response())}],
            "is_error": False,
        }

    except Exception as exc:  # noqa: BLE001
        audit_log.append({
            "tool_use_id": tool_use_id,
            "name": name,
            "error": str(exc),
        })
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [{"type": "text", "text": f"Error: {exc}"}],
            "is_error": True,
        }
