---
phase: 01-sports-science-foundation
plan: 06
subsystem: sports-science-tool-library
tags: [gap-closure, trust-model, ftp-estimation, capability-gap, testing]
dependency-graph:
  requires: [01-04-PLAN.md, 01-05-PLAN.md]
  provides: [trust01-enforcing-test, ftp-beginner-persona-support, capability-gap-observability]
  affects: [phase-2-agent-core, phase-3-coaching-loop]
tech-stack:
  added: []
  patterns:
    - "Two-pass quality-effort filter: loose duration pass -> rough CP fit -> ratio re-filter anchored to that estimate"
    - "Module-level client cache with a _reset_client_for_tests() test seam invoked from an autouse conftest fixture"
    - "grep exit-code discipline: distinguish 0 (match), 1 (clean no-match/pass), 2 (tooling error) rather than treating any non-zero as pass"
key-files:
  created: []
  modified:
    - tests/sports_science/test_import_boundary.py
    - backend/sports_science/ftp.py
    - tests/sports_science/test_ftp.py
    - backend/sports_science/capability_gap.py
    - tests/sports_science/conftest.py
    - tests/sports_science/test_capability_gap.py
decisions:
  - "Two-pass filter falls back to duration-qualified efforts (not null) when the rough CP fit fails to converge, so estimation degrades gracefully rather than losing the beginner persona entirely"
  - "logger.exception used (not a bare log.error) so the full traceback is captured for capability-gap DB failures without changing best-effort semantics (never re-raises)"
metrics:
  duration: "12 minutes"
  completed: 2026-07-06
status: complete
---

# Phase 1 Plan 06: Gap Closure (TRUST-01, FTP Two-Pass Filter, Capability-Gap Observability) Summary

Closed all three Phase 1 verification gaps: the TRUST-01 import-boundary test now genuinely enforces the zero-SDK-import invariant instead of passing unconditionally, the FTP two-pass quality-effort filter is reachable so a deconditioned-beginner effort set (140-149W) now yields a real estimate, and capability-gap DB failures are logged via `logger.exception` with a test seam that ends the module-client-cache order-dependence.

## What Was Built

### Task 1: TRUST-01 import-boundary test made genuinely enforcing

`tests/sports_science/test_import_boundary.py` previously greped a nonexistent root-level `sports_science/` path and asserted `returncode != 0`, which is true for both grep's "no match" exit (1) and its "path error" exit (2) — the test passed unconditionally regardless of what the tool library actually imported.

Fixed:
- Grep target corrected to `backend/sports_science/` (the real package path) in both existing tests.
- Assertion tightened to `returncode == 1` so a tooling/path error is distinguished from a genuine pass.
- Added `test_import_boundary_check_detects_violations(tmp_path)`, a meta-test that seeds a throwaway file with `import anthropic` under a temp directory and asserts grep returns exit code 0 — proving the mechanism can actually catch a real violation.

### Task 2: FTP two-pass quality-effort filter made reachable

`estimate_ftp_from_rides` previously called `_is_quality_effort(e, best_ftp_estimate=None)` unconditionally, permanently disabling the intended 85%-ratio branch and hardcoding a flat 150W floor. Any deconditioned-beginner effort set (this project's stated target persona) could never clear that floor, so `estimate_ftp_from_rides` always returned `value=None`.

Fixed via TDD (RED confirmed against the old single-pass code, then GREEN):
- Added `_rough_ftp_estimate(efforts)` helper: fits the existing `_cp_model` to a loose (duration-only) effort set using the same `curve_fit` call/p0/bounds/maxfev already in use; returns `None` on convergence failure.
- Rewrote `estimate_ftp_from_rides` as a genuine two-pass filter:
  1. Loose first pass: efforts with `duration_secs >= QUALITY_EFFORT_MIN_DURATION_SECS` only.
  2. If fewer than `MIN_QUALITY_EFFORTS` (4) survive, return `insufficient_data` immediately (unchanged behavior).
  3. Compute a rough CP estimate from the loose set.
  4. Second pass: re-filter using `_is_quality_effort(e, best_ftp_estimate=rough)` — this activates the 85%-of-estimate ratio branch, scale-invariant across a 140W beginner and a 300W rider alike. Falls back to the loose set if the rough fit doesn't converge.
  5. Re-apply the `>= MIN_QUALITY_EFFORTS` gate on the final filtered set before the final CP fit.
- Added `test_deconditioned_beginner_gets_estimate` (beginner effort set 140/145/148/149W now returns a real `ftp` in `[50, 500]` with `confidence == "low"`) and `test_quality_effort_ratio_branch_is_live` (direct call to `_is_quality_effort` with `best_ftp_estimate=200` proves the ratio branch is correct).

### Task 3: capability-gap DB-failure path made observable and genuinely tested

`capability_gap.py`'s `except Exception: pass` silently swallowed DB-insert failures with zero telemetry, and the module-level `_supabase_client` cache made `test_db_error_returns_fallback_tool_result` order-dependent — its own raising mock was never invoked if an earlier test had already cached a working client.

Fixed via TDD (RED confirmed: `execute_mock.await_count == 0` against the old code, then GREEN):
- Added a module `logger = logging.getLogger(__name__)` and replaced `except Exception: pass` with `logger.exception(...)`, including `method_name` in the backend-only log line (never surfaced to `value["message"]`, preserving GAP-03).
- Added `_reset_client_for_tests()` (`global _supabase_client = None`) as an explicit test seam — the module cache itself is retained (WR-04 connection-pool-leak rationale still holds).
- Added an autouse fixture in `conftest.py` that calls `capability_gap._reset_client_for_tests()` before and after every test in `tests/sports_science/`, ending the cross-test cache leak for the whole suite.
- Strengthened `test_db_error_returns_fallback_tool_result` to assert `execute_mock.await_count == 1` (the raising mock genuinely ran) and that `caplog` captured an ERROR-level record, in addition to the existing fallback-ToolResult assertions.

## Verification

```
.venv/bin/pytest tests/sports_science/test_import_boundary.py -q   -> 3 passed
.venv/bin/pytest tests/sports_science/test_ftp.py -q                -> 11 passed
.venv/bin/pytest tests/sports_science/test_capability_gap.py -q     -> 8 passed
.venv/bin/pytest tests/sports_science/ -q                           -> 95 passed (full-suite regression)
```

Live manual checks from the plan's verify blocks also passed:
- `estimate_ftp_from_rides` on the beginner effort set returns `{'ftp': 140.6, 'cp': 140.6, 'wprime': 1717.0, 'confidence': 'low'}`.
- `_is_quality_effort({'duration_secs':300,'mean_power_watts':180}, best_ftp_estimate=200)` is truthy; the 100W case is falsy.

## TDD Gate Compliance

Both TDD tasks followed the RED -> GREEN sequence with commits at each gate:

- Task 2 (FTP filter): `test(01-06): add failing beginner FTP regression test (RED)` (358a5dd) then `feat(01-06): make FTP two-pass quality-effort filter reachable` (7226e0e).
- Task 3 (capability-gap): `test(01-06): strengthen capability-gap DB-failure test (RED)` (474445c) then `fix(01-06): log capability-gap DB failures, add test reset seam` (076c290).

Note: `test_quality_effort_ratio_branch_is_live` (part of Task 2's RED commit) passed immediately rather than failing, because it calls `_is_quality_effort` directly and that function's ratio logic was already correct in isolation -- the defect was only in `estimate_ftp_from_rides` never invoking it with a live estimate. This is expected per the plan's own framing ("prove the branch is reachable and correct as two separate facts") and is not a RED-phase violation; `test_deconditioned_beginner_gets_estimate` (the test that exercises the actual reachability defect) failed correctly before the fix.

## Deviations from Plan

None - plan executed exactly as written. All three tasks, their read_first/action/verify/acceptance_criteria steps, and the TDD RED/GREEN sequence were followed as specified.

## Known Stubs

None. No hardcoded empty values, placeholder text, or unwired data sources were introduced.

## Threat Flags

None. This plan only strengthened existing enforcement (test correctness, filter reachability, failure observability) within files already covered by the phase's threat model; no new network endpoints, auth paths, or schema changes were introduced.

## Self-Check: PASSED

- FOUND: tests/sports_science/test_import_boundary.py
- FOUND: backend/sports_science/ftp.py
- FOUND: tests/sports_science/test_ftp.py
- FOUND: backend/sports_science/capability_gap.py
- FOUND: tests/sports_science/conftest.py
- FOUND: tests/sports_science/test_capability_gap.py
- FOUND commit 42039d6 (Task 1)
- FOUND commit 358a5dd (Task 2 RED)
- FOUND commit 7226e0e (Task 2 GREEN)
- FOUND commit 474445c (Task 3 RED)
- FOUND commit 076c290 (Task 3 GREEN)
