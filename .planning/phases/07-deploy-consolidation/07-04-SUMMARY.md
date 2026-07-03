---
phase: 07-deploy-consolidation
plan: 04
subsystem: infra
tags: [vercel, deploy, routing, fastapi, vite, services, env-vars, security]

# Dependency graph
requires:
  - phase: 07-deploy-consolidation
    provides: RESEARCH.md Pattern 1 (Vercel services split), threat model, validation strategy
provides:
  - Restructured vercel.json using Vercel's `services` model (frontend static service + backend Python service)
  - api/index.py slimmed to the /api mount only (SPA-serving code removed)
  - Fixed backend service root scoping so the sibling backend/ package is actually importable
  - Full Vercel Production + Preview env-var parity (CALENDAR_FERNET_KEY, SUPABASE_JWT_SECRET, ANTHROPIC_MODEL, BACKEND_BASE_URL added)
  - Fixed a live security issue: VITE_SUPABASE_ANON_KEY had been set to the service_role key (RLS-bypass credential exposed client-side)
  - Verified preview deploy: routing, env parity, and SSE streaming all confirmed working
  - Railway service decommissioned by the user (account owner action, outside agent capability)
affects: [deployment, ci-cd, routing, security]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Vercel `services` config (not the deprecated `experimentalServices`) for polyglot monorepo routing: services.<name>.root + entrypoint (module:app), top-level rewrites with destination.service"
    - "A services.<name>.root of anything narrower than repo root EXCLUDES sibling directories from that service's build — a Python service needs root at the level that contains every package it imports, not just its own entrypoint file's directory"

key-files:
  created: []
  modified:
    - vercel.json
    - api/index.py
    - .gitignore
  deleted:
    - frontend/vercel.json

key-decisions:
  - "Used Vercel `services` (not `experimentalServices`) after verifying against live docs — services is the current, non-deprecated schema; experimentalServices is what it replaced"
  - "Kept api/index.py's app.mount(\"/api\", _backend_app) wrapper — confirmed via docs that a service receives the ORIGINAL request path, so the /api prefix must be stripped inside the service"
  - "Changed services.backend.root from \"api/\" to \".\" (repo root) with entrypoint \"api.index:app\" (dotted module path) — root scoped to api/ excluded the sibling backend/ package entirely, causing ModuleNotFoundError on every /api/* request in production. Confirmed via Vercel runtime logs, fixed, and re-verified via a clean rebuild plus live traffic."
  - "Generated a fresh CALENDAR_FERNET_KEY rather than sourcing an existing one — confirmed via direct DB query (0 of 3 users have any stored calendar tokens) that no existing encrypted data depends on a prior key, so a fresh key is safe."
  - "Set BACKEND_BASE_URL to https://www.pacer.moorelabs.uk/api (not the bare domain) — backend/routes/calendar.py builds the OAuth redirect_uri as {BACKEND_BASE_URL}/calendar/callback, and the calendar router is mounted at /api/calendar, so the base must include /api or the redirect 404s."
  - "Deferred Google Calendar OAuth redirect-URI verification and functional testing per explicit user direction — Google's OAuth consent screen is not yet approved for production, so real users cannot complete the flow regardless; revisit once Google approves the app (tracked separately, not blocking this phase)."

requirements-completed: [DEPLOY-ROUTE-01, DEPLOY-SSE-01, DEPLOY-RAIL-02]

duration: ~3h (across three sessions: Task 2 restructure, Task 3 automation attempt + reconciliation, Task 3 completion with live debugging)
completed: 2026-07-03
status: complete
---

# Phase 07 Plan 04: Vercel services restructure + preview verification + Railway decommission — Summary

**Root vercel.json restructured to Vercel's `services` model (frontend static + backend Python), a critical backend-import bug found and fixed via live preview testing, full env-var parity established across Production and Preview (including a live security fix), preview deploy verified end-to-end (routing + SSE), and the Railway service decommissioned.**

## Accomplishments

### Task 2: Routing restructure
- Restructured root `vercel.json`: `services.frontend` (root `frontend/`, `buildCommand: npm run build`, `outputDirectory: dist`) + `services.backend`; top-level `rewrites` route `/api/(.*)` → backend, `/(.*)` → frontend
- Deleted orphaned `frontend/vercel.json`
- Removed the SPA-serving workaround from `api/index.py` (StaticFiles mount, dist-resolution logic, catch-all route); retained `app.mount("/api", _backend_app)`

### Task 3: Preview verification, bug fix, env parity, Railway decommission

**Critical bug found and fixed:** The initial `services.backend.root: "api/"` scoped the backend service's build to only the `api/` directory, excluding the sibling `backend/` Python package entirely. Every `/api/*` request in the first preview deploy returned `500` with `ModuleNotFoundError: No module named 'backend'` (confirmed via Vercel runtime logs). Fixed by changing `root` to `.` (repo root) and `entrypoint` to `"api.index:app"` (dotted module path). Verified via a forced clean rebuild and live traffic — zero errors across all subsequent requests.

**Env-var parity established (Production and Preview):**
- Added: `SUPABASE_JWT_SECRET`, `ANTHROPIC_MODEL` (`claude-sonnet-5`), `BACKEND_BASE_URL` (`https://www.pacer.moorelabs.uk/api`), `CALENDAR_FERNET_KEY` (freshly generated — confirmed no existing encrypted calendar tokens depend on a prior key)
- Copied to Preview (previously had zero env vars, making any preview test impossible): `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `VITE_SUPABASE_URL`

**Security fix (found during this task, not pre-planned):** `VITE_SUPABASE_ANON_KEY` in Production had been set to a JWT whose payload decoded to `"role":"service_role"` — the actual service-role (RLS-bypass) credential, not the anon key. Since `VITE_`-prefixed vars ship to the client bundle, this meant the RLS-bypass key was exposed to every browser. Caught before this deploy went live; replaced with a verified `"role":"anon"` key in both Production and Preview.

**Preview deploy verification (human-confirmed + server-log-confirmed):**
- Routing: homepage loads the SPA, `/api/*` reaches FastAPI, random paths fall back to the SPA (not a raw 404/traceback) — user-confirmed via browser (SSO deployment-protection blocks unauthenticated curl checks, so this required the account owner's own login)
- SSE: chat streamed and completed correctly. User reported a "connecting error" after several messages; cross-checked against Vercel runtime logs for the same window — all `/api/chat/stream` calls returned `200` with clean Anthropic + Supabase completions and zero server-side errors/warnings. This is a frontend-side SSE-handling issue, not a deploy/routing regression — it matches ROADMAP.md Phase 9's already-scoped "chat recovers from SSE errors" goal, not something introduced by this phase.
- Env parity: confirmed via `vercel env ls` after all additions

**Railway decommission:** performed by the user (account owner) in the Railway dashboard, per explicit confirmation — outside agent capability (no Railway CLI/API access in this session, and deleting a live service is an irreversible action requiring the account owner directly).

**Google Calendar scope decision:** per explicit user direction, calendar OAuth redirect-URI verification and functional testing were deferred rather than pursued — Google's OAuth consent screen for this app is not yet approved for production use, so real users cannot complete the calendar-connect flow regardless of deploy correctness. No code changes were made to disable/feature-flag calendar; it is simply out of scope for this deploy's verification, to be revisited once Google approves the app.

## Task Commits

1. **Task 1: Pre-flight — confirm `services` availability and current Framework Preset** — checkpoint, no commit (resolved: Framework Preset FastAPI, `services` confirmed current and available on all plans)
2. **Task 2: Restructure vercel.json, delete frontend/vercel.json, strip SPA-serving from api/index.py** — `731690f`
3. **Task 3: Verify preview deploy and decommission Railway** — this commit (fixes backend root/entrypoint bug; env-var and security work was applied directly to the live Vercel project via CLI, not represented as file diffs since it's infrastructure config, not repo state)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `services.backend.root` scoping excluded the backend package, causing 500s on every /api/* route**
- **Found during:** Task 3, first preview deploy — user reported "Could not reach the server," cross-checked against Vercel runtime logs which showed `ModuleNotFoundError: No module named 'backend'` on every request
- **Fix:** Changed `services.backend.root` from `"api/"` to `"."`, `entrypoint` from `"index:app"` to `"api.index:app"`. Verified via forced clean rebuild (`vercel deploy --force`) and confirmed zero import errors on subsequent live traffic.
- **Files modified:** `vercel.json`
- **Verification:** Runtime logs for the corrected deployment show `200` responses with successful Supabase + Anthropic calls on `/api/chat/stream`, `/api/profiles/me`, and no error/warning-level log entries in the post-fix window.

**2. [Rule 3 - Blocking, security] `VITE_SUPABASE_ANON_KEY` was set to the service-role key, not the anon key**
- **Found during:** Task 3, while collecting env-var values from the user for the parity check — the value supplied as the "anon key" decoded to `"role":"service_role"`, identical to the value separately supplied as `SUPABASE_SERVICE_ROLE_KEY`
- **Fix:** Flagged to the user before writing anything; user supplied the corrected anon-role JWT; replaced the Production value (removed + re-added, since Vercel "Sensitive" vars can't be updated in place) and added the correct value to Preview.
- **Files modified:** none (Vercel env var only, not repo state)
- **Impact:** This was a live exposure — a full RLS-bypass credential in the client bundle — not something this plan was scoped to look for, but should have been caught before any deploy shipped with it.

---

**Total deviations:** 2 auto-fixed (1 blocking functional bug, 1 blocking security issue), both found through actual live-deploy verification rather than static review — validates why Task 3 was a required checkpoint rather than something safe to skip or fabricate.
**Impact on plan:** No scope creep on repo changes — `vercel.json`'s root/entrypoint fields are the only additional file-level change beyond what Task 2 already touched. The env-var and security work is infrastructure configuration (Vercel project settings), not application code.

## User Setup Required (completed during this session)

- All missing Vercel Production + Preview env vars added: `SUPABASE_JWT_SECRET`, `ANTHROPIC_MODEL`, `BACKEND_BASE_URL`, `CALENDAR_FERNET_KEY`, plus Preview's copies of `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY` corrected in both environments
- Railway project decommissioned by the user

## Follow-ups Not Addressed (out of scope, noted for later)

- Google Calendar OAuth redirect-URI verification against the new `BACKEND_BASE_URL` — deferred until Google approves the production OAuth consent screen (tracked as pre-existing per project memory, not a Phase 7 gap)
- Frontend chat SSE "connecting error" after multiple messages — confirmed NOT a backend/deploy issue via server logs (all requests 200, zero errors); matches ROADMAP.md Phase 9's already-planned "chat recovers from SSE errors" scope
- `FRONTEND_URL` not yet copied to Preview environment — only affects CORS (safe localhost fallback) and calendar (out of scope this phase); not needed for routing/SSE verification

## Next Phase Readiness

**Complete.** All `must_haves` satisfied:
- `/api/*` reaches the Python function and returns FastAPI responses — verified (logs + user confirmation)
- Non-API paths serve the static SPA — verified
- `api/index.py` no longer serves the SPA; `/api` mount retained — verified
- `frontend/vercel.json` deleted; root `vercel.json` is the single routing source — verified
- SSE streams correctly within Vercel function limits — verified via server logs (zero premature cutoffs, all 200s)
- Live Railway service decommissioned — user-confirmed

---
*Phase: 07-deploy-consolidation*
*Status: complete*
