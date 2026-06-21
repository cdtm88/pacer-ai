# Phase 1: Sports-Science Foundation - Pattern Map

**Mapped:** 2026-06-19
**Files analyzed:** 21 (12 source + 9 test)
**Analogs found:** 0 / 21 (greenfield — no existing source code)

---

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `sports_science/__init__.py` | config | — | no existing analog — greenfield | — |
| `sports_science/types.py` | model | transform | no existing analog — greenfield | — |
| `sports_science/constants.py` | config | — | no existing analog — greenfield | — |
| `sports_science/zones.py` | utility | transform | no existing analog — greenfield | — |
| `sports_science/metrics.py` | utility | transform | no existing analog — greenfield | — |
| `sports_science/pmc.py` | utility | transform | no existing analog — greenfield | — |
| `sports_science/ftp.py` | utility | transform | no existing analog — greenfield | — |
| `sports_science/load.py` | utility | transform | no existing analog — greenfield | — |
| `sports_science/compliance.py` | utility | transform | no existing analog — greenfield | — |
| `sports_science/capability_gap.py` | service | request-response | no existing analog — greenfield | — |
| `supabase/migrations/0001_initial_schema.sql` | migration | CRUD | no existing analog — greenfield | — |
| `requirements.txt` | config | — | no existing analog — greenfield | — |
| `pytest.ini` | config | — | no existing analog — greenfield | — |
| `ruff.toml` | config | — | no existing analog — greenfield | — |
| `.env.example` | config | — | no existing analog — greenfield | — |
| `tests/sports_science/conftest.py` | test | — | no existing analog — greenfield | — |
| `tests/sports_science/test_types.py` | test | transform | no existing analog — greenfield | — |
| `tests/sports_science/test_zones.py` | test | transform | no existing analog — greenfield | — |
| `tests/sports_science/test_metrics.py` | test | transform | no existing analog — greenfield | — |
| `tests/sports_science/test_pmc.py` | test | transform | no existing analog — greenfield | — |
| `tests/sports_science/test_ftp.py` | test | transform | no existing analog — greenfield | — |
| `tests/sports_science/test_load.py` | test | transform | no existing analog — greenfield | — |
| `tests/sports_science/test_compliance.py` | test | transform | no existing analog — greenfield | — |
| `tests/sports_science/test_capability_gap.py` | test | request-response | no existing analog — greenfield | — |
| `tests/sports_science/test_import_boundary.py` | test | — | no existing analog — greenfield | — |

---

## Pattern Assignments

Since this is a greenfield project, all patterns come from RESEARCH.md code examples and locked decisions. The excerpts below are the canonical patterns the planner MUST reference — treat them as "copy from RESEARCH.md lines X-Y" with the actual code reproduced here for planner convenience.

---

### `sports_science/types.py` (model, transform)

**Source:** RESEARCH.md Pattern 1 / D-01 / D-09 (TOOL-09)
**Build order:** FIRST — all other modules depend on this.

**Full file pattern:**
```python
# sports_science/types.py
from pydantic import BaseModel
from typing import Any

class ToolResult(BaseModel):
    """Immutable result returned by every sports-science tool function."""
    value: Any
    unit: str
    methodology: str
    inputs: dict

    model_config = {"frozen": True}

    def to_tool_response(self) -> dict:
        """Serialize for Anthropic tool_result content block."""
        return self.model_dump()
```

**Validation note (A1):** Verify `model_config = {"frozen": True}` syntax works in Pydantic 2.13.x on first install. Alternative if broken: `model_config = ConfigDict(frozen=True)` with `from pydantic import ConfigDict`.

---

### `sports_science/constants.py` (config)

**Source:** RESEARCH.md D-05 / D-10
**Build order:** SECOND — zones.py, metrics.py, pmc.py, ftp.py all import from here.

**Full file pattern:**
```python
# sports_science/constants.py

# Banister PMC time constants (days) — D-05
CTL_TC: int = 42
ATL_TC: int = 7
PMC_MIN_DAYS: int = 28  # days before TSB is meaningful (D-06)

# Coggan/Allen 7-zone power model — boundaries as % of FTP (decimal)
# Zone membership: >= lower AND < upper (except Z7: >= lower only) — avoid dual membership (Pitfall 4)
POWER_ZONE_BOUNDARIES = [
    {"zone": 1, "name": "Active Recovery",    "lower": 0.00, "upper": 0.55},
    {"zone": 2, "name": "Endurance",          "lower": 0.55, "upper": 0.75},
    {"zone": 3, "name": "Tempo",              "lower": 0.75, "upper": 0.90},
    {"zone": 4, "name": "Threshold",          "lower": 0.90, "upper": 1.05},
    {"zone": 5, "name": "VO2max",             "lower": 1.05, "upper": 1.20},
    {"zone": 6, "name": "Anaerobic Capacity", "lower": 1.20, "upper": 1.50},
    {"zone": 7, "name": "Neuromuscular",      "lower": 1.50, "upper": None},
]

# NP spike filter (metrics.py) — D-10 / Claude's Discretion
NP_SPIKE_MULTIPLIER: float = 3.0       # clip at FTP * 3
NP_SPIKE_FALLBACK_WATTS: float = 600.0 # cap when no FTP available
NP_MIN_DURATION_SECS: int = 600        # 10 minutes minimum for TSS

# CP model quality-effort filter (ftp.py) — D-03
QUALITY_EFFORT_MIN_DURATION_SECS: int = 180   # 3 minutes
QUALITY_EFFORT_MIN_POWER_RATIO: float = 0.85  # 85% of best FTP estimate
QUALITY_EFFORT_FALLBACK_WATTS: float = 150.0  # threshold when no FTP estimate
MIN_QUALITY_EFFORTS: int = 4
```

---

### `sports_science/zones.py` (utility, transform)

**Source:** RESEARCH.md TOOL-01, TOOL-02 / Coggan/Allen 7-zone model
**Dependencies:** `constants.py`, `types.py`

**Core pattern — power zones:**
```python
# sports_science/zones.py
from .constants import POWER_ZONE_BOUNDARIES
from .types import ToolResult

def calculate_power_zones(ftp: float) -> ToolResult:
    """TOOL-01: Coggan/Allen 7-zone power zones from FTP."""
    zones = []
    for z in POWER_ZONE_BOUNDARIES:
        lower_watts = round(z["lower"] * ftp)
        upper_watts = round(z["upper"] * ftp) if z["upper"] else None
        zones.append({
            "zone": z["zone"],
            "name": z["name"],
            "lower_watts": lower_watts,
            "upper_watts": upper_watts,
        })

    return ToolResult(
        value=zones,
        unit="watts",
        methodology="Coggan/Allen 7-zone power model",
        inputs={"ftp": ftp},
    )
```

**Zone membership rule (Pitfall 4):** Use `>= lower AND < upper` for Z1-Z6; use `>= lower` only for Z7. Upper bound is exclusive to prevent dual membership at exact boundary values.

**HR zones follow the same structural pattern** with LTHR-based or MaxHR-based boundaries instead of FTP multipliers (TOOL-02). Methodology string: `"Coggan/Allen HR zones from LTHR"` or `"5-zone HR model from MaxHR"`.

---

### `sports_science/metrics.py` (utility, transform)

**Source:** RESEARCH.md Pattern 2 / TOOL-04 / Code Examples (TSS Calculation)
**Dependencies:** `constants.py`, `types.py`, `numpy`

**NP calculation (private helper):**
```python
# sports_science/metrics.py
import numpy as np
from .constants import NP_SPIKE_MULTIPLIER, NP_SPIKE_FALLBACK_WATTS
from .types import ToolResult

def _compute_np(power_array: list[float], ftp: float | None) -> float | None:
    """
    Normalized Power per TrainingPeaks definition.
    CRITICAL: Zeros MUST be included (coasting counts). Spike filter BEFORE rolling mean.
    """
    arr = np.array(power_array, dtype=float)

    # Spike filter: clip at FTP*3 or fallback cap if no FTP
    cap = ftp * NP_SPIKE_MULTIPLIER if ftp else NP_SPIKE_FALLBACK_WATTS
    arr = np.clip(arr, 0, cap)

    # 30-second rolling mean (assumes 1 Hz data)
    window = 30
    if len(arr) < window:
        return None
    rolling_mean = np.convolve(arr, np.ones(window) / window, mode='valid')

    # 4th power -> mean -> 4th root
    return float(np.mean(rolling_mean ** 4) ** 0.25)
```

**TSS calculation (public, TOOL-04):**
```python
def compute_tss(
    power_array: list[float],
    duration_secs: int,
    ftp: float,
) -> ToolResult:
    from .constants import NP_MIN_DURATION_SECS

    if duration_secs < NP_MIN_DURATION_SECS:
        return ToolResult(
            value=None,
            unit="TSS",
            methodology="TrainingPeaks TSS; ride too short (<10 min)",
            inputs={"duration_secs": duration_secs, "ftp": ftp},
        )

    np_watts = _compute_np(power_array, ftp)
    if np_watts is None:
        return ToolResult(value=None, unit="TSS",
                          methodology="NP unavailable", inputs={})

    intensity_factor = np_watts / ftp
    tss = (duration_secs * np_watts * intensity_factor) / (ftp * 3600) * 100

    warnings = []
    if duration_secs > 3600 and intensity_factor > 1.05:
        warnings.append(
            f"IF={intensity_factor:.2f} > 1.05 on ride > 60 min: possible stale FTP or data error"
        )

    return ToolResult(
        value={"tss": round(tss, 1), "np_watts": round(np_watts, 0),
               "if": round(intensity_factor, 3), "warnings": warnings},
        unit="TSS",
        methodology="TrainingPeaks TSS = (duration * NP * IF) / (FTP * 3600) * 100",
        inputs={"duration_secs": duration_secs, "ftp": ftp,
                "power_records": len(power_array)},
    )
```

**Anti-pattern to avoid (Pitfall 1):** Never filter zeros from `power_array` before calling `_compute_np`. Coasting is meaningful load data.

---

### `sports_science/pmc.py` (utility, transform)

**Source:** RESEARCH.md Pattern 3 / TOOL-05 / D-05, D-06
**Dependencies:** `constants.py`, `types.py`, `numpy`

**Full pattern:**
```python
# sports_science/pmc.py
import numpy as np
from .constants import CTL_TC, ATL_TC, PMC_MIN_DAYS
from .types import ToolResult

# Module-level decay alphas derived from time constants (D-05)
CTL_ALPHA = 1 - np.exp(-1 / CTL_TC)  # ~0.0235 for 42-day TC
ATL_ALPHA = 1 - np.exp(-1 / ATL_TC)  # ~0.1331 for 7-day TC

def update_pmc(
    prev_ctl: float,
    prev_atl: float,
    tss: float,
    days_of_data: int,
) -> ToolResult:
    """TOOL-05: One-step Banister PMC EWMA update. D-06: cold-start guard."""
    new_ctl = prev_ctl + CTL_ALPHA * (tss - prev_ctl)
    new_atl = prev_atl + ATL_ALPHA * (tss - prev_atl)
    tsb = prev_ctl - prev_atl  # TSB = yesterday's CTL - ATL ("form today")
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
        inputs={"prev_ctl": prev_ctl, "prev_atl": prev_atl,
                "tss": tss, "days_of_data": days_of_data},
    )
```

**Cold-start contract (D-06):** Initialize with `prev_ctl=0, prev_atl=0` on first ride. `tss_display_ready` is `False` until `days_of_data >= 28`. Consumers (Phase 4 UI) must gate the TSB chip on this flag.

---

### `sports_science/ftp.py` (utility, transform)

**Source:** RESEARCH.md Pattern 4 / Code Examples (Quality Effort Filter) / TOOL-03 / D-03, D-04
**Dependencies:** `constants.py`, `types.py`, `numpy`, `scipy`

**Quality effort filter:**
```python
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
    duration = effort.get("duration_secs", 0)
    mean_power = effort.get("mean_power_watts", 0)
    threshold = (
        best_ftp_estimate * QUALITY_EFFORT_MIN_POWER_RATIO
        if best_ftp_estimate
        else QUALITY_EFFORT_FALLBACK_WATTS
    )
    return duration >= QUALITY_EFFORT_MIN_DURATION_SECS and mean_power >= threshold

def _cp_model(t: np.ndarray, cp: float, wprime: float) -> np.ndarray:
    """2-parameter CP model: P(t) = CP + W'/t"""
    return cp + wprime / t
```

**Confidence levels (D-03):**
- `"insufficient_data"`: < 4 quality efforts — return `value=None`
- `"low"`: 4-6 efforts
- `"medium"`: 7-12 efforts
- `"high"`: 12+ efforts with good duration variance

**Sparse data contract (D-04):** When `< MIN_QUALITY_EFFORTS`, return:
```python
ToolResult(
    value=None,
    unit="watts",
    methodology="2-parameter Critical Power model (Morton 1996)",
    inputs={"quality_efforts": len(quality_efforts), "required": MIN_QUALITY_EFFORTS},
)
```
Never compute a number from insufficient data.

**scipy curve_fit call:**
```python
popt, _ = curve_fit(
    _cp_model,
    np.array(durations_sec),
    np.array(mean_powers),
    p0=[200.0, 20000.0],                        # initial guess: CP=200W, W'=20kJ
    bounds=([50.0, 1000.0], [500.0, 100000.0]), # physiological bounds
    maxfev=5000,
)
cp, wprime = popt
```

**Assumption (A4):** Verify `bounds` list-of-lists syntax works in scipy 1.17.x on first install.

---

### `sports_science/load.py` (utility, transform)

**Source:** RESEARCH.md TOOL-06 / D-09
**Dependencies:** `types.py`

**Core pattern:**
```python
# sports_science/load.py
from .types import ToolResult

CTL_RAMP_CEILING_PER_WEEK = 8.0  # max CTL points per week (standard safe ramp)

def progress_load(
    current_ctl: float,
    target_ctl: float,
    constraints: dict,
) -> ToolResult:
    """TOOL-06: Safe weekly load ramp target with back-protective caps (D-09)."""
    # Standard ramp ceiling
    max_ctl_increase = CTL_RAMP_CEILING_PER_WEEK

    # Apply back-protective constraints (D-09)
    if constraints.get("back_issues"):
        max_weekly_hours = constraints.get("max_initial_weekly_hours", 3.5)
        ramp_threshold = constraints.get("load_ramp_flag_threshold_pct", 10) / 100
        # Cap increase at ramp threshold percentage of current CTL
        max_ctl_increase = min(max_ctl_increase, current_ctl * ramp_threshold)

    recommended_ctl = min(current_ctl + max_ctl_increase, target_ctl)

    return ToolResult(
        value={
            "recommended_ctl_target": round(recommended_ctl, 1),
            "max_weekly_increase": round(max_ctl_increase, 1),
            "back_constraints_applied": constraints.get("back_issues", False),
        },
        unit="CTL",
        methodology="CTL ramp ceiling 8pts/week; back-protective JSONB constraints applied",
        inputs={"current_ctl": current_ctl, "target_ctl": target_ctl,
                "constraints": constraints},
    )
```

---

### `sports_science/compliance.py` (utility, transform)

**Source:** RESEARCH.md TOOL-07
**Dependencies:** `types.py`

**Core pattern:**
```python
# sports_science/compliance.py
from .types import ToolResult

def validate_session_vs_actual(planned: dict, actual: dict) -> ToolResult:
    """TOOL-07: Compliance percentage and qualitative delta flags."""
    planned_tss = planned.get("tss", 0)
    actual_tss = actual.get("tss", 0)

    compliance_pct = (actual_tss / planned_tss * 100) if planned_tss else None
    delta_tss = actual_tss - planned_tss

    flags = []
    if compliance_pct is not None:
        if compliance_pct < 70:
            flags.append("under_performed")
        elif compliance_pct > 130:
            flags.append("over_performed")

    return ToolResult(
        value={
            "compliance_pct": round(compliance_pct, 1) if compliance_pct else None,
            "delta_tss": round(delta_tss, 1),
            "flags": flags,
        },
        unit="%",
        methodology="Session compliance: actual TSS / planned TSS * 100",
        inputs={"planned": planned, "actual": actual},
    )
```

---

### `sports_science/capability_gap.py` (service, request-response)

**Source:** RESEARCH.md Code Examples (Supabase capability_gap Insert) / GAP-01, GAP-02, GAP-03 / Pitfall 6
**Dependencies:** `types.py`, `supabase` Python client, env vars

**Full pattern:**
```python
# sports_science/capability_gap.py
import os
from supabase import create_client, Client
from .types import ToolResult

def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    # Use SERVICE_ROLE_KEY for backend writes — bypasses RLS (Pitfall 6, D-07)
    # NEVER expose service role key to frontend
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)

def log_capability_gap(
    method_name: str,
    context: dict,
    user_id: str | None = None,
) -> ToolResult:
    """
    TOOL-08: Log a capability gap to DB and return a user-safe fallback message.
    GAP-03: user-facing message must NOT expose internal method_name.
    """
    supabase = _get_supabase()
    supabase.table("capability_gaps").insert({
        "user_id": user_id,
        "method_name": method_name,
        "description": f"Missing tool: {method_name}",
        "context": context,
    }).execute()

    # GAP-03: generic user message; method_name goes to DB only
    user_message = (
        "I don't have a specialized tool for that calculation yet. "
        "I've logged it for the development team. "
        "I'll use a qualitative approach for now."
    )

    return ToolResult(
        value={"status": "logged", "message": user_message},
        unit="",
        methodology="capability_gap_log",
        inputs={"context_keys": list(context.keys())},
    )
```

**Async upgrade path (Open Question 2):** Phase 1 uses sync `create_client`. Phase 2 migrates to `acreate_client` for FastAPI lifespan compatibility. Verify `AsyncClient` import surface in `supabase==2.31.0` before Phase 2.

---

### `sports_science/__init__.py` (config)

**Pattern:** Export public functions only — no Anthropic imports, no internal helpers.

```python
# sports_science/__init__.py
from .zones import calculate_power_zones, calculate_hr_zones
from .metrics import compute_tss
from .pmc import update_pmc
from .ftp import estimate_ftp_from_rides
from .load import progress_load
from .compliance import validate_session_vs_actual
from .capability_gap import log_capability_gap
from .types import ToolResult

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
```

---

### `supabase/migrations/0001_initial_schema.sql` (migration, CRUD)

**Source:** RESEARCH.md Pattern 5 / D-07, D-08, D-09 / ARCHITECTURE.md 8-table schema

**RLS template (apply to all 8 tables):**
```sql
-- Pattern for every table: enable RLS + user-owns-row policy
ALTER TABLE public.<table_name> ENABLE ROW LEVEL SECURITY;

CREATE POLICY "<table_name>: own row" ON public.<table_name>
  USING (user_id = auth.uid());
```

**Tables to create:** `users`, `profiles` (with `constraints JSONB` column per D-09), `rides`, `sessions`, `training_plans`, `pmc_history`, `conversations`, `capability_gaps`.

**capability_gaps special case (Pitfall 6):** Backend inserts use `SUPABASE_SERVICE_ROLE_KEY` (bypasses RLS). The RLS policy still exists for read access. The `method_name` column must be present (referenced in `log_capability_gap`).

**profiles.constraints JSONB schema (D-09):**
```sql
-- Default for users with no back issues
constraints jsonb DEFAULT '{"back_issues": false}'::jsonb
-- Full back-issues schema example:
-- {"back_issues": true, "max_initial_weekly_hours": 3.5,
--  "no_standing_efforts": true, "no_sprint_efforts": true,
--  "load_ramp_flag_threshold_pct": 10}
```

---

### Test Files: `tests/sports_science/` (test)

**Source:** RESEARCH.md Validation Architecture / Phase Requirements to Test Map

**conftest.py pattern:**
```python
# tests/sports_science/conftest.py
import pytest

@pytest.fixture
def sample_ftp():
    return 200.0

@pytest.fixture
def flat_power_array():
    """1 Hz data, 3600 samples (1 hour), constant 150W."""
    return [150.0] * 3600

@pytest.fixture
def variable_power_array():
    """1 Hz data with coasting zeros and peaks — tests NP > AP."""
    return [0.0] * 300 + [250.0] * 300  # alternating coasting and effort

@pytest.fixture
def sample_quality_efforts():
    """4 efforts spanning 3-20 minute range for CP model."""
    return [
        {"duration_secs": 1200, "mean_power_watts": 210},
        {"duration_secs": 600,  "mean_power_watts": 240},
        {"duration_secs": 300,  "mean_power_watts": 270},
        {"duration_secs": 180,  "mean_power_watts": 290},
    ]
```

**pytest.ini pattern (Wave 0 required):**
```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

**Import boundary test (TRUST-01):**
```python
# tests/sports_science/test_import_boundary.py
import subprocess

def test_sports_science_has_zero_anthropic_imports():
    """TRUST-01: sports_science/ must never import from anthropic SDK."""
    result = subprocess.run(
        ["grep", "-r", "anthropic", "sports_science/"],
        capture_output=True, text=True
    )
    # grep returncode 1 = no matches = test passes
    assert result.returncode != 0, (
        f"Found anthropic import in sports_science/:\n{result.stdout}"
    )
```

**Parametrize pattern for zone boundary tests (Pitfall 4):**
```python
# tests/sports_science/test_zones.py
import pytest
from sports_science import calculate_power_zones

@pytest.mark.parametrize("ftp,power,expected_zone", [
    (200, 100, 1),   # 50% FTP -> Z1
    (200, 110, 2),   # 55% FTP -> Z2 (not Z1)
    (200, 150, 2),   # 75% FTP -> Z2 (boundary: upper is exclusive)
    (200, 151, 3),   # 75.5% FTP -> Z3
])
def test_zone_boundary_no_overlap(ftp, power, expected_zone):
    ...
```

---

## Shared Patterns

### ToolResult Return Contract
**Source:** RESEARCH.md Pattern 1 / D-01
**Apply to:** All 8 public functions in `sports_science/`

Every public function returns a `ToolResult(value, unit, methodology, inputs)`. Never return a raw dict or primitive. This contract is what Phase 2's agent tool registry parses.

### Import Boundary Enforcement
**Source:** RESEARCH.md Pattern 6 / TRUST-01
**Apply to:** Every `.py` file in `sports_science/`

Zero Anthropic SDK imports. Enforced by `tests/sports_science/test_import_boundary.py` as part of the standard test run. CI must run `pytest tests/sports_science/test_import_boundary.py` as a gating check.

### Constants Over Magic Numbers
**Source:** D-05, D-10
**Apply to:** `metrics.py`, `pmc.py`, `ftp.py`, `load.py`

Import from `constants.py` only. Never hardcode `42`, `7`, `28`, `600`, `0.85`, `3.0`, or zone boundary multipliers inline.

### Pydantic v2 API
**Source:** RESEARCH.md State of the Art
**Apply to:** `types.py` and any future model files

Use `model_config = {}` dict syntax (not `class Config:`). Use `.model_dump()` not `.dict()`. Use `model_validate()` not `parse_obj()`.

### Service Role Key for Backend DB Writes
**Source:** RESEARCH.md Pitfall 6 / Pattern 5
**Apply to:** `capability_gap.py` and any future backend DB writes

Use `SUPABASE_SERVICE_ROLE_KEY` for all backend inserts. Never use the anon key for server-side writes that need to bypass RLS. Never expose service role key to frontend code.

---

## No Analog Found

All 25 files have no existing analog — this is a greenfield project. Planner must use RESEARCH.md patterns exclusively (reproduced above).

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| All 25 files | various | various | No existing source code in repo — Phase 1 establishes all foundational patterns |

---

## Metadata

**Analog search scope:** Full repo (`/Users/christianmoore/ai/pacer-ai`) — confirmed zero `.py` or `.ts` source files outside `.planning/` and `.claude/`
**Files scanned:** 0 source files (greenfield confirmed via `find`)
**Pattern extraction date:** 2026-06-19
**Pattern source:** RESEARCH.md code examples + locked decisions (CONTEXT.md D-01 through D-10)
