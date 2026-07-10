---
phase: 10-hygiene-safety-nets
plan: 01
subsystem: testing
tags: [pytest, httpx, sse, jwt, supabase, contract-testing]

# Dependency graph
requires:
  - phase: 08-trust-model-integrity
    provides: CR-03 conversation-ownership check (_resolve_conversation_id) that the 8 stale SSE tests predate
  - phase: 09-frontend-resilience
    provides: duration_secs/avg_power field-name fixes that this plan's contract tests now guard
provides:
  - Green backend test suite (0 failures across 333 tests, up from 8 failures in test_sse.py)
  - profile.py test-reset seam closing a latent module-singleton leak (parity with capability_gap.py)
  - tests/api/test_contracts.py: drift-detecting field-presence guards for rides/sessions/profile
affects: [10-02, 10-03, ci-phase, verify-work]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Test-only ownership-check bypass via monkeypatch.setattr(module, '_resolve_conversation_id', ...) for tests exercising mechanics unrelated to ownership"
    - "Module-singleton test-reset seam (_reset_client_for_tests) wired into an autouse conftest fixture"
    - "Subset field-presence contract assertion (required <= set(body.keys())) instead of exact-equality, so backend can add columns without breaking the guard"

key-files:
  created:
    - tests/api/test_contracts.py
  modified:
    - tests/agent/test_sse.py
    - backend/sports_science/profile.py
    - tests/sports_science/conftest.py

key-decisions:
  - "Applied all three coordinated SSE test fixes together (auth headers + ownership-check bypass + **kwargs on mock run_turn), per RESEARCH.md Pattern 1 — auth headers alone were verified insufficient"
  - "profile.py's _reset_client_for_tests() is a preventive parity fix (no test currently exercises the leak) rather than a reactive bugfix, matching capability_gap.py's existing pattern exactly"
  - "test_contracts.py asserts field presence by name via subset comparison, not exact equality or value assertions, so future backend column additions never break the guard"

patterns-established:
  - "Pattern 1: SSE test auth = monkeypatch.setenv(SUPABASE_JWT_SECRET) + headers=auth_headers() + ownership-check bypass + **kwargs on all mock run_turn signatures"
  - "Pattern 2: Module-singleton reset seam mirrored 1:1 across sibling modules sharing the same _get_async_supabase cache pattern"

requirements-completed: [ITEM-01, ITEM-02, ITEM-04]

coverage:
  - id: D1
    description: "8 previously-failing SSE tests in tests/agent/test_sse.py now pass with real auth headers, a test-only ownership-check bypass, and **kwargs on all mock run_turn signatures; production code untouched"
    requirement: "ITEM-01"
    verification:
      - kind: unit
        ref: "tests/agent/test_sse.py -q (10 passed, includes the previously-failing 8)"
        status: pass
    human_judgment: false
  - id: D2
    description: "backend/sports_science/profile.py gains _reset_client_for_tests(), wired into the existing autouse fixture in tests/sports_science/conftest.py, closing a latent module-singleton leak class matching capability_gap.py's pre-fix pattern"
    requirement: "ITEM-02"
    verification:
      - kind: unit
        ref: "tests/sports_science/ tests/agent/test_tools_phase3.py -q (120 passed)"
        status: pass
    human_judgment: false
  - id: D3
    description: "tests/api/test_contracts.py adds three field-presence contract guards (rides/sessions/profile) verified to fail when a required field is dropped from a mocked row"
    requirement: "ITEM-04"
    verification:
      - kind: unit
        ref: "tests/api/test_contracts.py -q (3 passed)"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-08
status: complete
---

# Phase 10 Plan 01: Backend Test Hygiene and Contract Guards Summary

**Fixed all 8 stale-auth SSE test failures with three coordinated changes, closed a latent Supabase-client singleton leak in profile.py, and added a new field-presence contract test suite that would have caught the Phase 6-9 Ride/Profile/FTP-key field-name mismatches.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-08T18:50:00Z
- **Completed:** 2026-07-08T19:15:00Z
- **Tasks:** 3
- **Files modified:** 4 (1 new, 3 modified)

## Accomplishments

- All 8 previously-401ing tests in `tests/agent/test_sse.py`'s `TestSSEEventSequence` class now pass by exercising the real endpoint with valid JWT auth, a test-only bypass of the CR-03 conversation-ownership check, and `**kwargs` added to every mock `run_turn` signature so it accepts the `user_id`/`conversation_id` kwargs `sse_generator` now always forwards. Production code (`backend/routes/chat.py`) is untouched, confirmed via an empty `git diff`.
- `backend/sports_science/profile.py` gained an identical `_reset_client_for_tests()` seam to `capability_gap.py`'s, wired into the existing autouse fixture in `tests/sports_science/conftest.py` — a preventive parity fix for a latent module-singleton leak class (no test currently exercises it, but it matches the exact pre-fix shape `capability_gap.py` once had).
- New `tests/api/test_contracts.py` adds three targeted field-presence contract tests (`test_rides_contract`, `test_sessions_today_contract`, `test_profile_me_contract`) hitting real routes with a mocked Supabase layer, asserting by name (subset comparison, not exact equality) that the exact fields `frontend/src/lib/api.ts` reads are present in each response. Verified live (temporarily dropped `tss` from the mocked ride row, confirmed the test failed, then reverted) that the guard actually detects drift rather than passing vacuously.
- Full backend suite (`pytest tests/ -q`) went from 322 passed / 8 failed to 333 passed / 0 failed (322 baseline + 8 fixed + 3 new contract tests).

## Task Commits

Each task was committed atomically:

1. **Task 1: Fix the 8 stale SSE tests in tests/agent/test_sse.py** - `10a4bb1` (fix)
2. **Task 2: Add profile.py test-reset seam and wire it into the sports_science autouse fixture** - `3a5dde3` (fix)
3. **Task 3: Add tests/api/test_contracts.py — targeted field-presence guards (D-01)** - `e0186d2` (test)

**Plan metadata:** (this commit)

## Files Created/Modified

- `tests/agent/test_sse.py` - Added `TEST_JWT_SECRET`/`auth_headers` import, a `_bypass_resolve` test-only ownership-check bypass, `**kwargs` on all 4 mock `run_turn` functions, and auth headers + bypass wiring on 7 of the 8 tests (the 422 test needed auth only, no bypass)
- `backend/sports_science/profile.py` - New `_reset_client_for_tests()` function mirroring `capability_gap.py`'s identical pattern
- `tests/sports_science/conftest.py` - Extended the existing `_reset_capability_gap_client` autouse fixture to also reset `profile`'s singleton (before and after each test)
- `tests/api/test_contracts.py` (NEW) - Three contract tests: rides, sessions/today, profiles/me field-presence guards

## Decisions Made

- Applied all three SSE fixes together in a single pass (not incrementally) since RESEARCH.md's Pitfall 1 explicitly verified that auth-headers-alone produces a different, confusing failure mode (`invalid_conversation_id` error frame) rather than the original 401.
- Used a local `_mock_supabase_factory_extended` helper in `test_contracts.py` (chaining `eq`/`gte`/`order`/`limit`) rather than the base `mock_supabase_factory` from `tests/api/conftest.py`, because `GET /rides/` chains `.limit(50)` which the base factory does not support — mirrors the existing `mock_supabase_factory_extended` pattern already established in `tests/api/test_sessions.py`.
- Kept the profile.py fix as a pure preventive parity measure with zero behavior change, exactly matching the existing `capability_gap.py` seam rather than inventing a new reset mechanism.

## Deviations from Plan

None - plan executed exactly as written. All three tasks matched their `<action>` specifications precisely; no Rule 1-4 deviations were needed.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Backend suite is fully green (333/333) with a drift-detecting contract net in place for the 3 endpoints that have broken before.
- Ready for the remaining Phase 10 items (SSE token exchange, rate limiting, CI, repo cleanup) in subsequent plans within this phase.
- No blockers identified.

## Self-Check: PASSED

- FOUND: tests/agent/test_sse.py
- FOUND: backend/sports_science/profile.py
- FOUND: tests/sports_science/conftest.py
- FOUND: tests/api/test_contracts.py
- FOUND: .planning/phases/10-hygiene-safety-nets/10-01-SUMMARY.md
- FOUND commit 10a4bb1 (Task 1)
- FOUND commit 3a5dde3 (Task 2)
- FOUND commit e0186d2 (Task 3)
- `.venv/bin/pytest tests/agent/test_sse.py -q` → 10 passed
- `.venv/bin/pytest tests/sports_science/ tests/agent/test_tools_phase3.py -q` → 120 passed
- `.venv/bin/pytest tests/api/test_contracts.py -q` → 3 passed
- `.venv/bin/pytest tests/ -q` → 333 passed, 0 failed

---
*Phase: 10-hygiene-safety-nets*
*Completed: 2026-07-08*
