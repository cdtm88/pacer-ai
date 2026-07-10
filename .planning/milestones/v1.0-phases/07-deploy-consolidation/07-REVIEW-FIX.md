---
phase: 07-deploy-consolidation
fixed_at: 2026-07-03T20:30:00Z
review_path: .planning/phases/07-deploy-consolidation/07-REVIEW.md
iteration: 1
findings_in_scope: 10
fixed: 10
skipped: 0
status: all_fixed
---

# Phase 7: Code Review Fix Report

**Fixed at:** 2026-07-03T20:30:00Z
**Source review:** .planning/phases/07-deploy-consolidation/07-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 10 (2 critical, 8 warning; fix_scope=critical_warning, so IN-01/IN-02 were excluded)
- Fixed: 10
- Skipped: 0

## Fixed Issues

### CR-01: Unbounded sequential inline-awaited Google Calendar calls risk function timeout

**Files modified:** `backend/calendar_sync.py`, `vercel.json`
**Commit:** ba81e9a
**Applied fix:** `push_all_sessions_to_calendar` now pushes sessions concurrently under an `asyncio.Semaphore(5)` (bounding Google API concurrency) instead of a fully sequential loop, capping aggregate latency instead of stacking `N * CALENDAR_API_TIMEOUT_SECS`. Also added an explicit `"maxDuration": 60` to the `backend` service in `vercel.json` so the function timeout budget is a deliberate, known value rather than the platform default.

### CR-02: `calendar_event_id` never selected in adaptations.py — `update_calendar_event` is dead code

**Files modified:** `backend/routes/adaptations.py`, `tests/api/test_adaptations.py`
**Commit:** 365c148
**Applied fix:** Added `calendar_event_id` to the sessions `SELECT` column list in both `apply_micro_adjustment` and `apply_macro_replan`, so `after_sessions` now carries the column downstream to `check_adaptations`/`mark_session_missed`'s calendar-sync loop. Added two new regression tests (`test_apply_micro_adjustment_retains_calendar_event_id`, `test_apply_macro_replan_retains_calendar_event_id`) that call the real (unmocked) functions and assert both the SELECT column list and the returned `after` sessions retain `calendar_event_id` — closing the exact test gap the review identified (prior tests monkeypatched these functions wholesale). All 25 tests in `tests/api/test_adaptations.py` pass.

### WR-01: `confirm_macro_replan` never syncs the calendar

**Files modified:** `backend/routes/adaptations.py`
**Commit:** 660f2f6
**Applied fix:** After the per-session `UPDATE` loop in `confirm_macro_replan`, added a calendar-sync block mirroring `check_adaptations`/`mark_session_missed`, using `proposed_sessions`' `calendar_event_id` (now populated once CR-02 landed) to call `update_calendar_event`. Existing `test_confirm_macro_applies_stored_snapshot` test (whose fixture proposal has no `calendar_event_id`) continues to pass unaffected.

### WR-02: Missing `user_id` dual-filter on two session UPDATE calls

**Files modified:** `backend/routes/adaptations.py`
**Commit:** 2f538f4
**Applied fix:** Added `.eq("user_id", user_id)` to the session `UPDATE` calls in `apply_micro_adjustment` and the apply-branch of `apply_macro_replan`, matching the dual-filter defence-in-depth pattern used everywhere else in the file.

### WR-03: `_parse_date`'s strptime loop is dead/no-op logic

**Files modified:** `backend/routes/adaptations.py`
**Commit:** 7a3d18d
**Applied fix:** Removed the broken `strptime` loop (which sliced by format-string length, not value length, so every attempt always raised) and now parse directly via `datetime.fromisoformat(val.replace("Z", "+00:00")).date()`, matching what the fallback already did in practice.

### WR-04: Nondeterministic `primary_trigger` / `signal_types` ordering

**Files modified:** `backend/routes/adaptations.py`
**Commit:** 197a9ca
**Applied fix:** Replaced `list({s.get("type") for s in signals})` with `list(dict.fromkeys(s.get("type") for s in signals))` at both call sites in `apply_macro_replan`, preserving first-seen order instead of relying on Python's hash-randomization-dependent set iteration order.

### WR-05: Stale comment in `api/index.py` contradicts the actual `vercel.json` entrypoint

**Files modified:** `api/index.py`
**Commit:** 7c0dfa4
**Applied fix:** Updated the comment to cite the actual entrypoint value (`services.backend.entrypoint = "api.index:app"`) instead of the stale `"index:app"`.

### WR-06 / WR-07: README.md Tech Stack table drift and missing `/api` prefix on documented endpoints

**Files modified:** `README.md`
**Commit:** 887cfa3
**Applied fix:** Combined into one commit since both edits land in the same file in tightly adjacent/overlapping regions (splitting them would have required an artificial intermediate broken state). Rewrote the "Backend" Tech Stack table row (Railway/Docker/Gunicorn/SQLAlchemy/Alembic -> Vercel Python Runtime, `supabase` client + raw SQL migrations), corrected the local-dev command (`uvicorn api.main:app` -> `uvicorn backend.main:app`, since the FastAPI app lives at `backend/main.py`), added a note to the API Endpoints section clarifying that every listed path is reached via the `/api` prefix in production (per `vercel.json`'s rewrite + `api/index.py`'s `/api` mount), and corrected the adjacent Vite-proxy description to match (`/api/*` paths, prefix-stripped) for internal consistency.

### WR-08: `onboarding_start` accepts a client-supplied `conversation_id` without ownership or format validation

**Files modified:** `backend/routes/onboarding.py`, `tests/api/test_onboarding.py`
**Commit:** f9d9c3a
**Applied fix:** Added `_resolve_conversation_id(user_id, conversation_id)`, which validates UUID format via `backend.utils.validate_uuid` (catching its `HTTPException` rather than propagating it) and verifies ownership via a `SELECT id FROM conversations WHERE id=... AND user_id=...` existence check; either failure falls back to treating the id as absent (matching the already-documented "when absent, a new conversation is created" behavior) instead of writing orphaned/mismatched message rows. Wired into `onboarding_start` in place of the raw `body.conversation_id` passthrough. Added three new unit tests covering malformed-id, foreign-id, and owned-id paths; all 8 tests in `tests/api/test_onboarding.py` pass.

## Skipped Issues

None — all in-scope findings were fixed.

## Out of Scope (not attempted)

IN-01 (no `.vercelignore`) and IN-02 (duplicated `signal_types` computation) are Info-severity and were excluded by `fix_scope=critical_warning`.

## Verification Notes

- Tier 2 syntax checks (`python -c "import ast; ast.parse(...)"`, `node -e "JSON.parse(...)"`) passed for every modified `.py`/`.json` file.
- `tests/api/test_adaptations.py` (25 tests) and `tests/api/test_onboarding.py` (8 tests) pass in full after all fixes, including the 5 new regression tests added.
- 8 pre-existing failures in `tests/agent/test_sse.py` were confirmed present on the unmodified `main` branch before any fix was applied (unrelated to any file touched in this fix pass) and are not introduced by this work.
- No finding in this pass was classified by the review as a logic-error requiring `"fixed: requires human verification"` status; all fixes are mechanical (missing SELECT column, missing filter clause, dead code removal, deterministic ordering, comment/doc corrections, added validation) and are covered by passing tests.

---

_Fixed: 2026-07-03T20:30:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
