# Deferred Items

Out-of-scope issues discovered during plan execution but not fixed (per SCOPE BOUNDARY rule).

## From Plan 06-04

- `tests/agent/test_sse.py` (8 tests) and `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields` fail on a clean checkout of `main` (verified pre-existing, unrelated to `backend/routes/adaptations.py`, `backend/sports_science/compliance.py`, or `tests/api/test_adaptations.py`). Not touched by this plan; out of scope.
