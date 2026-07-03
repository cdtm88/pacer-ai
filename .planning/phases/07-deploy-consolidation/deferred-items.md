# Deferred Items — Phase 07 Deploy Consolidation

Items discovered during execution that are out of scope for the current plan (pre-existing, unrelated to the files this plan touches). Logged, not fixed, per executor scope-boundary rule.

## From 07-01 (docs/config-only plan)

- `pytest tests/ -q` was run as the plan's overall-verification step and found **9 pre-existing failures** unrelated to this plan's scope (only `Dockerfile`, `railway.toml`, `requirements.txt`, `README.md`, `.claude/CLAUDE.md` were touched — no Python source changed):
  - `tests/agent/test_sse.py::TestSSEEventSequence` — 8 failing tests (content type, frame format, event ordering, token data field, done-data shape, no-live-call guard, conversation_id requirement)
  - `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields` — mock assertion failure (`table` mock called 0 times instead of once)
  - Confirmed pre-existing via `git diff <plan-base>..HEAD --stat`: no files under `tests/`, `backend/`, or `api/` were modified by this plan.
  - Likely relevant to Phase 07's own scope (RESEARCH.md flags `tests/agent/test_sse.py` as the regression test for `DEPLOY-SSE-01`), so a later plan in this phase (07-02/07-03/07-04, which touch SSE/BackgroundTasks/routing) should investigate and fix rather than this docs-only plan.
