# sports_science/__init__.py
"""
Public API surface for the sports-science tool library.

__all__ defines the registry-eligible function set (TRUST-02 contract).
The Phase 2 tool registry wraps ONLY these names as Anthropic tool schemas.
No private helpers (_compute_np, _cp_model, _is_quality_effort, _get_supabase)
are exported. Zero SDK imports from the LLM layer anywhere in this package (TRUST-01).
"""
from .capability_gap import log_capability_gap
from .compliance import validate_session_vs_actual
from .ftp import estimate_ftp_from_rides
from .load import progress_load
from .metrics import compute_tss
from .pmc import update_pmc
from .types import ToolResult
from .zones import calculate_hr_zones, calculate_power_zones

__all__ = [
    "calculate_power_zones",
    "calculate_hr_zones",
    "estimate_ftp_from_rides",
    "compute_tss",
    "update_pmc",
    "progress_load",
    "validate_session_vs_actual",
    "log_capability_gap",
    "ToolResult",
]
