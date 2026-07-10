# Deferred Items — Phase 03 (Coaching Loop)

Out-of-scope issues discovered during plan execution but not fixed (per SCOPE BOUNDARY rule).

## From Plan 03-06

- **`tests/agent/test_sse.py::TestSSEEventSequence` — 8 pre-existing failures, out of scope.**
  Confirmed via `git diff <wave-start-base> -- tests/agent/test_sse.py` that this
  plan's changes to the file are additions only (two new mock generators, one new
  `TestAssistantSinkGating` class) with zero lines removed or modified in the
  existing `TestSSEEventSequence` class, and confirmed by running the full suite
  against the unmodified base commit before making any change, so these failures
  predate 03-06 and are not caused by this plan's changes. All 8 fail identically:
  `GET /chat/stream` now requires a verified Supabase JWT via `get_current_user`
  (added in commit `b3fcf39`, 2026-07-02, part of the 260702-wev quick-task fix
  logged in STATE.md), but these tests call the endpoint with no `Authorization`
  header and no `?token=` query param, so every request returns 401 instead of the
  assertions' expected status/behavior (e.g. `test_sse_requires_conversation_id`
  expects 422 for a missing `conversation_id`, gets 401 first). This is the exact
  same failure signature already tracked in
  `.planning/phases/06-core-loop-persistence/deferred-items.md` and
  `.planning/phases/07-deploy-consolidation/deferred-items.md`, and is already
  scoped to Phase 10 (Hygiene and Safety Nets) per STATE.md's Roadmap Evolution
  section ("stale tests" line item).
  Not fixed here per the scope boundary rule (only auto-fix issues directly
  caused by the current task's changes) -- fixing it would mean adding JWT
  fixtures (mirroring `tests/api/conftest.py`'s `make_test_token`/`auth_headers`
  pattern) to 8 test functions unrelated to CR-01/WR-06, a separate task.
  This plan's two new regression tests (`test_sink_not_appended_on_error_terminated_turn`,
  `test_sink_appended_on_normal_completion`) sidestep the issue entirely by
  driving `sse_generator` directly rather than through the HTTP endpoint, per
  the plan's own instructions.
