---
phase: 01-sports-science-foundation
reviewed: 2026-06-19T00:00:00Z
depth: standard
files_reviewed: 20
files_reviewed_list:
  - sports_science/__init__.py
  - sports_science/capability_gap.py
  - sports_science/compliance.py
  - sports_science/constants.py
  - sports_science/ftp.py
  - sports_science/load.py
  - sports_science/metrics.py
  - sports_science/pmc.py
  - sports_science/types.py
  - sports_science/zones.py
  - supabase/migrations/0001_initial_schema.sql
  - tests/sports_science/conftest.py
  - tests/sports_science/test_capability_gap.py
  - tests/sports_science/test_compliance.py
  - tests/sports_science/test_ftp.py
  - tests/sports_science/test_import_boundary.py
  - tests/sports_science/test_load.py
  - tests/sports_science/test_metrics.py
  - tests/sports_science/test_pmc.py
  - tests/sports_science/test_types.py
  - tests/sports_science/test_zones.py
findings:
  critical: 3
  warning: 7
  info: 4
  total: 14
status: issues_found
---

# Phase 01: Code Review Report

**Reviewed:** 2026-06-19
**Depth:** standard
**Files Reviewed:** 20
**Status:** issues_found

## Summary

The sports-science library is structurally sound: the tool boundary, ToolResult contract, and PMC EWMA math are correct. Three blockers require fixes before this ships. The most dangerous is an unguarded `ZeroDivisionError` in `compute_tss` when `ftp=0`; the second is an unguarded `RuntimeError` from `curve_fit` in `estimate_ftp_from_rides` that will crash the agent on bad data; the third is a missing `UNIQUE(user_id, date)` constraint in `pmc_history` that allows duplicate entries to silently corrupt the time series. All three are fixable in under 10 lines each.

---

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `compute_tss` crashes with `ZeroDivisionError` when `ftp=0`

**File:** `sports_science/metrics.py:86`

**Issue:** `intensity_factor = np_watts / ftp` performs integer division with `ftp` in the denominator. When `ftp=0` is passed and `np_watts > 0` (i.e., the ride has non-zero power), this raises `ZeroDivisionError`. The spike-filter on line 28 already handles the `ftp=0` case by falling back to `NP_SPIKE_FALLBACK_WATTS`, so `_compute_np` does not crash — but the TSS calculation does. No test covers `ftp=0` with a non-zero power array. The function signature types `ftp: float` (not `Optional`), but callers could supply 0 for a rider with no FTP yet.

**Fix:**
```python
# Guard at the top of compute_tss, before NP calculation
if ftp <= 0:
    return ToolResult(
        value=None,
        unit="TSS",
        methodology="TSS requires positive FTP; ftp=0 is not valid",
        inputs={"duration_secs": duration_secs, "ftp": ftp},
    )
```

---

### CR-02: `estimate_ftp_from_rides` raises unhandled `RuntimeError` on convergence failure

**File:** `sports_science/ftp.py:64-71`

**Issue:** `scipy.optimize.curve_fit` raises `RuntimeError` when the optimizer cannot converge within `maxfev=5000` iterations. There is no try/except around this call. With real-world FIT data, degenerate effort distributions (e.g., all efforts at nearly identical durations, or power data with systematic measurement errors) will cause the entire agent tool call to raise an unhandled exception rather than returning `value=None` with a diagnostic confidence flag. This violates the D-04 contract that the function "never fabricates a number from sparse data" — an uncaught exception is worse than a fabrication.

**Fix:**
```python
try:
    popt, _ = curve_fit(
        _cp_model,
        durations,
        mean_powers,
        p0=[200.0, 20000.0],
        bounds=([50.0, 1000.0], [500.0, 100000.0]),
        maxfev=5000,
    )
except RuntimeError:
    return ToolResult(
        value=None,
        unit="watts",
        methodology="2-parameter Critical Power model (Morton 1996) — convergence failed",
        inputs={
            "quality_efforts": len(quality_efforts),
            "required": MIN_QUALITY_EFFORTS,
            "confidence": "insufficient_data",
        },
    )
```

---

### CR-03: `pmc_history` has no `UNIQUE(user_id, date)` constraint

**File:** `supabase/migrations/0001_initial_schema.sql:88-102`

**Issue:** The `pmc_history` table stores one PMC row per user per day. There is no unique constraint on `(user_id, date)`. If the caller to `update_pmc` inserts a row for a date that already has an entry (e.g., a retry, a bug, or a re-sync), multiple rows exist for the same day. When the PMC time series is later read sequentially, duplicate dates silently corrupt CTL/ATL/TSB values because the algorithm applies EWMA steps in order. A duplicate row adds a phantom training day that inflates ATL and skews form scores.

**Fix:**
```sql
ALTER TABLE public.pmc_history
    ADD CONSTRAINT pmc_history_user_date_unique UNIQUE (user_id, date);
```
Alternatively, callers should use `INSERT ... ON CONFLICT (user_id, date) DO UPDATE` (upsert).

---

## Warnings

### WR-01: `estimate_ftp_from_rides` quality-effort filter ignores estimated FTP

**File:** `sports_science/ftp.py:46`

**Issue:** The quality-effort filter is called with `best_ftp_estimate=None` for all rides unconditionally. This means the power threshold is always `QUALITY_EFFORT_FALLBACK_WATTS` (150 W), regardless of what the data suggests the rider's FTP might be. The `_is_quality_effort` function supports a `best_ftp_estimate` argument specifically to apply a tighter `85% of FTP` filter, but that path is never exercised. A beginner with FTP ~140 W would have all efforts passing the 150 W filter with `None` but would correctly fail when the estimated FTP is used. The filter could also reject valid efforts for stronger riders if 85% of their FTP > 150 W, but that direction is safe. Consequence: the data set fed to `curve_fit` is noisier than intended.

**Fix:** Compute a preliminary FTP estimate from duration/power data, then re-filter with that estimate before the final fit. Alternatively, document that the two-pass refinement is a deliberate future enhancement.

---

### WR-02: `compute_tss` warning trigger uses `ftp` instead of `ftp` — checks `intensity_factor > 1.05` but `if` key stored as string

**File:** `sports_science/metrics.py:90-93`

**Issue:** Minor but real: the value dict stores `"if"` as the key (line 99), which is a Python reserved word and will silently collide in any context that tries to unpack this dict into keyword arguments (`**result.value`). This is legal as a dict key but pathological to use. Additionally `"if"` as a key name makes the downstream tool schema harder to express (some JSON schema validators and OpenAPI generators treat `if` as a reserved keyword in draft-7+).

**Fix:** Rename the key to `"intensity_factor"` to match the variable name and avoid the reserved-word collision:
```python
value={
    "tss": round(tss, 1),
    "np_watts": round(np_watts, 0),
    "intensity_factor": round(intensity_factor, 3),
    "warnings": warnings,
},
```

---

### WR-03: `progress_load` stalls permanently when `current_ctl=0` and `back_issues=True`

**File:** `sports_science/load.py:25-26`

**Issue:** When `current_ctl=0` and `back_issues=True`, `back_cap = 0 * ramp_threshold = 0.0`, so `max_ctl_increase = min(8.0, 0.0) = 0.0` and `recommended_ctl_target = 0.0`. A new user starting from zero CTL with back issues will always be told to train at 0 CTL — they can never begin training. This is physiologically wrong: a beginner must start somewhere. The back-protective cap is intended to limit *relative* increases, not to prevent any load at all.

**Fix:** Apply a minimum floor to `back_cap` when `current_ctl` is near zero:
```python
back_cap = max(current_ctl * ramp_threshold, 2.0)  # minimum 2 CTL pts/week floor
```

---

### WR-04: `test_import_boundary.py` silently passes when `grep` receives a non-existent path

**File:** `tests/sports_science/test_import_boundary.py:7-14`

**Issue:** The test runs `grep -r anthropic sports_science/` with a relative path. If pytest is invoked from any directory other than the project root, `grep` will exit with returncode 2 (path error), not returncode 1 (no matches). The assertion `assert result.returncode != 0` passes for both returncode 1 (correct: no imports found) and returncode 2 (incorrect: path not found — grep never ran). A misconfigured CI job would silently report this test as passing even though the import boundary was never checked.

**Fix:**
```python
import subprocess, pathlib

def test_sports_science_has_zero_anthropic_imports():
    pkg_dir = pathlib.Path(__file__).parents[2] / "sports_science"
    result = subprocess.run(
        ["grep", "-r", "--include=*.py", "anthropic", str(pkg_dir)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1, (  # 1 = no matches; 0 = found; 2 = error
        f"Unexpected grep result (rc={result.returncode}):\n{result.stdout}{result.stderr}"
    )
```

---

### WR-05: `ftp.py` docstring says `medium: 7-12` but code produces `high` at `n=12`

**File:** `sports_science/ftp.py:41`

**Issue:** The docstring states `medium: 7-12 efforts`. The code at line 83 is `elif n < 12: confidence = "medium"`, so `n=12` produces `"high"`, not `"medium"`. The boundary is off-by-one relative to the documentation. The test (`test_confidence_levels`) passes 12 efforts and expects `"high"`, so the test is aligned with the code — but the docstring is wrong and will mislead anyone relying on it to understand the confidence tiers.

**Fix:** Correct the docstring to match code behaviour:
```
medium: 7-11 efforts
high: 12+ efforts
```

---

### WR-06: `sessions` table accepts arbitrary `status` strings

**File:** `supabase/migrations/0001_initial_schema.sql:56-57`

**Issue:** `status text NOT NULL DEFAULT 'planned'` has no `CHECK` constraint. Any string (including typos like `'compelted'`) is accepted. Application-level compliance checking via `validate_session_vs_actual` relies on sessions having a known status to identify which sessions are ready for comparison. Unexpected status values will silently pass through and cause logic errors in downstream queries.

**Fix:**
```sql
status text NOT NULL DEFAULT 'planned'
    CHECK (status IN ('planned', 'completed', 'skipped', 'partial')),
```

---

### WR-07: `users.google_tokens` stores OAuth tokens unencrypted

**File:** `supabase/migrations/0001_initial_schema.sql:13`

**Issue:** The comment says "encrypted at app layer (Phase 3)" — this is a known deferred item, but the migration ships the column as raw `jsonb` with no encryption. Google OAuth refresh tokens are long-lived credentials. If the Supabase instance is compromised or a misconfigured RLS policy allows a row leak, tokens are exposed in plaintext. This is a security gap that exists in the delivered schema regardless of the future-phase comment.

**Fix:** Either encrypt the value before writing (using `pgcrypto` or application-layer encryption) now, or document this explicitly as an accepted risk with a tracking issue. The column should not ship in Phase 1 if it will store live credentials before Phase 3 encryption is in place. Consider storing `NULL` until Phase 3 and adding a `NOT NULL` constraint only after encryption is wired.

---

## Info

### IN-01: `calculate_hr_zones` parameter named `max_hr_or_lthr` but always used as LTHR

**File:** `sports_science/zones.py:31`

**Issue:** The parameter name `max_hr_or_lthr` implies the function accepts either max HR or LTHR. But the HR zone multipliers in `HR_ZONE_BOUNDARIES` (e.g., zone 4 upper = 1.00, zone 5 lower = 1.00) are calibrated for LTHR — not max HR. Passing true max HR would place zones incorrectly. The `inputs` dict stores the value as `"lthr"`, and the docstring says "LTHR", so the parameter name is the outlier.

**Fix:** Rename parameter to `lthr: float` and update the docstring accordingly.

---

### IN-02: `capability_gaps.conversation_id` has no foreign key constraint

**File:** `supabase/migrations/0001_initial_schema.sql:147`

**Issue:** `conversation_id uuid` in `capability_gaps` has no `REFERENCES public.conversations` FK. Any UUID can be stored, including deleted or never-existing conversation IDs, silently corrupting audit trails.

**Fix:**
```sql
conversation_id uuid REFERENCES public.conversations(id) ON DELETE SET NULL,
```

---

### IN-03: `rides` table has no `session_id` foreign key

**File:** `supabase/migrations/0001_initial_schema.sql:69-78`

**Issue:** There is no column linking a ride to the planned session it fulfills. `validate_session_vs_actual` accepts `planned` and `actual` as plain dicts at the Python layer, but the schema cannot enforce or query the relationship between a completed ride and its planned session. This makes "which ride fulfills which session" a purely application-level concern with no DB integrity.

**Fix:** Add `session_id uuid REFERENCES public.sessions(id) ON DELETE SET NULL` to the `rides` table.

---

### IN-04: `estimate_ftp_from_rides` silently ignores `scipy.optimize.OptimizeWarning`

**File:** `sports_science/ftp.py:64`

**Issue:** `curve_fit` emits `OptimizeWarning` when covariance estimation is unreliable (e.g., poor data spread). This is distinct from the `RuntimeError` in CR-02. The warning does not crash but indicates the fit quality is low. Currently no warning is surfaced in the `ToolResult`. A caller cannot distinguish a well-converged fit from a poorly-constrained one except by confidence tier.

**Fix:** Capture the warning with `warnings.catch_warnings` and, if raised, downgrade confidence to `"low"` regardless of effort count, or include a `"fit_warning"` key in the value dict.

---

_Reviewed: 2026-06-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
