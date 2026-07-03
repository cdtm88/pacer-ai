# Deferred Items — Phase 06 (Core Loop Persistence)

Out-of-scope issues discovered during plan execution but not fixed (per SCOPE BOUNDARY rule).

## From Plan 06-02

- **`tests/agent/test_sse.py` — 8 pre-existing failures, out of scope.**
  Confirmed via `git show 644c090:tests/agent/test_sse.py` that the file is
  byte-identical to the wave-start base commit (no diff), so these failures
  predate 06-02 and are not caused by this plan's changes. Failures are auth
  related (expects 422 for missing `conversation_id`, gets 401; SSE frame/event
  assertions fail alongside). Tracked under Phase 10 (Hygiene and Safety Nets)
  in STATE.md's Roadmap Evolution section.
  Not fixed here per the scope boundary rule (only auto-fix issues directly
  caused by the current task's changes).

- **`tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields`
  — order-dependent pre-existing failure, out of scope.** Passes in isolation
  but fails when run as part of the full `tests/agent/ tests/sports_science/`
  suite (test-pollution / shared module-singleton leakage between test files,
  unrelated to 06-02). Confirmed present with 06-02's Task 2 changes fully
  reverted via `git apply -R`, so this predates this plan. Not fixed here per
  the scope boundary rule.

## From Plan 06-04

- `tests/agent/test_sse.py` (8 tests) and `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields` fail on a clean checkout of `main` (verified pre-existing, unrelated to `backend/routes/adaptations.py`, `backend/sports_science/compliance.py`, or `tests/api/test_adaptations.py`). Not touched by this plan; out of scope.
