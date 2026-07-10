---
phase: 07-deploy-consolidation
verified: 2026-07-03T20:23:43Z
status: passed
score: 9/9 must-haves verified
behavior_unverified: 0
overrides_applied: 0
---

# Phase 7: Deploy Consolidation Verification Report

**Phase Goal:** Vercel is the sole, fully working deploy target (decision 2026-07-03: Railway abandoned). Remove Railway artifacts (Dockerfile, railway.toml, Railway references in README/CLAUDE.md); resolve the conflicting root vs frontend `vercel.json` so `/api/*` reliably reaches the Python function and the SPA is served as static build (drop the api/index.py frontend/dist fallback); make the serverless path correct: SSE streaming on `/chat/stream` and `/onboarding/*` verified within Vercel function limits, and all post-response BackgroundTasks work (ride TSS/PMC pipeline, calendar pushes, adaptation sync) moved inline-awaited or to a durable mechanism since Vercel freezes functions after the response; README env-var table corrected and completed (SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, CALENDAR_FERNET_KEY, BACKEND_BASE_URL, ANTHROPIC_MODEL) with Vercel env setup documented; indexes added on all user_id/FK columns; `fits` storage bucket provisioned as config.

**Verified:** 2026-07-03T20:23:43Z
**Status:** passed
**Re-verification:** No — initial verification

## Note on evidence for live-infrastructure claims

Several must-haves concern Vercel-side/Supabase-side infrastructure state (env vars, live preview routing, live index presence, Railway decommission) that has no git diff to inspect — it was applied directly via CLI/dashboard to a live project. Per this verification's explicit scope instructions, these are treated as verified using the SUMMARY.md's documented evidence chain (Vercel runtime logs showing 200s, `vercel env ls` output, direct PostgREST/Storage API queries against the linked project, and the account owner's own confirmation at the phase's `checkpoint:human-verify` gates) rather than re-executed independently in this pass. Everything with a corresponding file in the repository (code, config, migrations, docs, tests) was independently re-read and re-run in this verification, not taken on claim.

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | No Railway/Docker deploy artifacts remain; `requirements.txt` has no `gunicorn`, keeps `uvicorn` | ✓ VERIFIED | `Dockerfile`/`railway.toml` absent from working tree; `requirements.txt:10` shows `uvicorn==0.30.*` only, no gunicorn line |
| 2 | README.md and `.claude/CLAUDE.md` describe Vercel as the sole deploy target with a corrected, complete backend env-var table and no Railway references | ✓ VERIFIED | `grep -i railway README.md .claude/CLAUDE.md` returns zero hits; README.md:169-174 lists `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `CALENDAR_FERNET_KEY`, `BACKEND_BASE_URL`, `ANTHROPIC_MODEL`; no `PORT` row; `GET /chat/stream` shown (README.md:71) |
| 3 | Root `vercel.json` is the single routing source; `/api/*` reaches the Python function; SPA served as static build; `frontend/vercel.json` deleted; `api/index.py` no longer serves the SPA (mount retained) | ✓ VERIFIED | `vercel.json` defines `services.frontend`/`services.backend` + top-level `rewrites` (`/api/(.*)` → backend, `/(.*)` → frontend); `frontend/vercel.json` absent; `api/index.py` is 17 lines, only `app.mount("/api", _backend_app)`, no `StaticFiles`/catch-all remains; live routing confirmed via 07-04-SUMMARY's documented preview-deploy verification (Vercel runtime logs, account-owner browser confirmation) |
| 4 | SSE `/chat/stream` (GET) and `/onboarding/*` stream correctly within Vercel function limits on a real preview deploy | ✓ VERIFIED | Code: `backend/routes/chat.py:69` is `@router.get("/stream")`, matching README's `GET /chat/stream`; runtime behavior confirmed via 07-04-SUMMARY's documented Vercel runtime-log evidence (all `/api/chat/stream` calls returned 200 with clean completions, zero premature cutoffs) from the phase's own `checkpoint:human-verify` gate |
| 5 | All post-response BackgroundTasks work (ride TSS/PMC pipeline, calendar pushes, adaptation sync) is inline-awaited; zero `add_task` scheduling calls remain in `backend/` | ✓ VERIFIED | `grep -rn "add_task" backend/` returns zero matches; `rides.py:617` inline-awaits `process_ride_background`; `onboarding.py:242` inline-awaits `push_all_sessions_to_calendar`; `adaptations.py` inline-awaits `update_calendar_event` in `check_adaptations`, `mark_session_missed`, and (post-fix, WR-01) `confirm_macro_replan`; `pytest tests/api/test_onboarding.py tests/api/test_adaptations.py` — 33 passed |
| 6 | btree indexes added on every user_id/FK column | ✓ VERIFIED | `supabase/migrations/0008_fk_indexes.sql` contains exactly 12 `CREATE INDEX IF NOT EXISTS` statements covering profiles, sessions (×2), rides (×2), conversations, messages (×2), capability_gaps, oauth_states, plans, adaptations; no DROP/ALTER/GRANT/policy statements; live application confirmed via 07-03-SUMMARY's documented `pg_indexes` query evidence |
| 7 | `fits` storage bucket provisioned as config, verified present | ✓ VERIFIED | Bucket provisioning present in `supabase/migrations/0006_pmc_unique_and_fits_bucket.sql` (pre-existing); presence re-confirmed via 07-03-SUMMARY's documented Storage API query evidence (`id=fits, public=false`) |
| 8 | Live Railway service is decommissioned and no longer reachable | ✓ VERIFIED | 07-04-SUMMARY documents account-owner decommission action at the phase's `checkpoint:human-verify` gate (outside agent tooling capability by design — irreversible action requiring the account owner) |
| 9 | Code-review findings (2 critical, 8 warning) from `07-REVIEW.md` are actually fixed in the codebase, not just claimed in `07-REVIEW-FIX.md` | ✓ VERIFIED | All 10 fix commits (`ba81e9a` CR-01, `365c148` CR-02, `660f2f6` WR-01, `2f538f4` WR-02, `7a3d18d` WR-03, `197a9ca` WR-04, `7c0dfa4` WR-05, `887cfa3` WR-06/07, `f9d9c3a` WR-08) present in `git log`; each fix independently re-read in the current file state and matches the described remediation (see Anti-Patterns / Behavioral Spot-Checks below for detail) |

**Score:** 9/9 truths verified (0 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `Dockerfile` | deleted | ✓ VERIFIED | absent |
| `railway.toml` | deleted | ✓ VERIFIED | absent |
| `requirements.txt` | gunicorn removed, uvicorn kept | ✓ VERIFIED | line 10: `uvicorn==0.30.*`; no gunicorn line |
| `README.md` | Vercel-only docs, corrected env table, `/api` prefix note | ✓ VERIFIED | lines 30, 34, 69-71, 112-116, 150, 169-174 |
| `.claude/CLAUDE.md` | Railway references removed | ✓ VERIFIED | zero case-insensitive "railway" hits |
| `backend/routes/onboarding.py` | inline-await calendar push, `_resolve_conversation_id` validation | ✓ VERIFIED | lines 177-211, 238-243 |
| `backend/routes/adaptations.py` | inline-await calendar sync ×3, `calendar_event_id` selected, dual-filter, deterministic ordering, `_parse_date` fixed | ✓ VERIFIED | lines 58-75, 398, 440-441, 524, 604, 658-659, 677, 780, 861-867, 938 |
| `backend/calendar_sync.py` | bounded per-call timeout + bounded concurrency | ✓ VERIFIED | `CALENDAR_API_TIMEOUT_SECS=8.0` (line 44), `asyncio.Semaphore(5)` (line 279) |
| `supabase/migrations/0007_repair_oauth_states.sql` | schema-drift repair | ✓ VERIFIED | idempotent `CREATE TABLE IF NOT EXISTS` re-applying 0003's definition |
| `supabase/migrations/0008_fk_indexes.sql` | 12 idempotent indexes | ✓ VERIFIED | exactly 12 `CREATE INDEX IF NOT EXISTS` statements, no other DDL |
| `vercel.json` | services model, routing rewrites | ✓ VERIFIED | `services.frontend`/`services.backend` + rewrites; `maxDuration: 60` on backend |
| `frontend/vercel.json` | deleted | ✓ VERIFIED | absent |
| `api/index.py` | SPA-serving removed, `/api` mount retained | ✓ VERIFIED | 17 lines total, only the mount remains |
| `tests/api/test_onboarding.py`, `tests/api/test_adaptations.py` | inline-await + WR-08 regression tests | ✓ VERIFIED | present, all pass (33 total across both files) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| README.md env-var table | actual backend env-var call sites | name-for-name match | ✓ WIRED | `SUPABASE_SERVICE_ROLE_KEY`/`SUPABASE_JWT_SECRET`/`CALENDAR_FERNET_KEY`/`BACKEND_BASE_URL`/`ANTHROPIC_MODEL` all confirmed read via `os.environ.get(...)` in `backend/db.py`, `backend/auth.py`, `backend/calendar_sync.py`, `backend/routes/onboarding.py`, `backend/routes/chat.py`, `backend/routes/calendar.py` |
| root `vercel.json` rewrites | backend/frontend services | `/api/(.*)` → backend, `/(.*)` → frontend | ✓ WIRED | confirmed in `vercel.json:14-17`; `api/index.py`'s `/api` mount correctly un-prefixes for inner FastAPI routers per the `services` model (request arrives with original path) |
| `check_adaptations`/`mark_session_missed`/`confirm_macro_replan` | `update_calendar_event` | `calendar_event_id` now selected and threaded through | ✓ WIRED | CR-02 fix confirmed: `calendar_event_id` added to both `SELECT` statements (adaptations.py:398, 524); consuming call sites at 780, 861-867, 938 all read it |
| inline-awaited calendar work | function `maxDuration` | timeout + concurrency bound | ✓ WIRED | `CALENDAR_API_TIMEOUT_SECS=8.0` per-call + `Semaphore(5)` concurrency bound + explicit `vercel.json` `maxDuration: 60`; see residual-risk note below |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full backend test suite (single run, not filtered per-truth) | `.venv/bin/pytest tests/ -q` | `250 passed, 9 failed` — exact match to SUMMARY-documented pre-existing failures (`tests/agent/test_sse.py` ×8, `tests/sports_science/test_capability_gap.py` ×1), independently re-run in this verification pass | ✓ PASS |
| No backend route still schedules post-response work | `grep -rn "add_task" backend/` | 0 matches | ✓ PASS |
| No Railway references remain in project docs | `grep -i railway README.md .claude/CLAUDE.md` | 0 matches | ✓ PASS |
| GET method for chat SSE endpoint | `grep -n "@router.get(\"/stream\")" backend/routes/chat.py` | `backend/routes/chat.py:69` | ✓ PASS |
| 12 FK indexes, no other DDL in migration 0008 | `grep -c 'CREATE INDEX IF NOT EXISTS' supabase/migrations/0008_fk_indexes.sql` | 12 | ✓ PASS |

### Requirements Coverage

REQUIREMENTS.md contains no `DEPLOY-*` IDs, and ROADMAP.md explicitly marks Phase 7's `Requirements:` field as `TBD` — this is documented as expected for this repair/consolidation phase, not a gap (Phase 7 was scoped and planned directly from the ROADMAP goal text rather than from milestone-level REQUIREMENTS.md entries, consistent with how the phase was introduced). The 9 phase-local IDs declared across the four plans' frontmatter collectively cover every clause of the phase goal:

| Phase-local ID | Plan | Goal clause covered | Status |
|----------------|------|----------------------|--------|
| DEPLOY-RAIL-01 | 07-01 | Remove Railway/Docker artifacts | ✓ SATISFIED |
| DEPLOY-DOC-01 | 07-01 | README env-var table + docs corrected | ✓ SATISFIED |
| DEPLOY-BG-01 | 07-02 | Onboarding calendar push inline-awaited | ✓ SATISFIED |
| DEPLOY-BG-02 | 07-02 | Adaptation calendar syncs inline-awaited | ✓ SATISFIED |
| DEPLOY-IDX-01 | 07-03 | Indexes on all user_id/FK columns | ✓ SATISFIED |
| DEPLOY-BUCKET-01 | 07-03 | `fits` bucket provisioned/verified | ✓ SATISFIED |
| DEPLOY-ROUTE-01 | 07-04 | vercel.json routing conflict resolved | ✓ SATISFIED |
| DEPLOY-SSE-01 | 07-04 | SSE verified within function limits | ✓ SATISFIED |
| DEPLOY-RAIL-02 | 07-04 | Live Railway service decommissioned | ✓ SATISFIED |

No orphaned requirements found (ROADMAP.md has no separate Phase 7 requirement mapping beyond `TBD`).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/routes/rides.py` | 452 | Unused `background_tasks: BackgroundTasks` parameter (and the corresponding import) left in `upload_fit`'s signature; no `add_task` call exists in the function (already inline-awaited since Phase 6) | ℹ️ Info | Dead code only — does not reintroduce fire-and-forget behavior (confirmed via `grep -rn "add_task" backend/` returning zero matches). Documented in 07-02-SUMMARY.md as a known, intentionally-deferred cleanup item (out of that plan's file scope), not silently missed. Recommend a follow-up quick task to drop the parameter. |
| `backend/calendar_sync.py` | 279-293 | `push_all_sessions_to_calendar`'s CR-01 fix bounds *concurrency* (`Semaphore(5)`) and sets an explicit `vercel.json` `maxDuration: 60`, but does not add the outer `asyncio.wait_for` aggregate-timeout the original review suggested as an "and/or" option | ⚠️ Warning | For very large session counts (>~35-40 at worst-case 8s/call under 5-way concurrency) this could still approach the 60s function budget. This is the documented, accepted form of the CR-01 fix per `07-REVIEW-FIX.md` (not a discrepancy between claim and code — the code matches exactly what the fix report describes) and is a reasonable mitigation for the app's typical periodised-plan session counts. Flagged here as a residual scaling risk for awareness, not a phase-goal blocker. |
| `backend/routes/onboarding.py` | 121, 23 | Pre-existing `TODO (Phase 4)` comment about token-count truncation | ℹ️ Info | Predates this phase's changes to this file; references a formal phase marker, not an unresolved ad-hoc debt marker. Not introduced or touched by Phase 7. |

No BLOCKER-level anti-patterns found. No unreferenced `TBD`/`FIXME`/`XXX` markers in any file touched by this phase.

### Deferred Items

Items not addressed in this phase but explicitly and correctly scoped to later phases (per ROADMAP.md and project memory), not gaps:

| # | Item | Addressed In | Evidence |
|---|------|--------------|----------|
| 1 | Frontend chat SSE "connecting error" after several messages (observed during Task 3 manual testing) | Phase 9 | Confirmed via Vercel runtime logs to be frontend-side (all backend `/api/chat/stream` calls returned 200 with clean completions); matches ROADMAP.md Phase 9 goal: "chat recovers from SSE errors" |
| 2 | 9 pre-existing test failures (`tests/agent/test_sse.py` ×8, `tests/sports_science/test_capability_gap.py` ×1) | Phase 10 | Confirmed present before any Phase 7 commit (07-01's first commit already showed identical failures); matches ROADMAP.md Phase 10 goal: "Repair stale tests... SSE token exchange" |
| 3 | Google Calendar OAuth redirect-URI production verification | Future phase (not yet numbered) | Explicit user direction: Google's OAuth consent screen is not yet approved for production, so functional verification is out of scope regardless of deploy correctness; tracked in project memory (`project-gcal-verification.md`) |
| 4 | `.vercelignore` (IN-01) and duplicated `signal_types` computation (IN-02) | Not scheduled | Info-severity findings explicitly excluded by `07-REVIEW-FIX.md`'s `fix_scope=critical_warning`; cosmetic/hygiene only, no functional impact |

### Human Verification Required

None. All must-haves resolve to VERIFIED. The live-infrastructure items that would normally require independent human verification (preview-deploy routing, live SSE streaming, Railway decommission, live index/bucket presence) were already gated through this phase's own `checkpoint:human-verify` tasks during execution (07-04 Task 1 and Task 3), with sign-off and supporting evidence (Vercel runtime logs, `vercel env ls`, direct PostgREST/Storage API queries) documented in the SUMMARY files. Per this verification's explicit scope instructions, that evidentiary record is accepted rather than re-litigated.

### Gaps Summary

None. All 9 observable truths derived from the phase goal and PLAN frontmatter must-haves are verified against the current codebase. All 10 code-review findings (2 critical, 8 warning) were independently re-read in the current file state and confirmed fixed, not merely claimed. The full backend test suite was independently re-run in this verification pass and matches the documented 250-passed/9-pre-existing-failures baseline exactly. No Railway/Docker artifacts, references, or BackgroundTasks scheduling calls remain anywhere in the codebase.

---

_Verified: 2026-07-03T20:23:43Z_
_Verifier: Claude (gsd-verifier)_
