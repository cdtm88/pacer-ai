---
phase: 10-hygiene-safety-nets
fixed_at: 2026-07-08T15:52:00Z
review_path: .planning/phases/10-hygiene-safety-nets/10-REVIEW.md
iteration: 1
findings_in_scope: 4
fixed: 4
skipped: 0
status: all_fixed
---

# Phase 10: Code Review Fix Report

**Fixed at:** 2026-07-08
**Source review:** .planning/phases/10-hygiene-safety-nets/10-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 4 (CR-01, WR-01, WR-02, WR-03; fix_scope=critical_warning, IN-01/IN-02 skipped by scope)
- Fixed: 4
- Skipped: 0

## Fixed Issues

### CR-01: The CI workflow added by this phase fails immediately (`ruff check .` has 237 pre-existing/introduced errors)

**Files modified:** `api/index.py`, `backend/agent/loop.py`, `backend/agent/tools.py`, `backend/agent/trust.py`, `backend/auth.py`, `backend/calendar_sync.py`, `backend/main.py`, `backend/routes/adaptations.py`, `backend/routes/calendar.py`, `backend/routes/chat.py`, `backend/routes/onboarding.py`, `backend/routes/rides.py`, `backend/routes/sessions.py`, `backend/sports_science/__init__.py`, `backend/sports_science/capability_gap.py`, `backend/sports_science/constants.py`, `backend/sports_science/ftp.py`, `backend/sports_science/metrics.py`, `backend/sports_science/plan.py`, `backend/sports_science/pmc.py`, `backend/sports_science/profile.py`, `backend/sports_science/types.py`, `backend/sports_science/zones.py`, `tests/agent/conftest.py`, `tests/agent/fixtures/trust_corpus.py`, `tests/agent/test_audit.py`, `tests/agent/test_loop.py`, `tests/agent/test_sdk_contract.py`, `tests/agent/test_sse.py`, `tests/agent/test_tools_phase3.py`, `tests/agent/test_trust.py`, `tests/agent/test_trust_corpus.py`, `tests/api/conftest.py`, `tests/api/test_adaptations.py`, `tests/api/test_auth.py`, `tests/api/test_calendar.py`, `tests/api/test_chat.py`, `tests/api/test_chat_token.py`, `tests/api/test_contracts.py`, `tests/api/test_onboarding.py`, `tests/api/test_rides.py`, `tests/api/test_sessions.py`, `tests/sports_science/test_capability_gap.py`, `tests/sports_science/test_compliance.py`, `tests/sports_science/test_ftp.py`, `tests/sports_science/test_load.py`, `tests/sports_science/test_metrics.py`, `tests/sports_science/test_plan.py`, `tests/sports_science/test_pmc.py`, `tests/sports_science/test_types.py`, `tests/sports_science/test_zones.py`, `tests/sports_science/test_zwo.py`
**Commit:** `3a3ffd7`
**Applied fix:** Chose option 1 from the review's fix guidance (repo-wide cleanup, not scoping/exclusion) so the CI ruff gate reflects a real bar rather than an accepted-debt carve-out. Ran `ruff check . --fix` for safe auto-fixes (import sorting/unused-import removal), then manually resolved every remaining `E501` (line-too-long), `E402` (`backend/main.py`'s `load_dotenv()` sat between import blocks; moved it after all imports since no module-level code reads env vars at import time -- confirmed via grep that all `os.environ.get` calls are inside function bodies) and `F841` (unused-variable) finding across the repo, wrapping long lines/dicts/calls or renaming genuinely-dead locals with a leading underscore per the file's own idiom. Verified `ruff check .` exits 0 and the full `pytest tests/ -q` suite (343 tests) still passes after every batch of edits, and again after the full set.

### WR-03: `get_current_user`'s `sse_token` branch can raise an unhandled `KeyError` instead of falling through cleanly

**Files modified:** `backend/auth.py`
**Commit:** `b09b310`
**Applied fix:** Replaced the plain `sse_payload["sub"]` dict indexing with `sse_payload.get("sub")` plus an explicit `if sub:` guard; when `sub` is missing, execution now falls through to the existing Supabase verification path (matching the function's documented "on any failure, fall through unchanged" contract) instead of raising `KeyError`. Reproduced the review's exact repro (`jwt.encode({"aud": "authenticated", "typ": "sse_token", "exp": ...}, SSE_TOKEN_SECRET, algorithm="HS256")` then `get_current_user`) and confirmed no `KeyError` is raised post-fix -- it now falls through and raises the expected downstream `HTTPException` instead.

### WR-01: `tests/agent/test_sse.py` is missing the rate-limit-log reset fixture added to its sibling test files, making it order-dependent

**Files modified:** `tests/agent/conftest.py`
**Commit:** `0768c0f`
**Applied fix:** Added the same `autouse=True` `_reset_rate_limit_log` fixture pattern already used in `tests/api/test_chat.py`, `tests/api/test_onboarding.py`, and `tests/api/test_rate_limit.py`, scoped to `tests/agent/conftest.py` so it covers all of `tests/agent/test_sse.py`'s tests automatically. Verified by running `pytest tests/agent/test_sse.py tests/api -q` and the reverse order `pytest tests/api tests/agent/test_sse.py -q` -- both pass now, confirming `test_sse.py` is self-contained rather than relying on sibling test files' teardown running first.

### WR-02: The new CI workflow never runs the Playwright e2e suite this phase modified

**Files modified:** `.github/workflows/ci.yml`
**Commit:** `04d65cf`
**Applied fix:** Added a new `e2e` job to the CI workflow that installs Playwright's Chromium browser (`npx playwright install --with-deps chromium`) and runs `npm run test:e2e`. Confirmed `frontend/playwright.config.ts` already has a `webServer` block that boots its own Vite dev server (`npx vite --mode test --port 5174`), and that both `full-uat.spec.ts` and `phase4.spec.ts` mock all backend calls via `page.route(...)`, so the new job needs no live backend and is self-sufficient in CI. Validated the resulting YAML parses correctly and the `e2e` job/step definitions are well-formed.

## Skipped Issues

None -- all 4 in-scope findings (CR-01, WR-01, WR-02, WR-03) were fixed. IN-01 and IN-02 were excluded per `fix_scope=critical_warning` and were not attempted.

---

_Fixed: 2026-07-08_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
