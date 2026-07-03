---
phase: 07-deploy-consolidation
plan: 04
subsystem: infra
tags: [vercel, deploy, routing, fastapi, vite, services]

# Dependency graph
requires:
  - phase: 07-deploy-consolidation
    provides: RESEARCH.md Pattern 1 (Vercel services split), threat model, validation strategy
provides:
  - Restructured vercel.json using Vercel's `services` model (frontend static service + backend Python service)
  - api/index.py slimmed to the /api mount only (SPA-serving code removed)
  - Live-docs-verified correction of the Task 1 checkpoint's schema guidance
affects: [deployment, ci-cd, routing]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Vercel `services` config (not the deprecated `experimentalServices`) for polyglot monorepo routing: services.<name>.root + entrypoint (module:app), top-level rewrites with destination.service"

key-files:
  created: []
  modified:
    - vercel.json
    - api/index.py
  deleted:
    - frontend/vercel.json

key-decisions:
  - "Used Vercel `services` (not `experimentalServices`) after verifying against live docs — services is the current, non-deprecated schema; experimentalServices is what it replaced"
  - "Kept api/index.py's app.mount(\"/api\", _backend_app) wrapper — confirmed via docs that a service receives the ORIGINAL request path, so the /api prefix must be stripped inside the service"

requirements-completed: []  # Task 3 (preview deploy verification + Railway decommission) not yet complete; plan is NOT done

duration: ~25min (this continuation session, Task 2 only)
completed: 2026-07-03
status: blocked
---

# Phase 07 Plan 04: Vercel services restructure Summary (Task 2 of 3 — Task 3 checkpoint pending)

**Root vercel.json restructured to Vercel's `services` model (frontend static + backend Python), correcting an incorrect schema from the Task 1 checkpoint resolution after live-docs verification.**

**This plan is NOT complete.** Task 3 (checkpoint:human-verify — real preview deploy verification of routing/SSE, env-var parity check, and Railway decommission) has not been attempted, per explicit instruction not to fabricate or skip it. This SUMMARY documents Task 1's corrected resolution and Task 2's completed work so the finding survives the handoff to whichever agent resumes at Task 3.

## Performance

- **Tasks this session:** 1 of 3 (Task 2; Task 1 was resolved by a prior agent, Task 3 remains a blocking checkpoint)
- **Files modified:** 3 (1 modified vercel.json, 1 modified api/index.py, 1 deleted frontend/vercel.json)

## Critical correction to the Task 1 checkpoint resolution

The prior agent's Task 1 resolution (relayed into this session's prompt) concluded that Vercel's current schema is `experimentalServices` (with `entrypoint` + `routePrefix`), superseding RESEARCH.md Pattern 1's `services`/`rewrites` schema. **This was backwards.** Live Vercel documentation, fetched and verified directly in this session (`vercel.com/docs/services`, `/docs/services/routing`, `/docs/services/config-reference`; `dateModified: 2026-06-16`, matching RESEARCH.md's citation date), states explicitly:

> "Looking for the earlier `experimentalServices` configuration? See Experimental Services. The `services` model described here replaces it for new projects."

So `experimentalServices` is the **deprecated predecessor**, and `services` (RESEARCH.md Pattern 1's schema) is **current and correct**. Key facts confirmed directly from the docs:

- **Availability:** "Services are available in Beta on all plans" — not gated behind a paid tier (consistent with what the prior agent observed, but the schema itself must be `services`, not `experimentalServices`).
- **Schema:** `services.<name>.root` (required), `.entrypoint` (e.g. `"index:app"` for a Python ASGI app — module:attribute), `.buildCommand`/`.outputDirectory`/etc. Top-level `rewrites` use `"destination": { "service": "<name>" }`. No `routePrefix` field exists anywhere in the current or reference docs.
- **Path-prefix behavior (resolves the ambiguity Task 1 flagged as needing investigation):** "The service receives the original request path. `GET /api/users` reaches `my_backend` as `/api/users`, not `/users`." This confirms `api/index.py`'s `app.mount("/api", _backend_app)` wrapper must be **kept** — it is what strips the `/api` prefix for the inner FastAPI routers, exactly as RESEARCH.md Pattern 1 originally stated.

This session proceeded with the `services` schema (matching RESEARCH.md Pattern 1) and treated the Task 1 resolution's `experimentalServices` recommendation as superseded by this direct verification, per the plan's own instruction: "Get this right before writing — a wrong shape produces a broken preview deploy."

## Accomplishments

- Restructured root `vercel.json`: `services.frontend` (root `frontend/`, `buildCommand: npm run build`, `outputDirectory: dist`) + `services.backend` (root `api/`, `entrypoint: index:app`); top-level `rewrites` route `/api/(.*)` → backend, `/(.*)` → frontend
- Deleted orphaned `frontend/vercel.json` (routing is now owned solely by the root config)
- Removed the SPA-serving workaround from `api/index.py`: the `StaticFiles` `/assets` mount, `_DIST_CANDIDATES`/`DIST` resolution logic, and the `@app.get("/{full_path:path}")` catch-all, plus their now-unused imports (`logging`, `StaticFiles`, `FileResponse`, `JSONResponse`)
- Retained `api/index.py`'s `app.mount("/api", _backend_app)` wrapper, with an updated comment explaining why (services routing model passes the original path)

## Task Commits

1. **Task 1: Pre-flight — confirm `services` availability and current Framework Preset** — checkpoint, no commit (resolved by prior agent as "services AVAILABLE, Framework Preset: FastAPI"; this session corrected the schema guidance within that resolution)
2. **Task 2: Restructure vercel.json, delete frontend/vercel.json, strip SPA-serving from api/index.py** — `731690f` (feat)

## Files Created/Modified

- `vercel.json` — restructured to the `services` model (frontend + backend services, top-level rewrites)
- `api/index.py` — SPA-serving code removed; `/api` mount retained with updated comment
- `frontend/vercel.json` — deleted (orphaned/conflicting config)

## Decisions Made

- **Corrected schema key:** used `services` (current, non-deprecated) instead of `experimentalServices` (deprecated predecessor named in the Task 1 resolution), based on direct live-docs verification in this session. See "Critical correction" section above for full evidence.
- **Kept the `/api` mount in `api/index.py`:** confirmed via docs that services receive the original (unstripped) request path.
- **Did not move or touch `requirements.txt`** (still at repo root, not under `api/`): Vercel's zero-config Python dependency detection already worked with this exact layout before this change (current production uses `api/index.py` with root-level `requirements.txt`); no documentation was found stating `services.backend.root` changes where `requirements.txt` is discovered, and changing this without evidence risked breaking the build in a way local verification cannot catch. **This is an explicit assumption that Task 3's preview-deploy verification must confirm** — if `/api/health` fails to build/return FastAPI JSON on the preview deploy, check whether the backend service's Python dependency install found `requirements.txt`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking, per plan's own explicit re-verification instruction] Corrected the routing schema from `experimentalServices` to `services`**
- **Found during:** Start of Task 2, before writing any config
- **Issue:** The Task 1 checkpoint resolution (produced by a prior agent/orchestrator) asserted `experimentalServices` was the current schema and that it superseded RESEARCH.md Pattern 1's `services` schema. Live documentation verification showed this was backwards — `experimentalServices` is deprecated, `services` is current.
- **Fix:** Verified directly against `vercel.com/docs/services`, `/docs/services/routing`, and `/docs/services/config-reference` (fetched via curl in this session); wrote `vercel.json` using the `services` schema per RESEARCH.md Pattern 1, with the `/api` mount retained in `api/index.py`.
- **Files modified:** `vercel.json`, `api/index.py`
- **Verification:** `test ! -e frontend/vercel.json && python -c "import ast,sys; ast.parse(open('api/index.py').read())"` passed; manual review of fetched doc pages confirmed schema fields (`root`, `entrypoint`, `framework`, `runtime`, `buildCommand`, `outputDirectory`, etc.) and routing behavior (original path preserved)
- **Committed in:** `731690f`

---

**Total deviations:** 1 auto-fixed (Rule 3 — corrected a blocking schema error before it could produce a broken preview deploy)
**Impact on plan:** Necessary correction; the plan itself explicitly instructed re-verifying the schema before writing rather than trusting Task 1's resolution at face value. No scope creep — files touched match the plan's `files_modified` list exactly.

## Issues Encountered

- Vercel MCP tools (`mcp__plugin_vercel_vercel__*`) were not reachable as directly-callable tools in this session's toolset (only `Read`, `Write`, `Edit`, `Bash`, `Skill` were available). Fell back to `curl` + HTML-stripping against `vercel.com/docs/services`, `/docs/services/routing`, and `/docs/services/config-reference` directly, per the plan's fallback instruction ("use WebFetch against vercel.com/docs/services instead" — no `WebFetch` tool was available either, so `curl` was used as the next-level fallback). All three doc pages were successfully fetched and their content confirmed against each other (config reference field list matches the schema used in both the overview and routing pages' examples).
- This worktree's actual path/branch (`agent-a4e4ee65676969f98`) did not match the continuation prompt's stated worktree (`agent-a5dafa12be1c0f7ce`, which does not exist on disk). Proceeded on the actual environment worktree after confirming it is on a valid `worktree-agent-*` branch, is at the correct phase-plan commit with no prior commits (consistent with "Task 1 made no file changes"), and contains the correct `07-04-PLAN.md`. Flagged for the orchestrator in the completion report.

## User Setup Required

Not yet applicable — Task 1's `user_setup` items (Vercel dashboard `services` confirmation, env-var parity check) were partially covered by the prior agent's Task 1 investigation (Framework Preset + `services` availability confirmed). The env-var parity check and the Railway decommission step are part of Task 3, still pending.

## Next Phase Readiness

**Not ready — Task 3 checkpoint blocks completion.** Task 3 requires:
1. A real Vercel preview deploy of this branch.
2. `curl` verification that `/api/health` returns FastAPI JSON, `/` returns the static SPA with CDN/static headers (not FastAPI headers), and a random path returns the static SPA (not source leakage).
3. Manual verification that SSE (`/onboarding/start`, `/chat/stream`) streams correctly on the preview deploy.
4. Confirmation that all backend env vars (including `CALENDAR_FERNET_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`) are present in Vercel Production, and no `BACKEND_BASE_URL`/`FRONTEND_URL` still points at `*.railway.app`.
5. Only after 1-4 pass: decommission the live Railway project (irreversible, requires the account owner's own dashboard access) and confirm its URL is unreachable.

This is a genuine human-in-the-loop gate — none of it can be automated or fabricated by an executor agent.

---
*Phase: 07-deploy-consolidation*
*Status: blocked at Task 3 checkpoint (2/3 tasks done)*
