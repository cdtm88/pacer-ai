---
phase: 01-sports-science-foundation
reviewed: 2026-07-06T00:00:00Z
depth: standard
files_reviewed: 23
files_reviewed_list:
  - backend/sports_science/__init__.py
  - backend/sports_science/capability_gap.py
  - backend/sports_science/compliance.py
  - backend/sports_science/constants.py
  - backend/sports_science/ftp.py
  - backend/sports_science/load.py
  - backend/sports_science/metrics.py
  - backend/sports_science/pmc.py
  - backend/sports_science/types.py
  - backend/sports_science/zones.py
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
findings:
  critical: 3
  warning: 3
  info: 5
  total: 11
status: issues_found
---

# Phase 1: Code Review Report

**Reviewed:** 2026-07-06T00:00:00Z
**Depth:** standard
**Files Reviewed:** 23
**Status:** issues_found

## Summary

This is a fresh, from-scratch review of the current state of the sports-science tool library, its tests, and the initial Supabase schema. It does not assume the 2026-06-19 review's findings (CR-001..004, WR-001..007, IN-001..005) are still valid, nor that they are all fixed — each claim in this report was independently re-derived from the current source and, where possible, verified by executing the code live against the repo's `.venv`.

**What's confirmed fixed since the last review:** the `ftp=0` ZeroDivisionError in `compute_tss` (guarded at `metrics.py:55-61`), the unhandled `curve_fit` `RuntimeError`/`ValueError` in `estimate_ftp_from_rides` (guarded at `ftp.py:64-83`), the `KeyError`-on-missing-env-vars crash in `capability_gap.py` (now uses `.get()` + `EnvironmentError`), the cross-conversation `messages` RLS gap (now has a `WITH CHECK` verifying conversation ownership), the zero-CTL back-constrained load stall in `progress_load` (now has a `BACK_CONSTRAINT_MIN_INCREASE` floor), the missing `pmc_history` unique constraint, the `"if"`-as-dict-key issue in `compute_tss` (now `intensity_factor`), and the missing `CHECK` constraints on `sessions.status`/`messages.role`. All of these were verified against the current file contents and/or reproduced with a live Python repl.

**What's new in this pass:** two of the currently-passing tests were proven, by live execution, to be vacuous or to silently skip the behavior they claim to verify (CR-01, CR-03). A third finding is a genuine domain-logic defect in FTP estimation that directly undermines the project's stated core value for its target persona (a deconditioned beginner with no FTP history) — this replaces and supersedes the old review's WR-001, which flagged the same code for a different (opposite-direction) concern.

**What's still open from the last review, unchanged:** `users.google_tokens` still ships as plaintext `jsonb` ahead of the Phase 3 encryption work; `capability_gaps.conversation_id` and `rides` still lack the FK relationships the old review flagged.

All 92 tests in `tests/sports_science/` pass. "Tests pass" is not being treated as evidence of correctness here — see CR-01 and CR-03 for concrete, reproduced counterexamples.

## Critical Issues

### CR-01: TRUST-01 import-boundary tests are vacuous — they pass regardless of what the code does

**File:** `tests/sports_science/test_import_boundary.py:5-32`
**Issue:** Both tests shell out to `grep -r "<name>" sports_science/`, a path relative to the repository root. The actual package lives at `backend/sports_science/` — `sports_science/` does not exist at the repo root. `grep` on a nonexistent directory exits with status `2` (error), not `1` (no match found). The assertion is `assert result.returncode != 0`, which treats *any* non-zero code as "no matches" — so the test passes whether or not `backend/sports_science/` actually contains an `anthropic` or `fastapi` import.

Verified live:
```
$ grep -r "anthropic" sports_science/
ugrep: warning: sports_science/: No such file or directory
$ echo $?
2
$ pytest tests/sports_science/test_import_boundary.py -v
test_sports_science_has_zero_anthropic_imports PASSED
test_sports_science_has_zero_fastapi_imports PASSED
```
This is the automated enforcement mechanism for TRUST-01 ("Zero SDK imports from the LLM layer anywhere in this package," described in `CLAUDE.md` as "Enforced at code level, verifiable in logs"). Right now it enforces nothing — an `import anthropic` added anywhere under `backend/sports_science/` would still pass this suite.

**Fix:**
```python
import subprocess

def test_sports_science_has_zero_anthropic_imports():
    result = subprocess.run(
        ["grep", "-r", "anthropic", "backend/sports_science/"],
        capture_output=True, text=True,
    )
    # 1 = grep ran and found no match. Anything else (0 = match found,
    # 2 = path/usage error) must fail loudly instead of being conflated.
    assert result.returncode == 1, (
        f"grep did not cleanly report 'no match' (rc={result.returncode}): "
        f"{result.stdout}{result.stderr}"
    )
```
Apply the same fix to the `fastapi` test.

---

### CR-02: FTP quality-effort filter always uses the flat 150W fallback — beginners below that threshold never get an FTP estimate

**File:** `backend/sports_science/ftp.py:46`
**Issue:** `_is_quality_effort(effort, best_ftp_estimate)` is designed to use a ratio-based threshold (85% of a prior FTP estimate) when one is available, falling back to a flat `QUALITY_EFFORT_FALLBACK_WATTS` (150W) only when no estimate exists yet. But `estimate_ftp_from_rides` calls it with `best_ftp_estimate=None` unconditionally:
```python
quality_efforts = [e for e in rides if _is_quality_effort(e, best_ftp_estimate=None)]
```
There is no first pass anywhere that computes a preliminary estimate and re-filters with the ratio path — the ratio branch in `_is_quality_effort` is dead code. The threshold is therefore always the flat 150W, for every rider, forever.

Verified live: a rider whose best 3-20 minute efforts are 140-149W (a realistic range for the project's explicit target persona — "beginner returning to fitness... no FTP and no fitness history") produces **zero** quality efforts no matter how many rides are supplied:
```python
rides = [
    {"duration_secs": 1200, "mean_power_watts": 140},
    {"duration_secs": 600,  "mean_power_watts": 145},
    {"duration_secs": 300,  "mean_power_watts": 148},
    {"duration_secs": 180,  "mean_power_watts": 149},
]
estimate_ftp_from_rides(rides).value  # -> None, confidence="insufficient_data"
```
This means `estimate_ftp_from_rides` can never succeed for a genuinely deconditioned beginner (or, effectively, anyone whose real FTP is under ~150W/0.85 ≈ 176W without ever exceeding 150W in a single effort), directly contradicting the project's core value statement: "...that plan adapts automatically as real ride data arrives." No test in `test_ftp.py` exercises efforts below 150W, so this gap is currently untested. (The 2026-06-19 review flagged this same dead-parameter pattern from the opposite angle — worrying it would under-filter a *strong* rider's noise; the more serious consequence is that it can completely block estimation for the weaker riders this product is built for.)

**Fix:** Either (a) implement the intended two-pass approach — a loose first pass (e.g., duration-only filter) to derive a rough `best_ftp_estimate`, then re-filter with the 85% ratio — or (b) if a single-pass design is intentional, lower `QUALITY_EFFORT_FALLBACK_WATTS` to a value that doesn't exclude realistic beginner power outputs, and remove the now-misleading `best_ftp_estimate` parameter from `_is_quality_effort` if it will never be used.

---

### CR-03: Module-level Supabase client singleton + blanket `except Exception: pass` makes gap-logging failures permanently silent, and demonstrably breaks the test that's supposed to prove the failure path works

**File:** `backend/sports_science/capability_gap.py:37-50, 81-82`
**Issue:** `_get_async_supabase()` caches the client in the module-level `_supabase_client` global and never invalidates it. Combined with `log_capability_gap`'s `except Exception: pass`, this produces two compounding problems:

1. **Production:** once a client is successfully created, it is reused for the lifetime of the process with no retry/refresh logic. If Supabase credentials rotate or the client starts erroring, every subsequent `log_capability_gap` call silently swallows the failure with zero logging — the entire point of TOOL-08/GAP-01 telemetry (catching capability gaps in production so the team knows what tools to build next) is defeated with no operator visibility.

2. **Tests:** `test_db_error_returns_fallback_tool_result` re-patches `acreate_client` with a fresh mock whose `.execute()` raises `Exception("DB connection failed")`, intending to prove the error-handling path works. Because of the module-level cache, this is not what happens — if any earlier test in the process already caused `_get_async_supabase()` to succeed, the cached (working) client is returned instead, `acreate_client` is never called again, and the raising mock is never exercised.

Verified live by replaying the test file's execution order directly against the module:
```
after test1 (no env vars set) -> cache = None
after test4 (test_supabase_insert_called_with_correct_fields, sets env vars) -> cache is that test's mock: True
test7 (test_db_error_returns_fallback_tool_result):
  acreate_client (its own newly-patched mock) called? False
  execute_mock (the one configured to raise) called? False
  result still comes back as {"status": "logged", ...}
```
The test passes, but it is not testing what its name and docstring claim ("GAP-02: DB insert failure must not prevent returning the fallback ToolResult") — it happens to pass because the DB call never actually runs in that test at all.

**Fix:**
- Log the exception instead of swallowing it silently: `logger.exception("capability_gap insert failed")` before `pass`.
- Add a test-only reset hook (e.g., `capability_gap._reset_client_for_tests()` called from an autouse fixture in `conftest.py`) so each test starts from `_supabase_client = None`, restoring test isolation.
- Consider whether the singleton should be recreated after N consecutive failures, or at minimum whether failures should increment a metric/counter so operators aren't blind to a permanently-broken gap logger.

## Warnings

### WR-01: `calculate_hr_zones(max_hr_or_lthr)` parameter name invites passing the wrong quantity

**File:** `backend/sports_science/zones.py:31-53`
**Issue:** The parameter is named `max_hr_or_lthr`, implying either a max-HR or an LTHR value is acceptable. But `HR_ZONE_BOUNDARIES` (in `constants.py`) is explicitly derived as percentages of **LTHR only** — the whole point of `D-06`'s correction (0.68/0.83/0.94/1.05) was to fix a previous mislabeling and make Zone 2's ceiling "materially gentler for a deconditioned, back-flagged beginner." If any caller passes a raw max-HR value directly (which the parameter name explicitly invites), the computed zone boundaries will run too high — LTHR is typically ~85-92% of max HR — pushing a beginner into harder-than-intended training zones. `estimate_lthr_from_max_hr` exists specifically to convert max HR to LTHR first, but nothing in `calculate_hr_zones`'s signature or type enforces that conversion happens before this function is called. (The 2026-06-19 review noted the naming mismatch as Info; given the explicit beginner-safety rationale behind the boundary values themselves, this is more accurately a Warning — a caller misuse here has direct physiological-safety consequences, not just a cosmetic naming issue.)
**Fix:** Rename the parameter to `lthr` (matching `inputs={"lthr": ...}` already used in the return value), and document/require that callers holding only a max-HR value must call `estimate_lthr_from_max_hr` first.

### WR-02: `estimate_lthr_from_max_hr` is not exported from `sports_science/__init__.py`'s `__all__`

**File:** `backend/sports_science/__init__.py:19-29`, `backend/sports_science/zones.py:56-74`
**Issue:** `__init__.py`'s docstring states `__all__` is the TRUST-02 tool-registry contract ("the Phase 2 tool registry wraps ONLY these names as Anthropic tool schemas"). `estimate_lthr_from_max_hr` is a pure, DB-free, Anthropic-free function tagged `D-05/ONBD-05` and exercised directly in `test_zones.py::test_estimate_lthr_from_max_hr`, but it is not imported or listed in `__all__` alongside the other eight tools. If it's meant to be callable by the agent (its docstring reads like a tool: "the LLM never derives this number itself"), its omission means it silently cannot be invoked through the registry. If it's intentionally internal-only (called directly by an onboarding route rather than through the tool loop), that's fine, but nothing in the code signals which is true.
**Fix:** Either add it to `__all__` if it should be LLM-invokable, or add a comment explaining why it's deliberately excluded (e.g., "invoked directly by the onboarding route before a conversation exists, not exposed as an agent tool").

### WR-03: `users.google_tokens` still stores OAuth refresh tokens unencrypted (carried over, unresolved)

**File:** `supabase/migrations/0001_initial_schema.sql:13`
**Issue:** The comment says "encrypted at app layer (Phase 3)" but the column ships as plain `jsonb` with no encryption, no access restriction beyond RLS, and no constraint preventing writes before Phase 3 lands. Google OAuth refresh tokens are long-lived credentials; if any Phase 2 code path writes a real token here before encryption is wired, that token is stored in plaintext in Postgres, accessible via any backup, the Supabase Studio admin panel, or any service-role query. This was flagged in the previous review and remains unresolved in the current migration.
**Fix:** Do not write real tokens to this column until Phase 3 encryption is wired. For Phase 1-2, consider tracking `google_connected: boolean` instead, and add the tokens column (encrypted) in the Phase 3 migration with an explicit tracking reference.

## Info

### IN-01: Unsynchronized double-checked-locking pattern in `_get_async_supabase` can create two clients under concurrency

**File:** `backend/sports_science/capability_gap.py:28-50`
**Issue:** `_get_async_supabase` checks `if _supabase_client is not None: return _supabase_client` and only later awaits `acreate_client`. Two concurrent calls that both observe `_supabase_client is None` before either finishes awaiting will each construct a client; the second assignment silently overwrites (and never closes) the first. Low likelihood in practice, but worth guarding with an `asyncio.Lock` if cold-start concurrency is plausible (e.g., first requests after a serverless cold start).
**Fix:**
```python
_client_lock = asyncio.Lock()

async def _get_async_supabase() -> AsyncClient:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    async with _client_lock:
        if _supabase_client is None:
            ...
            _supabase_client = await acreate_client(url, key)
    return _supabase_client
```

### IN-02: `round()`'s banker's-rounding can shift zone boundaries by 1 unit at exact `.5` values

**File:** `backend/sports_science/zones.py:14-15, 39-40`
**Issue:** `round(z["lower"] * ftp)` uses Python's round-half-to-even. E.g., at FTP=110W, `0.55 * 110 = 60.5` rounds to `60`, not `61`. This is a user-facing training-zone number, so occasional off-by-one-watt boundaries at exact halves are a minor fidelity issue (not a correctness bug — just worth being aware it isn't "round half up").
**Fix:** No action required unless boundary precision at exact `.5` values matters to the product; if so, use `math.floor(x + 0.5)` for round-half-up semantics.

### IN-03: `_compute_np`'s fallback-cap branch is unreachable from the only production call site

**File:** `backend/sports_science/metrics.py:11-29`
**Issue:** `_compute_np`'s `cap = ftp * NP_SPIKE_MULTIPLIER if ftp else NP_SPIKE_FALLBACK_WATTS` branch only triggers when `ftp` is falsy. The sole production caller, `compute_tss`, already returns early with `value=None` when `ftp <= 0` (line 55-61) before ever calling `_compute_np`. The fallback branch is therefore dead code in production and is exercised only via tests that import and call the private `_compute_np` directly.
**Fix:** Either document that the fallback exists for future/alternate callers of `_compute_np`, or remove it if `compute_tss` is intended to remain the only caller.

### IN-04: `capability_gaps.conversation_id` has no FK constraint (carried over, unresolved)

**File:** `supabase/migrations/0001_initial_schema.sql:151-159`
**Issue:** `conversation_id uuid` in `capability_gaps` is stored without a `REFERENCES public.conversations` FK. Any UUID can be written, including deleted or never-existing conversation IDs, silently corrupting the audit trail. Flagged in the previous review; still absent in the current migration.
**Fix:**
```sql
conversation_id uuid REFERENCES public.conversations(id) ON DELETE SET NULL,
```

### IN-05: `rides` table has no `session_id` FK — ride/session relationship is schema-invisible (carried over, unresolved)

**File:** `supabase/migrations/0001_initial_schema.sql:70-84`
**Issue:** There is no column linking a completed ride to the planned session it fulfills. `validate_session_vs_actual` accepts plain dicts at the Python layer, but the DB schema cannot enforce or query which ride maps to which session — the relationship is purely application-layer, with no referential integrity or query path. Flagged in the previous review; still absent in the current migration.
**Fix:** Add `session_id uuid REFERENCES public.sessions(id) ON DELETE SET NULL` to the `rides` table.

---

_Reviewed: 2026-07-06T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
