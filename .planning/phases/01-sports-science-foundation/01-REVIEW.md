---
status: issues_found
phase: "01"
phase_name: "sports-science-foundation"
files_reviewed: 23
depth: standard
reviewed_at: "2026-06-19"
findings:
  critical: 4
  warning: 7
  info: 5
  total: 16
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
  - supabase/config.toml
  - supabase/migrations/0001_initial_schema.sql
  - tests/__init__.py
  - tests/sports_science/__init__.py
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
---

# Code Review: Phase 01 -- Sports Science Foundation

## Summary

The library is structurally sound. The tool boundary (TRUST-01/TRUST-02), ToolResult contract, PMC EWMA math, and Coggan zone boundaries are all correctly implemented. Four critical defects require fixes before any code in this package is exercised against real data or a live DB.

The most dangerous: `compute_tss` crashes with `ZeroDivisionError` on `ftp=0`; `estimate_ftp_from_rides` raises an unhandled `RuntimeError` on any `curve_fit` convergence failure; `log_capability_gap` raises `KeyError` on missing env vars instead of returning its fallback; and the `messages` RLS policy allows cross-conversation message injection. Secondary issues include the `pmc_history` duplicate-date gap, a permanently-stalled load ramp for zero-CTL back-constrained users, and the `google_tokens` column accepting plaintext OAuth tokens before encryption is wired.

---

## Findings

### CR-001: `compute_tss` crashes with `ZeroDivisionError` when `ftp=0`

**Severity:** Critical
**File:** `sports_science/metrics.py:86`

**Issue:** `intensity_factor = np_watts / ftp` divides by `ftp` with no guard. When `ftp=0` is passed (new user, FTP not yet estimated) and the power array is non-zero, this raises `ZeroDivisionError`. The spike-filter in `_compute_np` already handles `ftp=0` by falling back to `NP_SPIKE_FALLBACK_WATTS` -- but the outer `compute_tss` function does not. No test covers `ftp=0` with a non-zero power array, so this crash is completely untested.

Confirmed with: `python3 -c "ftp=0.0; np_watts=150.0; print(np_watts/ftp)"` -> `ZeroDivisionError: division by zero`.

**Fix:**
```python
# Add before the NP calculation (line 65), or before line 86 after np_watts is known:
if ftp <= 0:
    return ToolResult(
        value=None,
        unit="TSS",
        methodology="TSS requires positive FTP; ftp=0 is not valid",
        inputs={"duration_secs": duration_secs, "ftp": ftp},
    )
```

---

### CR-002: `estimate_ftp_from_rides` raises unhandled `RuntimeError` on convergence failure

**Severity:** Critical
**File:** `sports_science/ftp.py:64-71`

**Issue:** `scipy.optimize.curve_fit` raises `RuntimeError` when the optimizer cannot converge within `maxfev=5000` iterations, and `ValueError` on malformed inputs. Neither exception is caught. Real-world triggers include: all quality efforts at identical or near-identical durations (degenerate CP curve), power data with systematic sensor errors, or any data set where the 2-parameter CP model cannot be fit within the stated physiological bounds. The uncaught exception propagates through the tool layer and crashes the agent call -- violating the D-04 contract that the function never fabricates a number from sparse data (a crash is worse than a fabrication).

No test exercises a convergence-failure path.

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
except (RuntimeError, ValueError):
    return ToolResult(
        value=None,
        unit="watts",
        methodology="2-parameter Critical Power model (Morton 1996) -- convergence failed",
        inputs={
            "quality_efforts": len(quality_efforts),
            "required": MIN_QUALITY_EFFORTS,
            "confidence": "insufficient_data",
        },
    )
cp, wprime = popt
```

---

### CR-003: `log_capability_gap` raises `KeyError` on missing env vars instead of returning fallback

**Severity:** Critical
**File:** `sports_science/capability_gap.py:19-22`

**Issue:** `_get_supabase()` uses bracket access `os.environ["SUPABASE_URL"]` and `os.environ["SUPABASE_SERVICE_ROLE_KEY"]`. If either env var is absent (misconfigured deploy, CI environment without secrets loaded, test run without `.env`), this raises `KeyError` before any Supabase call. The `log_capability_gap` function is supposed to always return a `ToolResult` -- a `KeyError` violates that contract. Tests pass only because they patch `_get_supabase` at the module level and never exercise this path.

Additionally, even with valid env vars, the `supabase.table(...).insert(...).execute()` call (line 47-52) has no error handling. Any DB error (network timeout, schema mismatch, RLS violation) also crashes the function instead of returning the fallback message.

**Fix:**
```python
def _get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise EnvironmentError(
            "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
        )
    return create_client(url, key)


def log_capability_gap(method_name, context, user_id=None) -> ToolResult:
    try:
        supabase = _get_supabase()
        supabase.table("capability_gaps").insert({
            "user_id": user_id,
            "method_name": method_name,
            "description": f"Missing tool: {method_name}",
            "context": context,
        }).execute()
    except Exception:
        pass  # gap logging is best-effort; never block the fallback response

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

### CR-004: `messages` RLS allows cross-conversation message injection

**Severity:** Critical
**File:** `supabase/migrations/0001_initial_schema.sql:132-133`

**Issue:** The messages RLS policy is `USING (user_id = auth.uid())`. For INSERT, PostgreSQL applies the USING expression as the WITH CHECK when no explicit WITH CHECK is defined. This prevents a user from setting `user_id` to another user's ID -- but it does NOT prevent a user from inserting a message with their own `user_id` and a `conversation_id` that belongs to another user. The FK constraint ensures the conversation exists, but not that it belongs to the authenticated user.

Result: User B can inject messages into User A's conversation. Those messages will appear in User A's coaching context and AI message history, corrupting the coaching session.

**Fix:**
```sql
DROP POLICY "messages: own row" ON public.messages;

CREATE POLICY "messages: own row" ON public.messages
    USING (user_id = auth.uid())
    WITH CHECK (
        user_id = auth.uid()
        AND EXISTS (
            SELECT 1 FROM public.conversations c
            WHERE c.id = conversation_id
              AND c.user_id = auth.uid()
        )
    );
```

---

### WR-001: `estimate_ftp_from_rides` always passes `best_ftp_estimate=None` -- quality filter permanently degraded

**Severity:** Warning
**File:** `sports_science/ftp.py:46`

**Issue:** The quality-effort filter is always called with `best_ftp_estimate=None`, unconditionally falling back to `QUALITY_EFFORT_FALLBACK_WATTS=150W`. The `_is_quality_effort` function was designed to accept an estimated FTP and apply the tighter `85% of FTP` threshold, but this code path is never used. For a strong rider with FTP ~300W, efforts at 155W (barely above the 150W fallback) qualify as "quality efforts" and pollute the CP model with sub-threshold data, producing an underestimated FTP. The parameter exists but is dead code at the call site.

**Fix:** Either implement a bootstrap pass (compute the mean of the top-N effort mean powers as an initial FTP proxy), or if two-pass filtering is a Phase 2 enhancement, document that explicitly and remove the unused parameter from `_is_quality_effort`.

---

### WR-002: `progress_load` stalls permanently when `current_ctl=0` and `back_issues=True`

**Severity:** Warning
**File:** `sports_science/load.py:25-26`

**Issue:** `back_cap = current_ctl * ramp_threshold`. When `current_ctl=0` (new user, cold start) and `back_issues=True`, `back_cap = 0 * 0.10 = 0.0`, so `max_ctl_increase = min(8.0, 0.0) = 0.0` and `recommended_ctl_target = 0.0`. A new user starting from zero CTL with back constraints will always be told to train at 0 CTL and can never begin training. The back-protective cap is intended to limit relative load increases, not prevent any load.

**Fix:**
```python
BACK_CONSTRAINT_MIN_INCREASE: float = 2.0  # floor: even back-constrained beginners can start

if back_constraints_applied:
    ramp_threshold = constraints.get("load_ramp_flag_threshold_pct", 10) / 100
    back_cap = max(current_ctl * ramp_threshold, BACK_CONSTRAINT_MIN_INCREASE)
    max_ctl_increase = min(max_ctl_increase, back_cap)
```

---

### WR-003: `pmc_history` has no `UNIQUE(user_id, date)` constraint -- duplicate PMC rows corrupt CTL/ATL

**Severity:** Warning
**File:** `supabase/migrations/0001_initial_schema.sql:88-103`

**Issue:** There is no unique constraint on `(user_id, date)` in `pmc_history`. If `update_pmc` is called twice for the same day (retry, re-sync, bug), duplicate rows are silently inserted. When the PMC time series is later read sequentially, duplicate dates silently corrupt CTL/ATL/TSB values because the algorithm applies an extra EWMA step for a phantom day.

**Fix:**
```sql
ALTER TABLE public.pmc_history
    ADD CONSTRAINT pmc_history_user_date_unique UNIQUE (user_id, date);
```
Callers should use `INSERT ... ON CONFLICT (user_id, date) DO UPDATE` (upsert) to update existing rows.

---

### WR-004: `ftp.py` docstring says `medium: 7-12` but code produces `high` at `n=12`

**Severity:** Warning
**File:** `sports_science/ftp.py:41, 83`

**Issue:** The docstring states `medium: 7-12 efforts`. The code at line 83 is `elif n < 12: confidence = "medium"`, so `n=12` produces `"high"`, not `"medium"`. The boundary is off-by-one relative to the documentation. The test `test_confidence_levels` passes 12 efforts and expects `"high"`, confirming the code is correct -- the docstring is wrong. Anyone reading the docstring to implement a caller will misunderstand the confidence tiers.

**Fix:** Correct the docstring:
```
medium: 7-11 efforts
high: 12+ efforts
```

---

### WR-005: `compute_tss` value dict uses `"if"` as a key -- Python reserved word

**Severity:** Warning
**File:** `sports_science/metrics.py:99, 79`

**Issue:** The value dict stores the intensity factor as `"if"` (line 99). `if` is a Python reserved keyword. While it is legal as a dict string key, it is pathological in practice: any code that tries to unpack this dict as keyword arguments (`**result.value`) will fail with a `SyntaxError`, and some JSON schema generators and OpenAPI tools treat `if` as a reserved keyword in JSON Schema draft-7+. This will cause breakage when the tool schema is generated in Phase 2.

**Fix:** Rename the key to `"intensity_factor"` throughout (metrics.py lines 79, 99; all test assertions on `result.value["if"]` in test_metrics.py).

---

### WR-006: `sessions.status` and `messages.role` have no CHECK constraints

**Severity:** Warning
**File:** `supabase/migrations/0001_initial_schema.sql:56, 125`

**Issue:** `sessions.status` (default `'planned'`) and `messages.role` (documented as `'user' | 'assistant'`) are unconstrained `text` columns. Any string is accepted without error. Downstream code that switches on these values will silently malfunction on typos or unexpected values (e.g., `'compelted'`, `'system'`).

**Fix:**
```sql
-- sessions
status text NOT NULL DEFAULT 'planned'
    CHECK (status IN ('planned', 'completed', 'skipped', 'partial')),

-- messages
role text NOT NULL
    CHECK (role IN ('user', 'assistant', 'tool')),
```

---

### WR-007: `users.google_tokens` stores OAuth refresh tokens unencrypted

**Severity:** Warning
**File:** `supabase/migrations/0001_initial_schema.sql:13`

**Issue:** The comment says "encrypted at app layer (Phase 3)" but the column ships as plain `jsonb` with no encryption, no access restriction beyond RLS, and no constraint preventing writes before Phase 3. Google OAuth refresh tokens are long-lived credentials. If Phase 2 code writes a real token here before encryption is in place, those tokens are stored in plaintext in Postgres, accessible via any backup, the Supabase Studio admin panel, or any service-role query.

**Fix:** Do not add this column until Phase 3 encryption is wired. For Phase 1-2, track `google_connected: boolean` instead and add the tokens column in the Phase 3 migration. Add a migration comment with an explicit tracking issue reference.

---

### IN-001: `calculate_hr_zones` parameter named `max_hr_or_lthr` but zone boundaries assume LTHR

**Severity:** Info
**File:** `sports_science/zones.py:31`

**Issue:** The parameter name implies it accepts either max HR or LTHR. The zone multipliers in `HR_ZONE_BOUNDARIES` (zone 4 upper = 1.00, zone 5 lower = 1.00) are calibrated for LTHR only. Passing max HR would place zones incorrectly (zone 5 would start at max HR rather than at LTHR). The `inputs` dict stores the value as `"lthr"` and the docstring says "LTHR", so the parameter name is the sole outlier.

**Fix:** Rename the parameter to `lthr: float`.

---

### IN-002: `test_import_boundary.py` silently passes when `grep` receives a non-existent path

**Severity:** Info
**File:** `tests/sports_science/test_import_boundary.py:8-14`

**Issue:** The subprocess uses `["grep", "-r", "anthropic", "sports_science/"]` with a relative path. If pytest is invoked from any directory other than the project root, `grep` exits with returncode 2 (path error, not found), not returncode 1 (no matches). The assertion `assert result.returncode != 0` passes for both returncode 1 (correct) and returncode 2 (incorrect: grep never ran). A misconfigured CI job silently reports this security boundary test as passing even though the check was never performed.

**Fix:**
```python
import pathlib, subprocess

def test_sports_science_has_zero_anthropic_imports():
    pkg_dir = pathlib.Path(__file__).parents[2] / "sports_science"
    result = subprocess.run(
        ["grep", "-r", "--include=*.py", "anthropic", str(pkg_dir)],
        capture_output=True, text=True,
    )
    # returncode 1 = no matches (pass); 0 = found (fail); 2 = error (fail)
    assert result.returncode == 1, (
        f"Unexpected grep result (rc={result.returncode}):\n{result.stdout}{result.stderr}"
    )
```

---

### IN-003: `capability_gaps.conversation_id` has no FK constraint

**Severity:** Info
**File:** `supabase/migrations/0001_initial_schema.sql:147`

**Issue:** `conversation_id uuid` in `capability_gaps` is stored without a `REFERENCES public.conversations` FK. Any UUID can be written, including deleted or never-existing conversation IDs, silently corrupting the audit trail.

**Fix:**
```sql
conversation_id uuid REFERENCES public.conversations(id) ON DELETE SET NULL,
```

---

### IN-004: No database indexes on high-frequency query patterns

**Severity:** Info
**File:** `supabase/migrations/0001_initial_schema.sql:88-103, 69-84`

**Issue:** The `pmc_history` table will be queried by date range per user on every PMC display load. The `rides` table will be queried by user for FTP estimation. Neither has an index beyond the primary key. Sequential scans on these tables will be unacceptable in production.

**Fix:**
```sql
CREATE INDEX idx_pmc_history_user_date  ON public.pmc_history (user_id, date DESC);
CREATE INDEX idx_rides_user_created     ON public.rides (user_id, created_at DESC);
```

---

### IN-005: `rides` table has no `session_id` FK -- ride/session relationship is schema-invisible

**Severity:** Info
**File:** `supabase/migrations/0001_initial_schema.sql:69-78`

**Issue:** There is no column linking a completed ride to the planned session it fulfills. `validate_session_vs_actual` accepts plain dicts at the Python layer, but the DB schema cannot enforce or query which ride maps to which session. The relationship is purely application-layer, with no referential integrity or query path.

**Fix:** Add `session_id uuid REFERENCES public.sessions(id) ON DELETE SET NULL` to the `rides` table.

---

_Reviewed: 2026-06-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
