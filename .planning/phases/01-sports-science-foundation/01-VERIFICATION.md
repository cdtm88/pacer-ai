---
phase: 01-sports-science-foundation
verified: 2026-07-06T00:00:00Z
status: gaps_found
score: 2/5 must-haves verified
behavior_unverified: 0
overrides_applied: 0
gaps:
  - truth: "The sports_science/ module has zero Anthropic SDK imports; no import path connects it to the agent layer (SC3, TRUST-01)"
    status: failed
    reason: >
      The automated enforcement test for TRUST-01 is vacuous and cannot detect a violation
      even if one were introduced. Both tests in test_import_boundary.py shell out to
      `grep -r "<name>" sports_science/` -- a path relative to the repo root that has never
      existed (the package lives at backend/sports_science/). Verified live: `grep -r
      "anthropic" sports_science/` exits with status 2 (path error), not 1 (no match). The
      test asserts `result.returncode != 0`, which is true for BOTH "no match" (1) and
      "grep errored because the path doesn't exist" (2) -- so the test passes unconditionally,
      regardless of what backend/sports_science/ actually contains. Confirmed by running
      `pytest tests/sports_science/test_import_boundary.py -v`: both tests PASS with zero
      discriminating power.
      Separately verified by direct inspection: `grep -rn "anthropic|openai|fastapi"
      backend/sports_science/` returns zero matches today, so the underlying invariant
      currently holds -- but it holds by author discipline, not by an enforced, working
      test. The phase goal requires functions be "verified correct before any other layer
      depends on it"; a test that always passes is not verification.
    artifacts:
      - path: "tests/sports_science/test_import_boundary.py"
        issue: "Greps a nonexistent root-level `sports_science/` path instead of `backend/sports_science/`; grep's error exit code (2) is conflated with a real \"no match\" exit code (1), so the assertion `returncode != 0` is always true."
    missing:
      - "Fix the grep target path to `backend/sports_science/` in both tests"
      - "Distinguish grep's error exit (2, path/usage problem -- must fail loudly) from its no-match exit (1, actual pass) instead of treating any non-zero code as pass"
  - truth: "The CP model rejects any FTP estimate derived from fewer than 4 quality efforts (SC2, TOOL-03, TOOL-06)"
    status: failed
    reason: >
      estimate_ftp_from_rides's "requires 4+ quality efforts" gate technically holds, but the
      quality-effort filter it depends on is broken by dead code, making the tool unable to
      ever produce an FTP estimate for the project's own target persona ("a beginner
      returning to fitness... no FTP and no fitness history"). `_is_quality_effort` is
      designed with a two-pass ratio threshold (85% of a prior FTP estimate) that falls back
      to a flat 150W only when no prior estimate exists -- but `estimate_ftp_from_rides`
      calls it with `best_ftp_estimate=None` unconditionally (ftp.py:46); there is no first
      pass anywhere that computes a rough estimate and re-filters with the ratio. The ratio
      branch is permanently dead code, and the threshold is always the flat 150W for every
      rider, forever.
      Verified live: for a rider whose best 3-20 minute efforts are realistic deconditioned-
      beginner values (140W/145W/148W/149W), estimate_ftp_from_rides(rides).value is None
      with confidence="insufficient_data" and quality_efforts=0, no matter how many such
      rides are supplied -- this rider can never receive an FTP estimate under this code.
      No test in test_ftp.py exercises efforts below 150W (confirmed by reading the file);
      this gap is currently untested as well as broken.
    artifacts:
      - path: "backend/sports_science/ftp.py"
        issue: "Line 46: estimate_ftp_from_rides always calls _is_quality_effort(e, best_ftp_estimate=None), making the ratio-threshold branch permanently unreachable and hardcoding a 150W flat floor for all riders."
    missing:
      - "Implement the intended two-pass approach (loose first-pass filter -> rough estimate -> re-filter at 85% ratio), OR lower QUALITY_EFFORT_FALLBACK_WATTS to a value that does not exclude realistic beginner power output, and remove the now-misleading best_ftp_estimate parameter if a single-pass design is intentional"
      - "Add a test_ftp.py case covering efforts in the 100-149W range (the stated target persona) to lock in the fix"
  - truth: "log_capability_gap appends a structured entry and returns a user-facing fallback message on DB failure, with that behavior actually verified by test (SC4, GAP-01, GAP-02)"
    status: failed
    reason: >
      Functionally, log_capability_gap's exception-swallowing DOES work when actually
      exercised (verified live: with a freshly-reset module cache and a raising execute()
      mock, the exception is caught and the fallback ToolResult is still returned). The
      problem is twofold: (1) the specific test that claims to prove this,
      test_db_error_returns_fallback_tool_result, does not actually exercise the failure
      path, because _get_async_supabase() caches its client in a module-level global that
      is never reset between tests -- if an earlier test in the same process already
      populated the cache with a working mock client, that cached client is returned instead
      of the newly-patched raising one, and the raising mock is never called. Verified live
      by replaying the test file's execution order: after the earlier
      test_supabase_insert_called_with_correct_fields test runs, the cache holds its mock
      client; the later DB-error test's own patched acreate_client is never invoked
      (mock2.called == False) and its raising execute() is never invoked
      (execute_mock_fail.called == False), yet the test still passes. (2) Combined with the
      blanket `except Exception: pass` in log_capability_gap, any real production failure
      (credential rotation, network issue) is silently and permanently swallowed with zero
      logging -- defeating the operator-visibility purpose of TOOL-08/GAP-01 telemetry
      (catching capability gaps so the team knows what tools to build next).
    artifacts:
      - path: "backend/sports_science/capability_gap.py"
        issue: "_get_async_supabase() caches _supabase_client at module level with no test-reset hook, and log_capability_gap's `except Exception: pass` logs nothing on failure -- both compound to make the DB-failure test order-dependent and to make real failures invisible in production."
      - path: "tests/sports_science/test_capability_gap.py"
        issue: "test_db_error_returns_fallback_tool_result passes without ever calling its own patched acreate_client or its raising execute() mock, due to the module-level client cache from an earlier test in the same run."
    missing:
      - "Add a test-only reset hook (e.g. capability_gap._reset_client_for_tests()) invoked from an autouse conftest fixture so each test starts with _supabase_client = None"
      - "Replace `except Exception: pass` with `except Exception: logger.exception(...)` (or increment a metric) so silent production failures are observable"
      - "Re-run the DB-error test after the reset hook is added to confirm it actually exercises the raising mock"
deferred: []
human_verification:
  - test: "Confirm the 0001_initial_schema.sql migration (8 tables + RLS) is actually applied to the live/linked Supabase cloud project, and that an anon-key insert against any table is rejected by RLS"
    expected: "All 8 tables visible in Supabase Studio Table Editor with RLS shield icons; an anon-role insert/select against e.g. capability_gaps returns 0 rows / permission denied"
    why_human: "This verifier could not query the live Supabase project directly (no DB credentials available in this session/sandbox). Strong circumstantial evidence supports migration being applied -- supabase/.temp/linked-project.json shows an active linked project (pxdfmlvrqveofguyxxfo), and 8 further migrations (0002-0009) exist in supabase/migrations/ that structurally depend on the 0001 schema already being in place -- but this has not been confirmed via a live query in this pass. The original 01-05-SUMMARY.md documented the `supabase db push` step as PENDING and the human-verify checkpoint as AWAITING HUMAN at the time Phase 1 was first executed."
---

# Phase 1: Sports-Science Foundation Verification Report

**Phase Goal:** A complete, unit-tested sports-science tool library and database schema exist; every physiological function is verified correct before any other layer depends on it
**Verified:** 2026-07-06T00:00:00Z
**Status:** gaps_found
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All tool functions return structured ToolResult(value, unit, methodology, inputs); edge cases (zeros, spike filter, cold-start, back-protective, sparse data) pass | VERIFIED | `pytest tests/sports_science/ -v` → 92/92 passed live. Spot-checked `test_metrics.py` (zeros, spike filter, short-ride null), `test_pmc.py` (cold-start guard at 10/27/28+ days), `test_load.py` (back-protective cap with specific numeric assertions), `test_ftp.py` (insufficient-data path). All substantive, not stubs. |
| 2 | The CP model rejects any FTP estimate derived from fewer than 4 quality efforts; update_pmc does not emit TSB until 28+ days | FAILED | Literal 4-effort gate and 28-day cold-start guard both pass in tests and live execution. BUT: live execution proves `estimate_ftp_from_rides` can **never** produce an estimate for the project's stated target persona (deconditioned beginner, 140-149W efforts) because `_is_quality_effort` is always called with `best_ftp_estimate=None` (ftp.py:46), making its ratio-threshold branch permanently dead code and hardcoding a 150W floor no realistic beginner effort clears. See gap detail. |
| 3 | sports_science/ module has zero Anthropic SDK imports; no import path connects it to the agent layer | FAILED | Underlying invariant currently holds (`grep -rn "anthropic|openai|fastapi" backend/sports_science/*.py` → zero matches, confirmed by direct file read of all imports). But the automated test built to enforce/verify this (test_import_boundary.py) is vacuous — it greps a nonexistent `sports_science/` root path, grep exits 2, and the test's `assert returncode != 0` treats that identically to a real pass. Verified live: the test PASSES with zero discriminating power, so an actual regression (e.g. someone adds `import anthropic` to backend/sports_science/) would go undetected. |
| 4 | log_capability_gap appends a structured entry to capability_gaps and returns a user-facing fallback message; registered as an Anthropic tool schema (TRUST-02); only the registry maps sports_science functions to schemas | FAILED | Registry wiring (SC4's second half) VERIFIED: `log_capability_gap` is in `backend/agent/tools.py`'s `TOOL_REGISTRY` and `TOOL_SCHEMAS`, and schema/registry definitions exist in exactly one file. BUT the fallback-on-DB-failure behavior, while functionally working when directly exercised, is (a) not actually proven by its own test due to test-order-dependent module-level client caching (verified live — the test's own mocks are never called, yet it passes), and (b) silently swallowed in production with zero logging (`except Exception: pass`), defeating GAP-01 telemetry's operator-visibility purpose. |
| 5 | The 8-table Supabase schema (users, profiles, sessions, rides, pmc_history, conversations, messages, capability_gaps) is migrated and accessible | VERIFIED (with human follow-up) | All 8 `CREATE TABLE` statements + `ENABLE ROW LEVEL SECURITY` present in `supabase/migrations/0001_initial_schema.sql`; `profiles.constraints` JSONB defaults to `{"back_issues": false}` as required. Strong indirect evidence of live application: `supabase/.temp/linked-project.json` shows an active linked cloud project, and 8 subsequent migrations (0002-0009) exist that structurally depend on 0001 already being applied. Direct live-DB confirmation not possible in this session (no credentials) — routed to human verification. |

**Score:** 2/5 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/sports_science/zones.py` | calculate_power_zones, calculate_hr_zones | VERIFIED | Substantive, imports from constants.py, all 15 zone tests pass including boundary-overlap parametrized cases |
| `backend/sports_science/metrics.py` | compute_tss, _compute_np | VERIFIED | Zero-FTP guard, spike filter, zero-inclusive NP all confirmed live |
| `backend/sports_science/pmc.py` | update_pmc (EWMA + cold-start) | VERIFIED | Cold-start guard confirmed false at 10/27 days, true at 28+ days |
| `backend/sports_science/ftp.py` | estimate_ftp_from_rides (CP model) | STUB-LIKE DEFECT | Exists, substantive code, wired, but the quality-effort filter's ratio branch is permanently dead code (CR-02) — see gap |
| `backend/sports_science/load.py` | progress_load (back-protective caps) | VERIFIED | Numeric back-constraint cap assertions pass live |
| `backend/sports_science/compliance.py` | validate_session_vs_actual | VERIFIED | Test suite passes |
| `backend/sports_science/capability_gap.py` | log_capability_gap | PARTIAL | Functionally works when exercised directly; production failure path is silent (no logging) and its own regression test doesn't actually exercise it (CR-03) |
| `supabase/migrations/0001_initial_schema.sql` | 8-table schema + RLS | VERIFIED | All 8 tables + RLS present; live application evidence indirect (see human verification) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `backend/sports_science/zones.py` | `backend/sports_science/constants.py` | imports `POWER_ZONE_BOUNDARIES`, `HR_ZONE_BOUNDARIES` | WIRED | Confirmed by import read |
| `backend/sports_science/ftp.py` | `backend/sports_science/constants.py` | imports `QUALITY_EFFORT_*`, `MIN_QUALITY_EFFORTS` | WIRED (but underlying logic defective — see CR-02) | Import present; `best_ftp_estimate` param never receives a live estimate |
| `backend/sports_science/__init__.py` | all 8 sports_science modules | `__all__` export surface | WIRED | Confirmed — `__init__.py` imports and re-exports all public tool functions |
| `backend/agent/tools.py` | `backend/sports_science/__init__.py` (+ submodules) | `TOOL_REGISTRY` dict + `TOOL_SCHEMAS` list | WIRED | `log_capability_gap`, all 7 other core tools, plus `save_profile`/`generate_plan`/`estimate_lthr_from_max_hr` (later-phase additions) present in both structures |
| `tests/sports_science/test_import_boundary.py` | `backend/sports_science/` | grep-based boundary check | NOT WIRED (vacuous) | Test greps the wrong path; confirmed vacuous via live run — see CR-01 gap |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `tests/sports_science/test_import_boundary.py` | 5-32 | Vacuous test (wrong grep path conflates error exit code with pass) | Blocker | TRUST-01 has no working automated enforcement |
| `backend/sports_science/ftp.py` | 46 | Dead-code ratio branch, hardcoded 150W floor | Blocker | Beginners under ~176W real FTP can never get an estimate |
| `backend/sports_science/capability_gap.py` | 37-50, 81-82 | Module-level client singleton + blanket `except Exception: pass` | Blocker | Silent production failures + non-functional regression test |
| `backend/sports_science/zones.py` | 31-53 | `calculate_hr_zones(max_hr_or_lthr)` param name invites passing raw max-HR instead of LTHR | Warning (carried from 01-REVIEW.md, not gating this phase) | Physiological-safety naming hazard, not a functional break today |
| `supabase/migrations/0001_initial_schema.sql` | 13 | `users.google_tokens` plaintext jsonb ahead of Phase 3 encryption | Warning (carried, tracked for Phase 3) | Not gating this phase |

No `TBD`/`FIXME`/`XXX` debt markers found in `backend/sports_science/*.py`.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TOOL-01 | 01-02 | Power zones | SATISFIED | zones.py + 15 passing tests |
| TOOL-02 | 01-02 | HR zones | SATISFIED | zones.py + passing tests (naming hazard noted as warning, not blocker) |
| TOOL-03 | 01-04 | FTP estimation via CP model | BLOCKED | CR-02: dead-code filter breaks estimation for target persona |
| TOOL-04 | 01-03 | compute_tss (NP/IF/TSS) | SATISFIED | metrics.py + passing tests |
| TOOL-05 | 01-03 | update_pmc (CTL/ATL/TSB, cold-start) | SATISFIED | pmc.py + passing tests |
| TOOL-06 | 01-04 | progress_load back-protective ramp | PARTIAL | load.py itself verified; requirement text bundles "safe ramp" concept with FTP-dependent planning elsewhere — flagged alongside TOOL-03 |
| TOOL-07 | 01-04 | validate_session_vs_actual | SATISFIED | compliance.py + passing tests |
| TOOL-08 | 01-05 | log_capability_gap | PARTIAL | Works when exercised; silent-failure + non-exercising test (CR-03) |
| TOOL-09 | 01-01/all | ToolResult contract | SATISFIED | Confirmed across all modules |
| TOOL-10 | all | Edge-case test coverage | PARTIAL | Sparse-data/zeros/spike/cold-start/back-protective covered; sub-150W beginner FTP scenario is NOT covered (the exact gap CR-02 exploits) |
| TRUST-01 | 01-02..04 | Zero Anthropic SDK imports | BLOCKED (enforcement) | Invariant holds today by inspection; automated test is vacuous (CR-01) |
| TRUST-02 | 01-05 | Tool registry is sole schema source | SATISFIED | Confirmed single-file schema/registry definition in backend/agent/tools.py |
| GAP-01 | 01-05 | Structured capability-gap DB entry | PARTIAL | Insert call correct when DB reachable; silent on failure (CR-03) |
| GAP-02 | 01-05 | Capability-gap log never expands runtime capability | SATISFIED | log_capability_gap only logs + returns fallback, never computes a number |
| GAP-03 | 01-05 | User-facing message hides internal method name | SATISFIED | Confirmed — hardcoded generic string, method_name DB-only |

No orphaned requirements found — all Phase 1 IDs in REQUIREMENTS.md (TOOL-01..10, TRUST-01/02, GAP-01..03) are claimed across the five plan frontmatters.

### Human Verification Required

### 1. Live Supabase schema application

**Test:** Query the linked Supabase project's Table Editor (or `supabase db pull`/`psql`) to confirm all 8 tables from `0001_initial_schema.sql` exist with RLS enabled, and attempt an anon-key insert against `capability_gaps` or `messages`.
**Expected:** All 8 tables visible with RLS shield icons; anon insert/select is rejected (0 rows / permission denied).
**Why human:** No DB credentials available to this verifier in-session. Strong indirect evidence (linked project file, 8 dependent later migrations) suggests this is done, but it was explicitly left PENDING/AWAITING HUMAN in the original 01-05-SUMMARY.md and has not been directly reconfirmed here.

## Gaps Summary

Three of the code-review's three CRITICAL findings were independently reproduced by live execution in this verification pass, and all three bear directly on stated Phase 1 success criteria:

1. **TRUST-01's enforcement test is vacuous** (SC3) — it greps a path that has never existed at the repo root, so it passes unconditionally regardless of what `backend/sports_science/` imports. The underlying invariant happens to hold today (confirmed by direct grep), but the phase goal demands the invariant be *verified*, not incidentally true. A one-line path fix plus tightening the exit-code check resolves this.

2. **FTP estimation is functionally broken for the project's own target persona** (SC2, TOOL-03) — `estimate_ftp_from_rides` can never return a value for a rider whose real FTP is under ~176W (any beginner whose best efforts stay below the hardcoded 150W flat threshold), because the intended two-pass ratio-based quality filter is dead code. This directly contradicts the project's core value statement about adapting to real beginner ride data. No existing test would have caught this — `test_ftp.py` never exercises sub-150W efforts.

3. **capability_gap's DB-failure path is silently unverifiable and silently swallowed in production** (SC4, GAP-01) — a module-level client cache makes the dedicated regression test order-dependent (it passes without ever calling its own mocks, confirmed live), and `except Exception: pass` means a real production failure (credential rotation, network blip) is permanently invisible with no log line, defeating the stated purpose of GAP-01 telemetry.

All three are narrowly-scoped, mechanically fixable issues (grep path, dead-parameter removal or fallback-threshold correction, cache-reset hook + exception logging) — none require an architecture change. Given the phase goal explicitly states "every physiological function is verified correct before any other layer depends on it," and Phase 2+ already builds the agent layer, tool registry, and onboarding flow on top of this foundation, these gaps should be closed with a targeted gap-closure plan before treating Phase 1 as fully trustworthy, even though the majority of the tool library (7 of 8 core functions, zone/metrics/pmc/load/compliance) is solid and correctly verified.

---

_Verified: 2026-07-06T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
