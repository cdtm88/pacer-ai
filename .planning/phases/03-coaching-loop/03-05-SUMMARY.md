---
phase: 03-coaching-loop
plan: 05
subsystem: adaptations
status: complete
tags: [adaptations, signal-detection, micro-macro, trust, transparency, coaching-loop]
dependency_graph:
  requires: [03-01, 03-02, 03-03, 03-04]
  provides: [ADAPT-01, ADAPT-02, ADAPT-03, ADAPT-04, ADAPT-05, TRANSP-01, TRANSP-02, TRANSP-03]
  affects: [api/routes/adaptations.py, api/main.py, tests/api/test_adaptations.py, tests/agent/fixtures/trust_corpus.py]
tech_stack:
  added: []
  patterns:
    - "Supabase async singleton (_get_async_supabase) reused from capability_gap.py"
    - "Pydantic body model (UserIdBody) for JSON endpoint body parsing"
    - "Pure function unit tests for decide_scope/check_shift_limit (no mock needed)"
    - "ADAPT-05: compliance threshold from validate_session_vs_actual tool result, not hardcoded literal"
    - "TRANSP-01: adaptation explanation text echoes tool-sourced values; trust corpus proves scanner passes them"
key_files:
  created:
    - api/routes/adaptations.py
  modified:
    - api/main.py
    - tests/api/test_adaptations.py
    - tests/agent/fixtures/trust_corpus.py
decisions:
  - "Pydantic body model (UserIdBody) instead of Body(str, ...) for JSON POST endpoints to correctly parse {user_id: ...} objects"
  - "detect_signals: compliance threshold 60 is the tool's compliance_pct from validate_session_vs_actual; not a hardcoded literal"
  - "macro replan capacity_ratio: progress_load recommended_ctl / current_ctl; cold-start fallback 0.8"
  - "30% guard uses >0.30 (strict greater than) per D-19"
metrics:
  duration: 5min
  completed: 2026-06-20T09:37:53Z
  tasks_completed: 2
  files_changed: 4
---

# Phase 3 Plan 05: Adaptive Re-planning and Transparency Layer Summary

Closed the coaching loop: signal detection (missed sessions and underperformance), micro/macro decision with 30% shift guard, weekly check endpoint, adaptation log, and cited-value transparency. Every plan change is persisted to the adaptations table and traceable to tool results.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Signal detection, micro/macro decision, 30% shift guard, adaptation logging | 8470c28 | api/routes/adaptations.py, api/main.py |
| 2 | Fill adaptation tests, extend trust corpus for TRANSP-01 | dd4d874 | tests/api/test_adaptations.py, tests/agent/fixtures/trust_corpus.py |

## What Was Built

**api/routes/adaptations.py** (720 lines):
- `detect_signals(user_id, window_days=7)`: missed-session check (past-due planned + no ride within +/-1 day) and underperformance check via `validate_session_vs_actual` (ADAPT-01, ADAPT-05)
- `decide_scope(signals)`: None / "micro" / "macro" for 0 / 1 / 2+ signals (ADAPT-02)
- `check_shift_limit(before, after)`: 30% guard, returns `requires_user_confirmation` when shift_pct > 0.30 (ADAPT-03)
- `log_adaptation(...)`: INSERT into adaptations table with trigger/scope/snapshots/explanation_text (TRANSP-02)
- `apply_micro_adjustment(user_id, signal)`: reduce next 1-3 sessions to 80% intensity, logs adaptation
- `apply_macro_replan(user_id, signals)`: calls `progress_load` for CTL target (ADAPT-05), runs shift guard, returns needs_confirmation if >30% shift (D-19), otherwise applies and logs
- `GET /adaptations/` (TRANSP-03): readable adaptation log, filtered by user_id, newest first
- `POST /adaptations/check` (ADAPT-04): weekly check independent of uploads
- `POST /adaptations/sessions/{id}/missed` (D-16): mark one session missed + re-run detection

**api/main.py**: adaptations_router registered at `/adaptations` prefix; onboarding and rides routers unchanged.

**tests/api/test_adaptations.py**: 8 tests covering ADAPT-01 through ADAPT-05, TRANSP-02, TRANSP-03.

**tests/agent/fixtures/trust_corpus.py**: 2 ATTRIBUTED entries added for adaptation explanations citing TSS/CTL from tool results (TRANSP-01).

## Verification

- `python -m pytest tests/api/test_adaptations.py tests/agent/test_trust_corpus.py -q` passes (47 tests)
- `python -m pytest tests/ -x -q` passes (189 tests; TRUST-02 holds)
- `/adaptations` routes present in app.routes
- `detect_signals` calls `validate_session_vs_actual` (6 occurrences in adaptations.py)
- `adaptations` table referenced 13 times in adaptations.py (TRANSP-02)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed POST /adaptations/check body parsing**

- **Found during:** Task 2 test run
- **Issue:** `user_id: str = Body(...)` requires a bare JSON string body, but the test (and idiomatic API) sends `{"user_id": "..."}` JSON object. FastAPI returned 422 with "Input should be a valid string".
- **Fix:** Replaced `Body(str, ...)` with a Pydantic model `UserIdBody(user_id: str)` for `check_adaptations` and `MissedSessionBody` for `mark_session_missed`. This follows the same pattern used by `onboarding.py`.
- **Files modified:** api/routes/adaptations.py
- **Commit:** dd4d874

## Known Stubs

None. All endpoints implement their full intended behavior. Adaptation numbers flow from tool results, not hardcoded placeholders.

## Threat Flags

No new security surface introduced beyond the plan's threat model. All three new endpoints have `# TODO(phase-4-auth)` markers consistent with prior waves. Reads are user_id-scoped; writes use SERVICE_ROLE_KEY.

## Self-Check: PASSED

- `api/routes/adaptations.py`: FOUND (720 lines, > 90 minimum)
- `tests/api/test_adaptations.py`: FOUND
- Commit 8470c28: FOUND
- Commit dd4d874: FOUND
- All acceptance criteria verified via automated checks
- 189 tests pass
