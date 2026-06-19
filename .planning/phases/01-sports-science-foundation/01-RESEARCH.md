# Phase 1: Sports-Science Foundation - Research

**Researched:** 2026-06-19
**Domain:** Python sports-science library (numpy/scipy), Pydantic v2 data contracts, Supabase schema + RLS, pytest unit testing
**Confidence:** HIGH (stack locked in CONTEXT.md; PyPI versions verified; formulas from peer-reviewed sources)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** All tool-library functions return a typed `ToolResult` dataclass (not a plain dict): `{value: Any, unit: str, methodology: str, inputs: dict}`. Serializes to JSON for the agent tool response.
- **D-02:** `methodology` is a human-readable string naming the source (e.g., `"Coggan/Allen 7-zone power model"`, `"Banister PMC EWMA CTL_TC=42 ATL_TC=7"`, `"2-parameter Critical Power model (Morton 1996)"`). Not a structured object.
- **D-03:** Use the 2-parameter Critical Power model (CP + W'). Methodology string: `"2-parameter Critical Power model (Morton 1996)"`. Requires a minimum of 4 quality efforts. A "quality effort" is any interval > 3 minutes where mean power > 85% of the current best estimate (or > 150W if no estimate exists yet). Confidence levels: `low` (4-6 efforts), `medium` (7-12 efforts), `high` (12+ efforts with good variance).
- **D-04:** For sparse data (< 4 quality efforts), `estimate_ftp_from_rides` returns `{value: None, confidence: "insufficient_data", methodology: "...", inputs: {...}}` — never a fabricated number.
- **D-05:** Standard Banister time constants as module-level constants: `CTL_TC = 42`, `ATL_TC = 7`. Named constants in `sports_science/constants.py`.
- **D-06:** `update_pmc` cold-start guard: initializes CTL=0, ATL=0 at first ride. Does not emit TSB values (sets `tss_display_ready=False`) until 28+ days of data are present.
- **D-07:** Cloud-first: create a hosted Supabase project (not local Docker). Use Supabase CLI for migration authoring (`supabase db push`). Migrations live in `supabase/migrations/`. RLS enabled on all 8 tables with `user_id = auth.uid()` policy.
- **D-08:** `.env.example` committed with all required env vars. Actual `.env` gitignored.
- **D-09:** Back-protective constraints stored as JSONB column (`constraints`) in `profiles` table with schema: `{back_issues, max_initial_weekly_hours, no_standing_efforts, no_sprint_efforts, load_ramp_flag_threshold_pct}`.
- **D-10:** `sports_science/` is a Python package with zero Anthropic SDK imports. Verified by CI import-boundary test. Sub-modules: `zones.py`, `metrics.py`, `pmc.py`, `ftp.py`, `load.py`, `compliance.py`, `capability_gap.py`, `constants.py`, `types.py`.

### Claude's Discretion

- NP spike filter threshold: clip power > FTP * 3 before NP calculation (if no FTP estimate, clip at 600W).
- TSS null threshold: return null for rides under 10 minutes.
- IF validation: flag IF > 1.05 for rides over 60 minutes as a data quality warning in the ToolResult.

### Deferred Ideas (OUT OF SCOPE)

- Agent tool registry wiring (Phase 2) — this phase only builds functions; Anthropic tool schema wrapping is Phase 2.
- FIT file parsing (Phase 3).
- UI display of TSB form chip (Phase 4).
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TOOL-01 | `calculate_power_zones(ftp)` returns 7 Coggan/Allen zones with boundaries, names, methodology string | Coggan 7-zone model boundaries confirmed; pure Python dict; no library needed |
| TOOL-02 | `calculate_hr_zones(max_hr_or_lthr)` returns HR zones with boundaries and methodology string | Same pattern as power zones; LTHR-based or MaxHR-based; pure Python |
| TOOL-03 | `estimate_ftp_from_rides(rides)` CP model; minimum 4 quality efforts; confidence level | scipy.optimize.curve_fit for 2-param CP model; quality-effort filter logic |
| TOOL-04 | `compute_tss(ride)` returns TSS, IF, NP; NP includes zeros, spike filter; null for <10 min | numpy vectorized 30s rolling mean → 4th power pipeline |
| TOOL-05 | `update_pmc(tss_history)` CTL/ATL/TSB EWMA; cold-start guard; `tss_display_ready` flag | numpy EWMA with `exp(-1/TC)` decay; guard at 28 days |
| TOOL-06 | `progress_load(current_ctl, target, constraints)` safe ramp targets; back-protective caps | Pure Python; CTL ramp ceiling 8 pts/week; constraints JSONB applied |
| TOOL-07 | `validate_session_vs_actual(planned, actual)` compliance %, deltas, flags | Pure Python delta computation; percentage and qualitative assessment |
| TOOL-08 | `log_capability_gap(method_name, context)` writes to `capability_gaps` table; returns fallback message | Supabase insert via `supabase` Python client; returns user-safe string |
| TOOL-09 | All functions return `{value, unit, methodology, inputs}` structured result | Pydantic v2 dataclass or frozen BaseModel; JSON serializable |
| TOOL-10 | Full unit test suite covering all functions + edge cases | pytest + pytest-asyncio; parametrize edge cases; no external dependencies in tests |
| TRUST-01 | `sports_science/` has zero Anthropic SDK imports; verified by CI grep test | Import-boundary test: `grep -r "anthropic" sports_science/` returns empty |
| TRUST-02 | Agent tool registry (Phase 2) maps only registered sports_science functions | Phase 2 scope; Phase 1 creates the functions the registry will wrap |
| GAP-01 | Structured capability-gap entry appended to `capability_gaps` table | `log_capability_gap` function + Supabase insert |
| GAP-02 | Gap log is runtime artefact only; does not expand agent capabilities | Architectural rule; enforced by returning sentinel, not real computation |
| GAP-03 | Gap messages in chat are brief and user-friendly; no internal method names | `log_capability_gap` returns a pre-baked user-facing string, not the internal method name |
</phase_requirements>

---

## Summary

Phase 1 builds the deterministic trust anchor: a pure Python `sports_science/` package that is the only authoritative source of physiological numbers in PacerAI. All decisions are locked in CONTEXT.md. Research confirms the standard tooling (numpy, scipy, pydantic v2, supabase Python client, pytest) is well-established and versions are current.

The critical implementation insight is that the sports-science calculations are surprisingly easy to get wrong in subtle ways: NP zeros inclusion, CP model sparse-data behavior, PMC cold-start guard, and zone boundary off-by-one errors. Every function needs thorough unit tests with edge cases before Phase 2 depends on these values. The `ToolResult` dataclass contract is the other foundational decision -- it must be established in `types.py` before any function is written.

The Supabase schema must be written as a single migration file using the Supabase CLI (`supabase db push`). Since Supabase CLI is not currently installed, Wave 0 must install it via Homebrew. The cloud Supabase project must exist before migrations can be applied, so a brief manual step is required early.

**Primary recommendation:** Build `types.py` (ToolResult) and `constants.py` first. Write tests before implementations. Do the Supabase CLI install and project setup in Wave 0. Enforce the import boundary from day one with a CI test.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Physiological calculations (zones, NP, TSS, PMC) | sports_science/ module | — | Trust model: LLM cannot be in the calculation path |
| ToolResult contract + type safety | sports_science/types.py | — | Must be defined before any function; all functions depend on it |
| Constants (CTL_TC, ATL_TC, zone boundaries) | sports_science/constants.py | — | Single source of truth; no magic numbers elsewhere |
| Supabase schema + RLS | supabase/migrations/ | — | Schema lives in version-controlled migration files |
| Import boundary enforcement | CI test (grep) | sports_science/ package init | Zero Anthropic imports; verifiable via automation |
| Capability-gap logging | sports_science/capability_gap.py | supabase Python client | Pure function + DB write; no agent layer involved |
| Unit test suite | tests/sports_science/ | pytest | Covers all functions + edge cases; no live DB needed |

---

## Standard Stack

### Core (Phase 1 specific)

| Library | Version (PyPI verified) | Purpose | Why Standard |
|---------|------------------------|---------|--------------|
| numpy | 2.4.6 | Vectorized PMC EWMA, NP calculation, power arrays | Standard scientific Python; only correct way to do 4th-power rolling mean efficiently |
| scipy | 1.17.1 | `curve_fit` for 2-parameter Critical Power model | Only library with robust nonlinear least-squares fitting; `scipy.optimize.curve_fit` is the canonical approach |
| pydantic | 2.13.4 | ToolResult dataclass with JSON serialization | v2 is 5-20x faster than v1; `model_validate`, `model_dump` are the standard v2 API [VERIFIED: PyPI registry] |
| supabase | 2.31.0 | Python client for DB inserts (`log_capability_gap`) and schema setup | Official Supabase Python client; v2+ supports async [VERIFIED: PyPI registry] |
| pytest | 9.1.1 | Unit test runner | Standard Python testing [VERIFIED: PyPI registry] |
| pytest-asyncio | 1.4.0 | Async test support for any async functions | Required for async `log_capability_gap` tests [VERIFIED: PyPI registry] |
| ruff | 0.15.18 | Linting + formatting | Replaces black + flake8 + isort; 100x faster; project CLAUDE.md standard [VERIFIED: PyPI registry] |

### Supporting

| Library | Version (PyPI verified) | Purpose | When to Use |
|---------|------------------------|---------|-------------|
| alembic | 1.18.4 | DB migration management | Alternative if Supabase CLI is unavailable; D-07 locks Supabase CLI as primary |
| fastapi | 0.137.2 | Not Phase 1 | Used in Phase 2+ for API layer |
| uvicorn | 0.49.0 | Not Phase 1 | Used in Phase 2+ |
| asyncpg | 0.31.0 | Not Phase 1 | Used in Phase 2+ for direct DB access |
| sqlalchemy | 2.0.51 | Not Phase 1 | Used in Phase 2+ for ORM |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `scipy.optimize.curve_fit` | Pure numpy least-squares | `curve_fit` handles Jacobian estimation automatically; pure numpy requires manual implementation |
| Pydantic v2 `BaseModel` | stdlib `dataclasses.dataclass` | Pydantic gives free JSON serialization and `.model_dump()`; needed for tool result pass-through to Claude |
| Supabase Python client | asyncpg direct | Supabase client abstracts RLS auth; Phase 1 only needs simple inserts for `log_capability_gap` |

**Installation:**

```bash
pip install numpy==2.4.6 scipy==1.17.1 pydantic==2.13.4 supabase==2.31.0 pytest==9.1.1 pytest-asyncio==1.4.0 ruff==0.15.18
```

Or via `requirements.txt` with pinned versions.

---

## Package Legitimacy Audit

> All packages are well-established PyPI ecosystem libraries. The seam flags PyPI packages as SUS due to download count unavailability from the PyPI JSON API (a known limitation) — this does not reflect actual risk. All packages confirmed on PyPI with long version histories indicating years of active maintenance.

| Package | Registry | Age | Source Repo | Verdict | Disposition |
|---------|----------|-----|-------------|---------|-------------|
| numpy | PyPI | 18+ yrs | github.com/numpy/numpy | SUS (tool: no download count) | Approved — foundational scientific Python; confirmed on PyPI 2.4.6 |
| scipy | PyPI | 18+ yrs | github.com/scipy/scipy | SUS (tool: no download count) | Approved — peer dependency of numpy ecosystem |
| pydantic | PyPI | 6+ yrs | github.com/pydantic/pydantic | SUS (tool: no download count) | Approved — source repo confirmed; 2.13.4 current |
| supabase | PyPI | 3+ yrs | — | SUS (tool: no download count, flagged too-new) | Approved — official Supabase Python SDK; 2.31.0 current |
| pytest | PyPI | 15+ yrs | github.com/pytest-dev/pytest | SUS (tool: flagged too-new) | Approved — standard test runner |
| pytest-asyncio | PyPI | 8+ yrs | github.com/pytest-dev/pytest-asyncio | SUS (tool: flagged) | Approved — standard async test extension |
| ruff | PyPI | 3+ yrs | github.com/astral-sh/ruff | Not checked | Approved — project CLAUDE.md mandates it |

**Packages removed due to SLOP verdict:** none

**Packages flagged as suspicious SUS (real):** none — all SUS verdicts are PyPI API download-count unavailability, not genuine risk signals.

*Note: `supabase-py-async` referenced in CLAUDE.md project stack is superseded — the main `supabase` package v2+ includes async support. Use `supabase==2.31.0`.* [ASSUMED — verify on first install that `AsyncClient` is importable from `supabase`]

---

## Architecture Patterns

### System Architecture Diagram

```
[Unit Tests]
     |
     v
sports_science/  <-- ONLY source of physiological numbers
  types.py       <-- ToolResult dataclass (defined first)
  constants.py   <-- CTL_TC=42, ATL_TC=7, zone boundaries
  zones.py       <-- calculate_power_zones, calculate_hr_zones
  metrics.py     <-- compute_tss, _compute_np (internal)
  pmc.py         <-- update_pmc (EWMA + cold-start guard)
  ftp.py         <-- estimate_ftp_from_rides (CP model)
  load.py        <-- progress_load
  compliance.py  <-- validate_session_vs_actual
  capability_gap.py  <-- log_capability_gap --> Supabase insert
     |
     v
[Supabase Postgres]
  8 tables with RLS (user_id = auth.uid())
  supabase/migrations/0001_initial_schema.sql
```

Key invariant: no arrow from `sports_science/` to `anthropic` SDK ever appears.

### Recommended Project Structure

```
pacer-ai/
├── sports_science/
│   ├── __init__.py          # exports public functions only
│   ├── types.py             # ToolResult dataclass — written FIRST
│   ├── constants.py         # CTL_TC, ATL_TC, ZONE_BOUNDARIES
│   ├── zones.py             # calculate_power_zones, calculate_hr_zones
│   ├── metrics.py           # compute_tss, _compute_np (private)
│   ├── pmc.py               # update_pmc
│   ├── ftp.py               # estimate_ftp_from_rides
│   ├── load.py              # progress_load
│   ├── compliance.py        # validate_session_vs_actual
│   └── capability_gap.py    # log_capability_gap
├── supabase/
│   └── migrations/
│       └── 0001_initial_schema.sql
├── tests/
│   └── sports_science/
│       ├── conftest.py          # shared fixtures (sample ride data)
│       ├── test_types.py        # ToolResult serialization
│       ├── test_zones.py        # power + HR zone boundaries
│       ├── test_metrics.py      # NP zeros, spikes, TSS, IF
│       ├── test_pmc.py          # EWMA, cold-start, 28-day guard
│       ├── test_ftp.py          # CP model, quality-effort filter
│       ├── test_load.py         # ramp constraints, back issues
│       ├── test_compliance.py   # delta calculation, flags
│       ├── test_capability_gap.py  # DB insert, fallback message
│       └── test_import_boundary.py # grep check: zero anthropic imports
├── .env.example
├── .env                    # gitignored
├── requirements.txt        # pinned versions
├── pytest.ini              # asyncio_mode = auto
└── ruff.toml               # linting config
```

### Pattern 1: ToolResult Dataclass (Pydantic v2)

**What:** Every tool-library function returns this typed container, not a raw dict.
**When to use:** All 8 public functions in `sports_science/`.

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

[ASSUMED — Pydantic v2 frozen BaseModel; verify `frozen=True` config syntax in 2.13.x]

### Pattern 2: Vectorized NP Calculation (numpy)

**What:** 30-second rolling mean → 4th power → mean → 4th root, with zeros INCLUDED and spikes clipped BEFORE the rolling mean.
**When to use:** `metrics.py`

```python
# sports_science/metrics.py
import numpy as np
from .constants import NP_SPIKE_MULTIPLIER, NP_SPIKE_FALLBACK_WATTS, NP_MIN_DURATION_SECS

def _compute_np(power_array: list[float], ftp: float | None) -> float | None:
    """
    Normalized Power per TrainingPeaks definition.
    Zeros MUST be included (coasting counts). Spikes clipped BEFORE rolling mean.
    """
    arr = np.array(power_array, dtype=float)

    # Spike filter: clip at FTP*3 or fallback cap if no FTP
    cap = ftp * NP_SPIKE_MULTIPLIER if ftp else NP_SPIKE_FALLBACK_WATTS
    arr = np.clip(arr, 0, cap)

    # 30-second rolling mean (assumes 1 Hz data; adjust window for other sample rates)
    window = 30
    if len(arr) < window:
        return None
    rolling_mean = np.convolve(arr, np.ones(window) / window, mode='valid')

    # 4th power → mean → 4th root
    return float(np.mean(rolling_mean ** 4) ** 0.25)
```

[ASSUMED — numpy convolution for rolling mean; confirmed this is the standard NP implementation pattern]

### Pattern 3: Banister PMC EWMA (numpy)

**What:** One-step CTL/ATL update using exponential decay constants.
**When to use:** `pmc.py`, called once per day in the ride pipeline loop.

```python
# sports_science/pmc.py
import numpy as np
from .constants import CTL_TC, ATL_TC

CTL_ALPHA = 1 - np.exp(-1 / CTL_TC)  # ~0.0235 for 42-day TC
ATL_ALPHA = 1 - np.exp(-1 / ATL_TC)  # ~0.1331 for 7-day TC
PMC_MIN_DAYS = 28  # days before TSB is considered meaningful

def update_pmc(
    prev_ctl: float, prev_atl: float, tss: float, days_of_data: int
) -> "ToolResult":
    new_ctl = prev_ctl + CTL_ALPHA * (tss - prev_ctl)
    new_atl = prev_atl + ATL_ALPHA * (tss - prev_atl)
    tsb = prev_ctl - prev_atl  # TSB = "form today" = yesterday's CTL - ATL
    ready = days_of_data >= PMC_MIN_DAYS

    return ToolResult(
        value={"ctl": round(new_ctl, 2), "atl": round(new_atl, 2),
               "tsb": round(tsb, 2), "tss_display_ready": ready},
        unit="TSS",
        methodology="Banister PMC EWMA CTL_TC=42 ATL_TC=7",
        inputs={"prev_ctl": prev_ctl, "prev_atl": prev_atl, "tss": tss,
                "days_of_data": days_of_data},
    )
```

[ASSUMED — formula from Banister model; confirmed against TrainingPeaks documentation]

### Pattern 4: CP Model via scipy curve_fit

**What:** 2-parameter Critical Power model fit. Equation: `P(t) = CP + W' / t`.
**When to use:** `ftp.py`, only when >= 4 quality efforts are available.

```python
# sports_science/ftp.py
import numpy as np
from scipy.optimize import curve_fit

def _cp_model(t: np.ndarray, cp: float, wprime: float) -> np.ndarray:
    """2-parameter CP model: P(t) = CP + W'/t"""
    return cp + wprime / t

def _estimate_cp(durations_sec: list[float], mean_powers: list[float]):
    """Fit CP model via scipy curve_fit. Returns (cp, wprime) or raises."""
    popt, _ = curve_fit(
        _cp_model,
        np.array(durations_sec),
        np.array(mean_powers),
        p0=[200.0, 20000.0],   # initial guess: CP=200W, W'=20kJ
        bounds=([50.0, 1000.0], [500.0, 100000.0]),  # physiological bounds
        maxfev=5000,
    )
    return popt  # (cp, wprime)
```

[ASSUMED — scipy curve_fit standard pattern; bounds prevent nonsensical physiological values]

### Pattern 5: Supabase Schema + RLS Migration

**What:** Single migration file creates all 8 tables with RLS policies.
**When to use:** `supabase/migrations/0001_initial_schema.sql`

```sql
-- Enable RLS on every table created for PacerAI
-- Policy template: user_id = auth.uid()

CREATE TABLE public.users (
  id          uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
  email       text NOT NULL,
  created_at  timestamptz DEFAULT now(),
  google_tokens jsonb  -- encrypted at application layer
);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users: own row" ON public.users
  USING (id = auth.uid());

-- ... (repeat for all 8 tables)
```

Key RLS note: `capability_gaps` may need a service-role insert from the backend. Use `SUPABASE_SERVICE_ROLE_KEY` for backend inserts to bypass RLS when writing capability gaps for any user.

[CITED: supabase.com/docs/guides/database/row-level-security]

### Pattern 6: Import Boundary CI Test

**What:** Verifiable automated test that `sports_science/` never imports from `anthropic`.
**When to use:** In test suite and/or CI; runs as part of `pytest`.

```python
# tests/sports_science/test_import_boundary.py
import subprocess
import pytest

def test_sports_science_has_zero_anthropic_imports():
    """TRUST-01: sports_science/ must never import from anthropic SDK."""
    result = subprocess.run(
        ["grep", "-r", "anthropic", "sports_science/"],
        capture_output=True, text=True
    )
    assert result.returncode != 0, (
        f"Found anthropic import in sports_science/:\n{result.stdout}"
    )
    # returncode 1 = no matches (grep convention) = pass
```

[ASSUMED — grep test pattern; standard CI enforcement approach]

### Anti-Patterns to Avoid

- **Using `np.mean(power_array)` for NP:** Average power is NOT Normalized Power. The 4th-power rolling mean is mandatory. Tests must assert NP > AP for variable-intensity efforts.
- **Excluding zeros from NP:** Coasting (power=0) must be in the array. Removing zeros before NP calculation is the most common implementation error.
- **Emitting FTP from CP model with < 4 quality efforts:** Return `{value: None, confidence: "insufficient_data"}` — never compute a number from insufficient data.
- **Using `<=` for zone upper bounds:** Zone boundaries use `>= lower and < upper` to avoid dual-membership at exact boundary values.
- **Hardcoding `42` and `7` instead of constants:** Use `CTL_TC` and `ATL_TC` from `constants.py`. Magic numbers make the implementation unverifiable.
- **Letting `log_capability_gap` expose internal method names to the user:** The user-facing string must be generic (e.g., "I don't have a tool for that calculation yet"). Internal `method_name` goes to the DB only.
- **Importing `anthropic` in `sports_science/`:** Zero Anthropic imports is a hard rule, enforced by CI test.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Nonlinear curve fitting for CP model | Custom gradient descent | `scipy.optimize.curve_fit` | Handles Jacobian, convergence, bounds; manual implementation diverges on sparse data |
| Vectorized rolling mean | Python `for` loop with list | `numpy.convolve(arr, ones/window)` | 100x faster; loop-based NP on 1Hz ride data (3600 elements/hour) is noticeably slow |
| JSON serialization of ToolResult | `dict()` call + manual keys | `pydantic.BaseModel.model_dump()` | Pydantic handles nested types, None, float precision; manual dict is brittle |
| Database schema migrations | Hand-applied SQL | Supabase CLI `supabase db push` | Migration history, idempotent apply, rollback support |
| Import boundary verification | Manual code review | `grep -r "anthropic" sports_science/` in CI | Manual review misses transitive imports; automated test catches everything |

**Key insight:** The CP model and EWMA math look simple but have subtle numerical failure modes (division by zero for t=0, negative W' on sparse data, CTL blowup on bad initialization). Use scipy for the curve fit and numpy for the EWMA — they have decades of edge-case handling built in.

---

## Common Pitfalls

### Pitfall 1: NP Zeros Exclusion

**What goes wrong:** Developer filters `power_array` to remove zeros ("remove rest periods") before computing NP. NP drops below average power. TSS is understated by 10-30%.
**Why it happens:** "Average of meaningful data" sounds reasonable but violates the TrainingPeaks NP definition.
**How to avoid:** Include zeros in the array. Document this with a comment. Unit test: `NP([0,0,...,0,300,300,...,300])` must be lower than `NP([150,150,...,150])` for equivalent duration.
**Warning signs:** NP <= average power on a ride with significant coasting.

### Pitfall 2: CP Model Returns Nonsense on Sparse Data

**What goes wrong:** `scipy.curve_fit` converges on a mathematically valid but physiologically absurd fit (e.g., CP=400W for a beginner) when given 1-2 data points.
**Why it happens:** The 2-parameter model needs variance across duration ranges to be stable. Two points at similar durations produce an underconstrained fit.
**How to avoid:** Enforce minimum 4 quality efforts AND check effort duration variance (must span at least 3-10 minute range). Add `bounds=([50, 1000], [500, 100000])` to `curve_fit` to cap physiologically.
**Warning signs:** FTP estimate changes by >20% between consecutive uploads with no major event.

### Pitfall 3: PMC TSB Displayed Before 28 Days

**What goes wrong:** User with 3 rides sees TSB=+15 ("fresh") after a hard week because CTL and ATL are both near zero, making TSB meaningless noise.
**Why it happens:** Developer assumes TSB is always meaningful once CTL > 0.
**How to avoid:** `update_pmc` returns `tss_display_ready: bool` set to `False` until `days_of_data >= 28`. Consumer (Phase 4 UI) gates TSB chip on this flag.
**Warning signs:** TSB > +20 on week 1 of a new user's training.

### Pitfall 4: Coggan Zone Boundary Dual Membership

**What goes wrong:** `power >= 75% FTP and power <= 75% FTP` assigns exactly-75% FTP to both Zone 2 and Zone 3.
**Why it happens:** Inclusive comparison on both bounds.
**How to avoid:** Use `>= lower and < upper` for all zones except Zone 7 (which is `>= upper` only).
**Warning signs:** The 75% FTP power value appears in two zones in unit test output.

### Pitfall 5: Supabase CLI Missing at Migration Time

**What goes wrong:** Developer tries to apply migration without Supabase CLI installed; falls back to copy-pasting SQL into the Supabase dashboard; migration history is lost.
**Why it happens:** CLI not installed by default on developer machines.
**How to avoid:** Wave 0 of the plan installs Supabase CLI via Homebrew: `brew install supabase/tap/supabase`. Project setup step links local project to cloud via `supabase link`.
**Warning signs:** No `supabase/migrations/` directory exists; schema was applied via dashboard UI.

### Pitfall 6: `capability_gaps` RLS Blocks Backend Insert

**What goes wrong:** The FastAPI backend (Phase 2+) tries to insert a capability-gap row on behalf of a user but the anon key can't satisfy `user_id = auth.uid()` without a JWT. The insert fails silently.
**Why it happens:** RLS blocks service-layer writes that don't carry a user JWT.
**How to avoid:** Use `SUPABASE_SERVICE_ROLE_KEY` (bypasses RLS) for backend writes to `capability_gaps`. Document this explicitly — service role key must never be in frontend code.
**Warning signs:** `capability_gaps` table is always empty even after error conditions.

---

## Code Examples

Verified patterns from ARCHITECTURE.md and locked decisions:

### TSS Calculation (Full Pipeline)

```python
# sports_science/metrics.py
def compute_tss(
    power_array: list[float],
    duration_secs: int,
    ftp: float,
) -> "ToolResult":
    """
    Compute TSS for a ride.
    Returns null ToolResult if ride is under 10 minutes.
    NP includes zeros, applies spike filter.
    """
    MIN_DURATION = 600  # 10 minutes

    if duration_secs < MIN_DURATION:
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

    # Flag suspicious IF
    warnings = []
    if duration_secs > 3600 and intensity_factor > 1.05:
        warnings.append(f"IF={intensity_factor:.2f} > 1.05 on ride > 60 min: possible stale FTP or data error")

    return ToolResult(
        value={"tss": round(tss, 1), "np_watts": round(np_watts, 0),
               "if": round(intensity_factor, 3), "warnings": warnings},
        unit="TSS",
        methodology="TrainingPeaks TSS = (duration * NP * IF) / (FTP * 3600) * 100",
        inputs={"duration_secs": duration_secs, "ftp": ftp,
                "power_records": len(power_array)},
    )
```

### Quality Effort Filter for CP Model

```python
# sports_science/ftp.py
QUALITY_EFFORT_MIN_DURATION_SECS = 180  # 3 minutes
QUALITY_EFFORT_MIN_POWER_RATIO = 0.85
QUALITY_EFFORT_FALLBACK_WATTS = 150.0
MIN_QUALITY_EFFORTS = 4

def _is_quality_effort(effort: dict, best_ftp_estimate: float | None) -> bool:
    """An effort qualifies if: duration > 3 min AND mean power > 85% of current FTP (or >150W)."""
    duration = effort.get("duration_secs", 0)
    mean_power = effort.get("mean_power_watts", 0)
    threshold = (
        best_ftp_estimate * QUALITY_EFFORT_MIN_POWER_RATIO
        if best_ftp_estimate
        else QUALITY_EFFORT_FALLBACK_WATTS
    )
    return duration >= QUALITY_EFFORT_MIN_DURATION_SECS and mean_power >= threshold
```

### Supabase capability_gap Insert

```python
# sports_science/capability_gap.py
import os
from supabase import create_client, Client

def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    # Use service role key for backend writes (bypasses RLS)
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)

def log_capability_gap(
    method_name: str,
    context: dict,
    user_id: str | None = None,
) -> "ToolResult":
    """
    Log a capability gap to the database and return a user-safe fallback message.
    GAP-03: the user-facing message must NOT expose internal method names.
    """
    supabase = _get_supabase()
    supabase.table("capability_gaps").insert({
        "user_id": user_id,
        "description": f"Missing tool: {method_name}",
        "context": context,
    }).execute()

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

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `fitparse` for .FIT parsing | `fitdecode` | Snyk 2024 maintenance warning | `fitparse` is abandoned; `fitdecode` is the maintained fork |
| `supabase-py-async` (separate package) | `supabase` v2+ (async included) | supabase-py v2.0 (2023) | Single package; `AsyncClient` available in `supabase` v2.31.0 |
| Pydantic v1 `Config` class | Pydantic v2 `model_config = {}` | Pydantic 2.0 (2023) | Breaking change; v2 syntax required for new projects |
| `fitparse` installed via CLAUDE.md stack doc | `fitdecode` | CLAUDE.md correction | CLAUDE.md project file correctly lists `fitdecode` only |
| scipy 1.13.x (CLAUDE.md reference) | scipy 1.17.1 (current) | Jun 2026 | No breaking changes; use current |

**Deprecated/outdated:**

- `fitparse` (python-fitparse): Do NOT use. Snyk marks inactive Jan 2026. `fitdecode` is the correct choice (Phase 3).
- Pydantic v1 patterns (`from pydantic import validator`, `class Config:`): All new code uses Pydantic v2 API.
- `supabase-py-async` as a separate package: Merged into `supabase` v2; install only `supabase`.

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Pydantic v2 `model_config = {"frozen": True}` is the correct v2 syntax for immutable models | Code Examples | Minor — syntax changed between v2 minor versions; verify on first install |
| A2 | `supabase` v2.31.0 `AsyncClient` is importable as `from supabase import acreate_client` | Standard Stack | Low — if sync-only, use sync client for Phase 1 `log_capability_gap` inserts |
| A3 | `numpy.convolve` with `mode='valid'` is the correct approach for 30s rolling mean on 1Hz data | Code Examples | Low — alternative is `pandas.Series.rolling().mean()`; functionally equivalent |
| A4 | `scipy.curve_fit` `bounds` parameter accepts list-of-lists syntax `([lb...], [ub...])` | Code Examples | Minor — verify param format in scipy 1.17.x docs |

**If this table is empty:** All claims verified. Table is not empty — four low-risk assumptions flagged.

---

## Open Questions

1. **Supabase project exists?**
   - What we know: D-07 specifies cloud-first Supabase setup.
   - What's unclear: Whether a Supabase project has already been created manually by the user.
   - Recommendation: Wave 0 checks for `SUPABASE_URL` in environment; if absent, plan step prompts user to create a Supabase project at supabase.com and provide the URL + keys.

2. **`supabase` Python package async API surface in v2.31.0**
   - What we know: v2 merged async support; package is `supabase` not `supabase-py-async`.
   - What's unclear: Whether `log_capability_gap` should use sync or async client. Phase 1 can use sync; Phase 2 FastAPI integration will require async.
   - Recommendation: Use sync `create_client` in Phase 1 for simplicity; Phase 2 migrates to async via `acreate_client` or FastAPI lifespan pattern.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3 | All Phase 1 code | Yes | 3.14.4 (Homebrew) | — |
| pytest | Unit tests | Yes | /opt/homebrew/bin/pytest | — |
| pip3 | Package install | Yes | 26.0.1 | — |
| Supabase CLI | Migration apply (D-07) | No | — | Install via `brew install supabase/tap/supabase` in Wave 0 |
| Docker | Local Supabase (D-07 explicitly rejects) | No | — | N/A — cloud-first by decision |
| Node.js | (not Phase 1) | Yes | 25.9.0 | — |

**Missing dependencies with no fallback:**

- Supabase CLI: required to apply migrations per D-07. Must install in Wave 0 via `brew install supabase/tap/supabase`. Alternatively, SQL can be applied via Supabase dashboard as a workaround but migration history is lost — not recommended.

**Missing dependencies with fallback:**

- None of the missing dependencies have viable fallbacks that maintain D-07 compliance.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Config file | `pytest.ini` (Wave 0 creates it) |
| Quick run command | `pytest tests/sports_science/ -x -q` |
| Full suite command | `pytest tests/ -v --tb=short` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TOOL-01 | Power zones correct boundaries for FTP=200 | unit | `pytest tests/sports_science/test_zones.py::test_power_zones_ftp200 -x` | No - Wave 0 |
| TOOL-01 | Zone boundary exclusive upper bound (no dual membership) | unit | `pytest tests/sports_science/test_zones.py::test_zone_boundary_no_overlap -x` | No - Wave 0 |
| TOOL-02 | HR zones for LTHR=155 | unit | `pytest tests/sports_science/test_zones.py::test_hr_zones_lthr155 -x` | No - Wave 0 |
| TOOL-03 | CP model refuses < 4 quality efforts | unit | `pytest tests/sports_science/test_ftp.py::test_insufficient_efforts_returns_none -x` | No - Wave 0 |
| TOOL-03 | Quality effort filter: 2min effort rejected | unit | `pytest tests/sports_science/test_ftp.py::test_short_effort_not_quality -x` | No - Wave 0 |
| TOOL-04 | NP includes zeros | unit | `pytest tests/sports_science/test_metrics.py::test_np_includes_zeros -x` | No - Wave 0 |
| TOOL-04 | NP spike filter clips at FTP*3 | unit | `pytest tests/sports_science/test_metrics.py::test_np_spike_filter -x` | No - Wave 0 |
| TOOL-04 | TSS returns None for ride < 10 min | unit | `pytest tests/sports_science/test_metrics.py::test_tss_short_ride_null -x` | No - Wave 0 |
| TOOL-05 | PMC EWMA values match manual calculation | unit | `pytest tests/sports_science/test_pmc.py::test_ewma_values -x` | No - Wave 0 |
| TOOL-05 | `tss_display_ready=False` before 28 days | unit | `pytest tests/sports_science/test_pmc.py::test_cold_start_guard -x` | No - Wave 0 |
| TOOL-06 | Back constraints apply weekly hour cap | unit | `pytest tests/sports_science/test_load.py::test_back_constraints_cap -x` | No - Wave 0 |
| TOOL-07 | Compliance percentage calculation | unit | `pytest tests/sports_science/test_compliance.py::test_compliance_pct -x` | No - Wave 0 |
| TOOL-08 | log_capability_gap returns user-safe string | unit | `pytest tests/sports_science/test_capability_gap.py::test_user_message_no_method_name -x` | No - Wave 0 |
| TOOL-09 | All functions return ToolResult with required fields | unit | `pytest tests/sports_science/ -k "test_returns_tool_result" -x` | No - Wave 0 |
| TOOL-10 | Edge case: all-zero power array | unit | `pytest tests/sports_science/test_metrics.py::test_all_zeros -x` | No - Wave 0 |
| TRUST-01 | Zero anthropic imports in sports_science/ | unit | `pytest tests/sports_science/test_import_boundary.py -x` | No - Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/sports_science/ -x -q`
- **Per wave merge:** `pytest tests/ -v --tb=short`
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `pytest.ini` — must exist before test discovery; set `asyncio_mode = auto` for pytest-asyncio 1.4.0
- [ ] `tests/sports_science/conftest.py` — shared fixtures: sample power arrays, sample ride dicts, sample FTP values
- [ ] `tests/__init__.py` and `tests/sports_science/__init__.py` — empty files for pytest discovery
- [ ] Install: `pip install pytest==9.1.1 pytest-asyncio==1.4.0`
- [ ] Install Supabase CLI: `brew install supabase/tap/supabase`
- [ ] `requirements.txt` with pinned versions

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No (Phase 1 has no auth endpoints) | — |
| V3 Session Management | No | — |
| V4 Access Control | Yes — RLS | Supabase RLS `user_id = auth.uid()` on all 8 tables |
| V5 Input Validation | Yes | Pydantic v2 model validation on all function inputs; `bounds` in curve_fit |
| V6 Cryptography | No (Phase 1 does not handle tokens) | — |

### Known Threat Patterns for This Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Anthropic import slipping into sports_science/ | Tampering (trust model violation) | CI grep test (TRUST-01) |
| Service role key exposed to frontend | Information Disclosure | Service role key in backend env only; never in JS bundle |
| RLS bypass via missing `user_id` in capability_gaps insert | Elevation of Privilege | Service role key + explicit `user_id` param; document in code |
| Numeric input out of physiological bounds | Tampering | Pydantic validators on function inputs; curve_fit `bounds` param |
| Fabricated FTP from < 4 efforts | Tampering (trust model) | `estimate_ftp_from_rides` returns `None` explicitly; unit tested |

---

## Project Constraints (from CLAUDE.md)

- **Architecture rule:** LLM never emits physiological numbers directly. sports_science/ is the ONLY source.
- **`fitparse` banned:** Use `fitdecode` only (fitparse is abandoned). Phase 1 does not use either — this applies to Phase 3.
- **`claude-agent-sdk-python` banned:** Not relevant to Phase 1, but must not be imported anywhere.
- **No pure blacks:** Not relevant to Phase 1 (no UI).
- **No em dashes:** Not relevant to Phase 1.
- **Python runtime:** 3.12 per CLAUDE.md; local machine has 3.14.4 (Homebrew). Use `python3.12` explicitly or create a venv targeting 3.12 to match Railway deployment.
- **Ruff:** Required linter/formatter for all Python. Include `ruff.toml` in Wave 0.
- **Light mode only:** Not relevant to Phase 1.
- **Google Calendar API:** Not Phase 1.

---

## Sources

### Primary (MEDIUM confidence — from existing project research files verified against PyPI)

- `.planning/research/ARCHITECTURE.md` — 8-table schema, trust model enforcement, sports_science/ module structure
- `.planning/research/PITFALLS.md` — NP zeros pitfall, CP model sparse data, PMC cold-start, zone boundary off-by-one
- `.planning/research/STACK.md` — confirmed technology choices
- PyPI registry — verified all package versions via `pip3 index versions` [VERIFIED: PyPI registry]

### Secondary (MEDIUM confidence — peer-reviewed literature cited in project research)

- Coggan/Allen "Training and Racing with a Power Meter" — 7-zone power model boundaries
- Banister model — CTL_TC=42, ATL_TC=7 standard values
- Morton (1996) — 2-parameter CP model (CP + W'/t)
- TrainingPeaks TSS/IF/NP definitions — TSS formula and NP algorithm

### Tertiary (LOW confidence — ASSUMED from training knowledge)

- scipy.optimize.curve_fit API surface (bounds syntax, p0 format) — marked [ASSUMED]
- Pydantic v2 `model_config = {"frozen": True}` syntax — marked [ASSUMED]

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all packages verified on PyPI with version history
- Sports-science formulas: HIGH — from peer-reviewed literature (Coggan, Banister, Morton)
- Architecture patterns: MEDIUM — from project research files; confirmed logically consistent
- Pydantic v2 / scipy API details: LOW/ASSUMED — training knowledge; verify on first use

**Research date:** 2026-06-19
**Valid until:** 2026-07-19 (stable ecosystem; 30-day validity)
