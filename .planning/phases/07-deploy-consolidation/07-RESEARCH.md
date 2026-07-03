# Phase 7: Deploy Consolidation - Research

**Researched:** 2026-07-03
**Domain:** Vercel deployment consolidation (Python/FastAPI serverless + static SPA), serverless background-work migration, DB indexing, deploy documentation
**Confidence:** HIGH (all findings verified against the live codebase and current Vercel docs; no CONTEXT.md existed for this research pass)

## Summary

This is a repair/consolidation phase over an already-deployed app, not greenfield work. Railway was abandoned 2026-07-03 (STATE.md decision); Vercel is now the sole target. Direct codebase inspection found: (1) a real, load-bearing conflict between `vercel.json` (root) and `frontend/vercel.json` caused by Vercel's FastAPI Framework Preset routing 100% of non-matched traffic through the single Python function, which is why `api/index.py` was forced to grow its own SPA-serving/static-file-fallback logic as a production workaround (commit `260702-ulq`); (2) three live `BackgroundTasks` call sites remain unsafe under Vercel's freeze-after-response model (calendar push in onboarding, two calendar-event updates in adaptations) — the ride-processing pipeline was already fixed to inline-await in Phase 6 (`06-05-PLAN.md`), and this phase must apply the identical, already-proven pattern to the three remaining sites; (3) the `fits` storage bucket is **already** provisioned as config via migration `0006_pmc_unique_and_fits_bucket.sql` — this roadmap item is done, not pending; (4) zero `CREATE INDEX` statements exist anywhere across all 6 migrations — every FK/user_id column relies on no index except `pmc_history` (which got a composite unique constraint in 0006); (5) the README env-var table is stale in multiple ways (wrong key name `SUPABASE_SERVICE_KEY` instead of `SUPABASE_SERVICE_ROLE_KEY`, four vars entirely undocumented, and the whole "Backend: Railway" deployment section needs replacing); (6) the project's own root `.claude/CLAUDE.md` also declares Railway as part of the architecture and must be corrected alongside README.md.

**Primary recommendation:** Adopt Vercel's `services` feature (GA per docs, last updated 2026-06-16) to formally split the deployment into a `frontend` static-build service and a `backend` Python service, replacing the ad-hoc rewrites-vs-Framework-Preset conflict. Convert the three remaining `BackgroundTasks` call sites to inline-await, exactly matching the pattern Phase 6 already proved safe and correct for `rides.py`. Add btree indexes on every FK/user_id column in a new migration. Rewrite the README deploy + env-var sections and correct the project CLAUDE.md's stale Railway references.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| SPA static asset serving | CDN / Static (Vercel service) | — | Should be served directly by Vercel's static hosting, not proxied through the Python function (phase goal explicitly requires dropping the Python-side fallback) |
| `/api/*` request routing | API / Backend (Vercel Python service) | Routing config (vercel.json) | FastAPI app is the sole owner of business logic; vercel.json only decides which requests reach it |
| SSE streaming (`/chat/stream`, `/onboarding/*`) | API / Backend | — | Must run inside the same Python function as the rest of the API; Vercel's Python runtime supports streaming natively via ASGI `StreamingResponse` |
| Post-response work (calendar push/sync, PMC recompute) | API / Backend (inline-awaited) | — | No durable queue exists in this stack; FastAPI `BackgroundTasks` is unsafe under Vercel's freeze-after-response model, so this work must complete before the response is sent |
| DB indexing | Database / Storage | — | Pure schema concern; owned entirely by Supabase migrations |
| Env var documentation | N/A (docs) | — | Cross-cutting; must reflect both tiers accurately |

## User Constraints

No CONTEXT.md exists for this phase (user chose to skip `/gsd-discuss-phase`). Constraints below are derived from ROADMAP.md phase text and STATE.md decisions, which function as the locked scope for this research.

### Locked Decisions (from ROADMAP.md / STATE.md)
- Vercel is the sole, fully working deploy target (STATE.md decision, 2026-07-03). Railway is abandoned.
- Remove Railway artifacts: `Dockerfile`, `railway.toml`, Railway references in README/CLAUDE.md.
- Resolve the conflicting root vs. `frontend/vercel.json` so `/api/*` reliably reaches the Python function and the SPA is served as a static build; **drop the `api/index.py` frontend/dist fallback** (i.e., stop serving the SPA from inside the Python function).
- SSE streaming on `/chat/stream` and `/onboarding/*` must be verified within Vercel function limits.
- All post-response `BackgroundTasks` work (ride TSS/PMC pipeline, calendar pushes, adaptation sync) must move to inline-awaited or a durable mechanism, since Vercel freezes functions after the response.
- README env-var table must be corrected and completed: `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `CALENDAR_FERNET_KEY`, `BACKEND_BASE_URL`, `ANTHROPIC_MODEL`, with Vercel env setup documented.
- Indexes added on all `user_id`/FK columns.
- `fits` storage bucket provisioned as config.

### Claude's Discretion
- Exact mechanism for the vercel.json restructuring (Services vs. classic split) — resolved below with a concrete recommendation.
- Exact resolution of the inline-await vs. durable-mechanism question — resolved below: **inline-await**, not a durable queue.
- Migration numbering/filename for the new index migration.
- Whether to also correct the stale endpoint list and "POST /chat/stream" typo in README (actual method is GET) — in scope as part of general README deploy-doc correction, since the phase goal already mandates a README pass.

### Deferred Ideas (OUT OF SCOPE)
- None explicitly deferred in ROADMAP.md for this phase; general hygiene items (root `node_modules`, `test-ride.fit`, root `.gitignore` cleanup, CI, rate limiting) are explicitly assigned to **Phase 10**, not this phase. Do not pull them forward.
- Trust-model/audit-log work is explicitly **Phase 8**. Do not pull it forward.

## Phase Requirements

No REQ-IDs are mapped to Phase 7 in REQUIREMENTS.md (marked "TBD" in ROADMAP.md — this is a repair/consolidation phase, not tied to v1 requirement IDs). The phase instead repairs infrastructure that all completed-phase requirements (CAL-01..04, AGENT-05, FIT-04/05, TRANSP-02, etc.) depend on at runtime. Treat the ROADMAP.md goal paragraph itself as the requirements source; each clause below maps to a concrete finding/plan area.

| Goal-text clause | Research Support |
|----|-------------|
| Remove Railway artifacts | Confirmed exact file list: `Dockerfile`, `railway.toml`, README.md (3 sections), `.claude/CLAUDE.md` (5 locations), `requirements.txt` (`gunicorn`, arguably `uvicorn` if unused outside Docker) |
| Resolve root vs frontend vercel.json conflict | Root cause identified: FastAPI Framework Preset makes the whole app one function; `services` feature is the current (2026-06) documented fix |
| SSE within Vercel function limits | Both SSE endpoints found and read; both already use ASGI `StreamingResponse`, which Vercel's Python runtime explicitly supports |
| BackgroundTasks -> inline-await | All 3 remaining call sites found and read; both target functions already swallow their own errors (CAL-04-safe to inline-await) |
| README env-var table | Full diff computed between documented vars and actual `os.environ.get(...)` call sites |
| DB indexes on user_id/FK columns | Full column inventory built from all 6 migrations; zero indexes found anywhere except the incidental one from the 0006 unique constraint |
| `fits` bucket provisioned as config | **Already done** — migration `0006_pmc_unique_and_fits_bucket.sql` provisions it. No further plan work needed; verify only. |

## Standard Stack

### Core
| Tool | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Vercel CLI | 54.18.1 (installed locally, verified) | Local deploy/dev, `vercel dev`, service routing | Required >= 48.1.8 for the FastAPI entrypoint model and `services` routing used in this phase; installed version far exceeds minimum [VERIFIED: local `vercel --version`] |
| Vercel Python Runtime | current (3.12 default; 3.13/3.14 available) | Executes the FastAPI app as a Vercel Function | Official, zero-config ASGI support; already in use [CITED: vercel.com/docs/functions/runtimes/python] |
| Vercel `services` | GA, `services` key in `vercel.json` (docs last updated 2026-06-16; replaces the older `experimentalServices`) | Split one Vercel project into a static frontend service + a Python backend service under one routing table | Directly matches the phase's literal requirement ("SPA served as static build", "/api/* reliably reaches the Python function") without hand-rolled Python-side static serving [CITED: vercel.com/docs/services] |

**No new packages are installed in this phase.** This is a configuration/removal/migration phase.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `services` (split frontend/backend) | Keep the current single-function model (Python serves the SPA via `StaticFiles` + catch-all, as shipped in commit `260702-ulq`) | Already working in production today; zero migration risk. But it directly contradicts the phase goal's explicit instruction to "drop the api/index.py frontend/dist fallback," and every non-API request pays a Python cold-start/invocation cost instead of being served from Vercel's static CDN. Keep as documented fallback only if `services` turns out to be unavailable on the account's plan (see Package/Feature Legitimacy note below). |
| Inline-await for background work | A durable queue (Vercel Queues / QStash / Upstash) | A durable mechanism survives longer than a single request and can retry independently, but it is new infrastructure (new service, new env vars, new failure mode) for work that is already designed to be best-effort and non-fatal (CAL-04: calendar failures must never break the user-facing flow). Given the work here is bounded (a handful of Google Calendar API calls per request) and already wrapped in try/except-swallow, inline-await is proportionate; a queue would be over-engineering for the current scale. Revisit only if calendar push volume or latency becomes a measured problem. |

**Feature availability note:** The Vercel `services` docs page is marked "🔒 Permissions Required: Services" — this may be plan/account-gated. **The planner must add a `checkpoint:human-verify` task to confirm `services` is available on this Vercel account/plan before committing the vercel.json rewrite** (e.g., `vercel services` or a scratch deploy). If unavailable, fall back to the "keep single-function model, delete orphaned `frontend/vercel.json`, simplify root `vercel.json`" path documented above.

**Installation:** N/A — no new dependencies. Existing `requirements.txt` should have `gunicorn` removed (Vercel's Python runtime does not use Gunicorn/Uvicorn CLI process managers; it invokes the ASGI `app` object directly) as part of the Railway-artifact cleanup.

## Package Legitimacy Audit

Not applicable — this phase installs no new packages. It only removes existing Railway-only dependencies (`gunicorn`) from `requirements.txt`.

## Architecture Patterns

### System Architecture Diagram

```
                     Browser Request
                          |
                          v
              ┌─────────────────────┐
              │   vercel.json        │   (top-level routing table)
              │   rewrites[]          │
              └───────┬──────┬───────┘
                       |      |
        source=/api/(.*)   source=/(.*)
                       |      |
                       v      v
        ┌──────────────────┐  ┌───────────────────────┐
        │ backend service   │  │ frontend service        │
        │ (Python, Fluid    │  │ (static build,          │
        │  Compute)         │  │  frontend/dist)          │
        │                   │  │                          │
        │ api/index.py:app  │  │  index.html + assets/*  │
        │  = FastAPI()      │  │  SPA fallback rewrite   │
        │  .mount("/api",   │  │  (service-level config) │
        │    backend.main)  │  │                          │
        └─────────┬─────────┘  └──────────────────────────┘
                  |
                  v
     ┌─────────────────────────────┐
     │ backend/main.py (FastAPI)   │
     │  routers: /chat, /onboarding,│
     │  /rides, /adaptations,      │
     │  /sessions, /calendar        │
     └───────┬──────────┬───────────┘
             |          |
   SSE routes:      Non-SSE routes:
   /chat/stream      inline-awaited pipelines
   /onboarding/*     (TSS/PMC, calendar push,
   (StreamingResponse) calendar-event update)
             |          |
             v          v
     ┌───────────────────────────┐
     │ Supabase (Postgres+Storage)│
     │  - service-role client     │
     │  - fits bucket (private)   │
     │  - indexed FK/user_id cols │
     └───────────────────────────┘
```

Reader can trace the primary use case: a request to `/api/rides/upload` enters via the top-level rewrite, lands on the backend service, is handled by `rides.py`'s `upload_fit`, and the TSS/PMC/debrief pipeline runs fully inline (already true since Phase 6) before the HTTP response is returned — no work survives past the response boundary.

### Recommended Project Structure (vercel.json changes only; app code structure unchanged)
```
/
├── vercel.json          # top-level: services{} + rewrites[] only
├── api/
│   └── index.py         # backend service entrypoint: app.mount("/api", backend.main.app) ONLY
│                         # (SPA-serving/StaticFiles/catch-all code REMOVED per phase goal)
├── frontend/
│   ├── vercel.json      # DELETE (orphaned once services{} owns routing) — see Pitfall 1
│   ├── dist/             # build output, served by the frontend service
│   └── ...
└── backend/              # unchanged; FastAPI routers
```

### Pattern 1: Vercel `services` split (frontend static + backend Python)
**What:** A single `vercel.json` `services` block defines two independently-built units; top-level `rewrites` decide which public paths reach which service.
**When to use:** Any monorepo combining a static SPA build with a Python (or any non-JS) API, where the API must NOT also be responsible for serving static assets.
**Example:**
```json
// Source: https://vercel.com/docs/services (CITED, last_updated 2026-06-16)
{
  "services": {
    "frontend": {
      "root": "frontend/",
      "buildCommand": "npm run build",
      "outputDirectory": "dist"
    },
    "backend": {
      "root": "api/",
      "entrypoint": "index:app"
    }
  },
  "rewrites": [
    { "source": "/api/(.*)", "destination": { "service": "backend" } },
    { "source": "/(.*)", "destination": { "service": "frontend" } }
  ]
}
```
Note: per the routing docs, the service **receives the original request path** — `/api/rides/upload` reaches the backend service as `/api/rides/upload`, not `/rides/upload`. This means `api/index.py`'s existing `app.mount("/api", _backend_app)` wrapper must be **kept** as the service entrypoint (it is what turns `/api/rides/upload` into `/rides/upload` for the inner FastAPI routers) — only its SPA-serving code should be deleted.

### Pattern 2: Inline-await for post-response work (already proven in this codebase)
**What:** Replace `background_tasks.add_task(fn, ...)` with `await fn(...)` executed before `return`, since Vercel Fluid Compute functions do not reliably continue executing FastAPI `BackgroundTasks` registered work after the response is sent (empirically confirmed in this project's own Phase 6 fix; see `backend/routes/rides.py` docstring and commit history `06-05-PLAN.md`).
**When to use:** Any FastAPI endpoint on this Vercel deployment that currently uses `BackgroundTasks.add_task`.
**Example (already-shipped reference pattern from `backend/routes/rides.py`):**
```python
# Source: backend/routes/rides.py (Phase 6, already in this codebase)
# BEFORE (unsafe under Vercel):
#   background_tasks.add_task(process_ride_background, ride_id, user_id, parsed, ftp_used, ride_date)
#   return {"ride_id": ride_id, "status": "processed"}
#
# AFTER (Phase 6 pattern, apply identically to the 3 remaining sites):
await process_ride_background(ride_id, user_id, parsed, ftp_used, ride_date)
return {"ride_id": ride_id, "status": "processed"}
```
Apply the same transform to:
- `backend/routes/onboarding.py:201` — `background_tasks.add_task(push_all_sessions_to_calendar, user_id)` -> `await push_all_sessions_to_calendar(user_id)`
- `backend/routes/adaptations.py:766` (inside `check_adaptations`) — `background_tasks.add_task(update_calendar_event, user_id, event_id, session)` -> `await update_calendar_event(user_id, event_id, session)`
- `backend/routes/adaptations.py:909` (inside `mark_session_missed`) — same transform

Both `push_all_sessions_to_calendar` and `update_calendar_event` already wrap their entire body in `try/except` and swallow errors silently (CAL-04 compliant) — this makes the inline-await conversion mechanically safe: no new error-handling needs to be written, only the scheduling mechanism changes. The `background_tasks: BackgroundTasks` parameter can be dropped from all three route signatures once no call site uses it.

### Anti-Patterns to Avoid
- **Python-side SPA serving as a permanent architecture:** `api/index.py`'s current `StaticFiles` mount + `@app.get("/{full_path:path}")` catch-all was a correct emergency fix for production (`260702-ulq`) but is explicitly called out in the phase goal for removal. Every non-API request currently pays a Python function invocation just to return a static `index.html`; moving to a static Vercel service removes that cost and matches Vercel's documented model.
- **Trusting root `vercel.json`'s existing `rewrites` as currently effective:** they are almost certainly dead code today, since the FastAPI Framework Preset (implied by `260702-ulq`'s commit message: "under the retained fastapi Vercel preset") routes all non-matched requests to the single function regardless of `vercel.json` rewrites for non-API paths — this is why the Python-side fallback had to exist at all. Any plan must not assume the current root `vercel.json` "just works"; it must be replaced/restructured.
- **Registering a background task without awaiting it, "just this once":** all 3 remaining `BackgroundTasks` sites look superficially safe (fire-and-forget, best-effort) but Vercel's freeze-after-response behavior means "fire-and-forget" silently becomes "may never fire" in production. Do not leave any `BackgroundTasks.add_task` call in the codebase after this phase.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Serving a Vite/React SPA + Python API from one Vercel project | Custom Python `StaticFiles` mount + manual catch-all route (current state) | Vercel `services` (frontend service + backend service) with top-level `rewrites` | This is now an officially documented, first-class Vercel feature for exactly this repo shape (polyglot monorepo: JS frontend + Python backend) — see Pattern 1 |
| Post-response background work on serverless | A hand-rolled retry/polling mechanism, or continuing to rely on `BackgroundTasks` | Inline-await (already the proven pattern in this codebase since Phase 6) | Simpler and already validated in production for the highest-risk pipeline (ride TSS/PMC); the 3 remaining sites are lower-volume Google Calendar calls, well within a single request's duration budget under Fluid Compute's 300s default |
| FK/user_id lookups without indexes | Nothing to hand-roll — this is a "don't skip" item, not a "don't build" item | Standard Postgres `CREATE INDEX` on every FK/user_id column | Every list/detail query in this app (`sessions.user_id`, `rides.user_id`, `messages.conversation_id`, etc.) currently does a sequential scan; this is a correctness-adjacent performance defect, not a design choice |

**Key insight:** The single biggest risk in this phase is treating the vercel.json conflict as "delete one file, keep the other" rather than understanding *why* the Python function grew SPA-serving logic in the first place (Framework Preset routing behavior). A plan that merely deletes `frontend/vercel.json` without addressing the Preset-routing root cause will not achieve "the SPA is served as static build."

## Runtime State Inventory

Trigger: this phase removes a deploy target (Railway) and repairs deploy config for an already-live production app.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None — Railway held no persistent app data; all state was always in Supabase (unaffected by Railway removal). `fits` storage bucket already provisioned via migration 0006. | None |
| Live service config | **Railway project itself** (if still provisioned in the Railway dashboard) is out-of-band, not in git — code removal (`Dockerfile`, `railway.toml`) does not delete the live Railway service/deployment. If a Railway service is still running and consuming credits, or still has a public URL that something references (e.g., `BACKEND_BASE_URL` pointed at Railway in any env, or old CORS `FRONTEND_URL`), it must be decommissioned in the Railway dashboard as a manual step outside git. | Manual: decommission/delete the Railway project in the Railway dashboard (checkpoint:human-verify); grep and correct any `BACKEND_BASE_URL`/`FRONTEND_URL` values still pointed at a `*.railway.app` / `*.up.railway.app` host in Vercel's env var dashboard |
| OS-registered state | None found — no Task Scheduler/launchd/systemd/pm2 artifacts reference Railway or Dockerfile in this repo | None |
| Secrets/env vars | Env var **names** (`ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, etc.) do not change; only their *host* changes (Railway dashboard -> Vercel dashboard, per-environment). Confirm every var currently set in Railway is also set in Vercel's Project Settings > Environment Variables before removing Railway access. | Manual: diff Railway env vars against Vercel env vars (checkpoint:human-verify); no code change |
| Build artifacts | `requirements.txt` still lists `gunicorn` (Railway/Docker-only; unused by Vercel's Python runtime, which invokes the ASGI `app` directly without a WSGI/process-manager layer) | Code edit: remove `gunicorn` from `requirements.txt` |

## Common Pitfalls

### Pitfall 1: Deleting `frontend/vercel.json` without restructuring root `vercel.json`
**What goes wrong:** If only the orphaned `frontend/vercel.json` is deleted and the root `vercel.json`'s existing (currently-ineffective) `rewrites` are left as-is, the Python Framework Preset continues routing 100% of traffic to the function, and the SPA is still served by Python — the phase goal is not actually satisfied even though the "conflict" file is gone.
**Why it happens:** The presence of two `vercel.json` files looks like "duplicate config" that just needs de-duplication, but the real defect is the *routing model* (single-function Framework Preset) vs. the *intended model* (static + function split), which requires `services` or an equivalent explicit split, not just file deletion.
**How to avoid:** Restructure root `vercel.json` to use `services` (Pattern 1) *and* remove the Python-side static-serving code in `api/index.py` in the same change; verify with a preview deploy that `/` returns `index.html` from the static service (check response headers for CDN cache markers, not FastAPI headers) and `/api/health` returns from the Python function.
**Warning signs:** After the change, a preview-deploy request to `/some-random-path` still returns HTML with FastAPI-style headers, or the `frontend/dist` build never gets referenced anywhere in the new config.

### Pitfall 2: Assuming `services` is available without checking account/plan
**What goes wrong:** The `services` docs page carries a "🔒 Permissions Required" badge; if the plan gates it, a plan built entirely around `services` will fail on first deploy.
**Why it happens:** Docs describe the feature as GA/current, but permission-gating on newer platform features is common and not always obvious from docs alone.
**How to avoid:** Add a `checkpoint:human-verify` task early in the plan (before any vercel.json rewrite) to confirm `services` works via a scratch preview deploy; have the fallback (single-function model, cleaned-up config, orphaned file deleted) ready as Plan B.
**Warning signs:** `vercel deploy` errors referencing unsupported top-level `services` key, or the Vercel dashboard shows only one "Function" instead of two services after deploy.

### Pitfall 3: Converting `BackgroundTasks` to inline-await but leaving CAL-04's non-blocking promise unverified
**What goes wrong:** `check_adaptations` and `mark_session_missed` currently return quickly because calendar sync is fire-and-forget; after inline-await, the endpoint's response time now includes however long the Google Calendar API call takes. If that call hangs (e.g., expired/invalid refresh token retried without a timeout), the endpoint could hang up to the function's `maxDuration`.
**Why it happens:** `_load_credentials` / `_build_calendar_service` / Google API calls do not appear to have an explicit per-call timeout in the reviewed code paths.
**How to avoid:** When converting these 3 call sites, verify (or add) a bounded timeout around the Google Calendar API calls inside `update_calendar_event`/`push_all_sessions_to_calendar` so a slow/hanging external call cannot stall the whole request past a reasonable UX budget (a few seconds), independent of the function's hard `maxDuration` ceiling.
**Warning signs:** `POST /adaptations/check` or `POST /adaptations/sessions/{id}/missed` latency spikes after this change, especially for users with stale/expired Calendar tokens.

### Pitfall 4: Forgetting that `/chat/stream` is GET, not POST, when updating README
**What goes wrong:** The current README's API Endpoint list says `POST /chat/stream`, but the actual route (`backend/routes/chat.py:69`) is `@router.get("/stream")`. If the README is "corrected" mechanically without checking actual route decorators, this existing error will be preserved or a new one introduced.
**Why it happens:** GET is required here specifically because the frontend uses browser `EventSource`, which can only issue GET requests — this is a deliberate, documented design constraint (JWT passed via `?token=` query param because `EventSource` cannot set headers), not an oversight.
**How to avoid:** When rewriting the README's endpoint table, verify each route's HTTP method against the actual `@router.<method>` decorator in source, not against the previous README text.
**Warning signs:** A new contributor tries `curl -X POST /chat/stream` per the README and gets a 405.

## Code Examples

### Full inline-await conversion (onboarding.py plan-calendar-sync)
```python
# Source: backend/routes/onboarding.py (existing code, lines 181-202) + Phase 6 pattern
# CURRENT (unsafe under Vercel):
@router.post("/plan-calendar-sync")
async def onboarding_plan_calendar_sync(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
) -> dict:
    user_id = current_user["user_id"]
    background_tasks.add_task(push_all_sessions_to_calendar, user_id)
    return {"status": "scheduled"}

# TARGET (inline-await, matches rides.py Phase 6 pattern):
@router.post("/plan-calendar-sync")
async def onboarding_plan_calendar_sync(
    current_user: dict = Depends(get_current_user),
) -> dict:
    user_id = current_user["user_id"]
    await push_all_sessions_to_calendar(user_id)
    return {"status": "completed"}
```
Note the response body's `"status"` value should change from `"scheduled"` to something reflecting that the work is already done (e.g. `"completed"`) — check the frontend for any code that branches on this literal string before renaming it.

### New migration: FK/user_id indexes
```sql
-- Source: derived from full column inventory across supabase/migrations/0001-0006
-- New file: supabase/migrations/0007_fk_indexes.sql
CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON public.profiles (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_plan_id ON public.sessions (plan_id);
CREATE INDEX IF NOT EXISTS idx_rides_user_id ON public.rides (user_id);
CREATE INDEX IF NOT EXISTS idx_rides_session_id ON public.rides (session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON public.conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON public.messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON public.messages (user_id);
CREATE INDEX IF NOT EXISTS idx_capability_gaps_user_id ON public.capability_gaps (user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_states_user_id ON public.oauth_states (user_id);
CREATE INDEX IF NOT EXISTS idx_plans_user_id ON public.plans (user_id);
CREATE INDEX IF NOT EXISTS idx_adaptations_user_id ON public.adaptations (user_id);
-- pmc_history(user_id, date) already has a composite unique index from 0006
-- (pmc_history_user_id_date_key), which serves user_id-only lookups via
-- leftmost-prefix matching -- no additional index needed there.
```
Apply with `supabase db push --linked --yes` per the established project pattern (STATE.md: "Migration applied via supabase db push --linked (non-interactive with --yes flag)").

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Manual `builds`/rewrites juggling to combine a Python function with a static frontend in one Vercel project | Native `services` key in `vercel.json` (frontend + backend as separate build units under one routing table) | Docs last updated 2026-06-16; replaces the earlier `experimentalServices` config | Eliminates the class of bug this phase is fixing (Framework Preset silently owning all routing); this project predates the feature's stabilization, hence the workaround in `api/index.py` |
| Dual hosts (Vercel frontend + Railway backend) | Single Vercel project, single deployment, shared domain | 2026-07-03 (this project's own decision) | Removes cross-origin CORS complexity risk (though CORS middleware remains in place defensively), removes a second platform's billing/ops surface, removes Docker/Gunicorn as a required skill for this codebase |
| `BackgroundTasks.add_task` for any post-response work | Inline-await everything before returning, on serverless/Fluid Compute platforms without a durable task API in the language runtime being used | Already established in this codebase's Phase 6 (2026-07-03) | This phase completes that migration for the last 3 call sites; after this phase, `BackgroundTasks` should have zero remaining call sites in `backend/` |

**Deprecated/outdated:**
- Railway hosting for this project: fully abandoned per STATE.md 2026-07-03 decision. `Dockerfile`, `railway.toml`, and `gunicorn` in `requirements.txt` are now dead weight.
- `experimentalServices` config key: superseded by `services` (mentioned only for awareness; this project never used it).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `services` is available on this project's current Vercel plan/account | Standard Stack, Pitfall 2 | If unavailable, the primary recommended vercel.json restructuring cannot be deployed as designed; planner must gate this behind a checkpoint and have the fallback (clean up single-function model) ready |
| A2 | The FastAPI Framework Preset (not an explicit `builds` array) is what is actually active on the live Vercel project today, based on `260702-ulq`'s commit message ("under the retained fastapi Vercel preset") | Anti-Patterns, Pitfall 1 | If the live project's actual Framework Preset/Root Directory setting differs from what the commit message implies, the root-cause diagnosis of the vercel.json conflict could be incomplete; planner should verify current Project Settings in the Vercel dashboard before finalizing the vercel.json rewrite |
| A3 | Google Calendar API calls inside `update_calendar_event`/`push_all_sessions_to_calendar` have no explicit per-call timeout today | Pitfall 3 | If a timeout already exists deeper in `_build_calendar_service`/`googleapiclient` defaults, the pitfall may be lower-severity than described; verify during implementation before adding redundant timeout handling |

## Open Questions

1. **Is the live Vercel project's Framework Preset actually "fastapi", or "Other"?**
   - What we know: `260702-ulq`'s commit message says "under the retained fastapi Vercel preset."
   - What's unclear: This research could not access the live Vercel dashboard Project Settings to confirm directly.
   - Recommendation: First task in the plan should be a read-only check (`vercel project inspect` or dashboard screenshot) to confirm the current Framework Preset before restructuring vercel.json.

2. **Does the account have `services` enabled?**
   - What we know: The docs describe it as a current, documented feature but flag "Permissions Required."
   - What's unclear: Whether this specific Vercel account/plan has it enabled.
   - Recommendation: `checkpoint:human-verify` task early in the plan, with the single-function fallback path fully specified as Plan B (see Alternatives Considered).

3. **Is `uvicorn` still needed in `requirements.txt` after Railway removal?**
   - What we know: `gunicorn` is definitely Railway/Docker-only (used only in the removed `Dockerfile` CMD).
   - What's unclear: Whether any local dev workflow (`uvicorn api.main:app --reload`, per current README) still needs `uvicorn` directly, independent of Vercel's runtime (which invokes the ASGI app without going through the `uvicorn` CLI).
   - Recommendation: Keep `uvicorn` in `requirements.txt` (local dev still needs it per the README's own documented local-dev command) but remove `gunicorn` (used nowhere outside the deleted Dockerfile).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Vercel CLI | Preview deploys, `vercel dev`, services routing verification | Yes | 54.18.1 | — |
| Supabase CLI | `supabase db push --linked` for the new index migration | Yes | 2.107.0 | — |
| Node.js | Frontend build | Yes | v25.9.0 | — |
| npm | Frontend build | Yes | 11.12.1 | — |

No missing dependencies. No blockers to execution from a tooling standpoint.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 (backend); Vitest + Playwright (frontend, unaffected by this phase) |
| Config file | `pytest.ini` (testpaths=tests, asyncio_mode=auto) |
| Quick run command | `pytest tests/api/test_onboarding.py tests/api/test_adaptations.py -x` |
| Full suite command | `pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DEPLOY-BG-01 | `onboarding_plan_calendar_sync` awaits `push_all_sessions_to_calendar` directly instead of scheduling it as a background task | unit | `pytest tests/api/test_onboarding.py -k calendar_sync -x` | Check existing `tests/api/test_onboarding.py` for a background-task-mock assertion to update; ❌ Wave 0 if absent |
| DEPLOY-BG-02 | `check_adaptations` and `mark_session_missed` await `update_calendar_event` directly | unit | `pytest tests/api/test_adaptations.py -k calendar -x` | Check existing `tests/api/test_adaptations.py`; ❌ Wave 0 if no test currently asserts on `background_tasks.add_task` call args (which would need updating to assert direct await instead) |
| DEPLOY-IDX-01 | New migration applies cleanly and indexes exist on all FK/user_id columns | manual/deploy-verification | `supabase db push --linked --yes` then a Supabase SQL check (`SELECT indexname FROM pg_indexes WHERE schemaname='public'`) | ❌ Wave 0 — no existing automated test covers index presence; this is inherently a deploy-time verification, not a unit test |
| DEPLOY-ROUTE-01 | `/api/*` reaches the Python function and `/` (and all other non-API paths) serve the static SPA build, not the Python function | manual (post-deploy) | Preview-deploy `curl -I https://<preview-url>/` (expect static CDN headers) and `curl https://<preview-url>/api/health` (expect FastAPI JSON) | manual-only — no local test can exercise Vercel's actual routing table; requires a real preview deployment |
| DEPLOY-SSE-01 | `/chat/stream` and `/onboarding/start` continue to stream correctly after the vercel.json restructure | manual (post-deploy) + existing test | `pytest tests/agent/test_sse.py -x` (regression, local) + manual EventSource check against the preview deploy | `tests/agent/test_sse.py` exists ✅ for local regression; production streaming behavior itself is manual-only |

### Sampling Rate
- **Per task commit:** targeted pytest file for the touched route (e.g. `pytest tests/api/test_adaptations.py -x`)
- **Per wave merge:** `pytest tests/ -v` (full backend suite)
- **Phase gate:** Full backend suite green + a real Vercel preview deployment manually verified (`/`, `/api/health`, `/chat/stream`, `/onboarding/start`) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/api/test_onboarding.py` — update/add a test asserting `push_all_sessions_to_calendar` is awaited directly (no `BackgroundTasks` mock needed after the change); covers DEPLOY-BG-01
- [ ] `tests/api/test_adaptations.py` — update/add tests asserting `update_calendar_event` is awaited directly in both `check_adaptations` and `mark_session_missed`; covers DEPLOY-BG-02
- [ ] No test infra gap for indexes/routing/SSE — these are inherently deploy-time/manual verification, not something a Wave 0 test file would cover; document as `checkpoint:human-verify` tasks in the plan instead of forcing them into pytest

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No change in this phase | Existing Supabase JWT verification (`backend/auth.py`) unaffected |
| V3 Session Management | No change | N/A |
| V4 Access Control | No change | N/A |
| V5 Input Validation | No change | N/A |
| V6 Cryptography | Indirectly relevant | `CALENDAR_FERNET_KEY` must be present in Vercel's env vars (not just Railway's) before Railway is decommissioned, or Calendar token decryption breaks in production — this is a deploy-config correctness issue, not a new crypto control |
| V13/V14 (config/deployment) | Yes — this entire phase | Removing dead deploy artifacts (Dockerfile, railway.toml) and correcting documented env-var requirements reduces the chance of a misconfigured/duplicate production surface; ensure no `.env`/secret value is ever written into README.md's corrected env-var table (names only, no example real values) |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Stale/orphaned Railway deployment left running after "abandonment" (still reachable publicly, still holding a copy of `SUPABASE_SERVICE_ROLE_KEY`) | Information Disclosure / Elevation of Privilege | Manually decommission the Railway project in its dashboard (Runtime State Inventory item); do not consider the migration complete until confirmed via the Railway dashboard, not just via git diff |
| README/CLAUDE.md documenting a real secret's *value* while "completing" the env-var table | Information Disclosure | Document variable **names** and one-line purpose only, exactly as the existing table already does; do not paste actual `.env`/`.env.local` values into any committed doc |
| SSE endpoint auth via `?token=<jwt>` query string (already existing pattern, not introduced by this phase) | Information Disclosure (JWT in server logs/referrer headers) | Already a known, documented tradeoff in this codebase (`chat.py`'s own docstring: "EventSource cannot send headers"); out of scope for this phase (short-lived SSE token exchange is explicitly assigned to **Phase 10**) — do not attempt to fix it here, just don't make it worse |

## Sources

### Primary (HIGH confidence)
- Direct codebase inspection: `vercel.json`, `frontend/vercel.json`, `api/index.py`, `Dockerfile`, `railway.toml`, `backend/routes/{onboarding,adaptations,rides,chat}.py`, `backend/routes/_sse.py`, `backend/calendar_sync.py`, `backend/main.py`, `requirements.txt`, `README.md`, all 6 files in `supabase/migrations/`, `.planning/STATE.md`, `.planning/ROADMAP.md`
- [Vercel Services](https://vercel.com/docs/services) — services/rewrites config model, last_updated 2026-06-16
- [Vercel Services Routing](https://vercel.com/docs/services/routing) — confirmed service receives full original path (no prefix stripping)
- [Deploy a FastAPI app on Vercel](https://vercel.com/docs/frameworks/backend/fastapi) — confirmed "the whole app becomes a single Vercel Function" under the plain Framework Preset model
- [Using the Python Runtime with Vercel Functions](https://vercel.com/docs/functions/runtimes/python) — confirmed streaming support, entrypoint resolution rules, bundle limits

### Secondary (MEDIUM confidence)
- `vercel:vercel-functions` skill guidance (bundled reference, cross-checked against the above official docs pages) — Fluid Compute default 300s / Pro-Enterprise 800s duration limits, `waitUntil`/`after` background-processing APIs (Node.js-documented; Python-specific `waitUntil` support could not be confirmed from official Python runtime docs — treated as unconfirmed, hence the inline-await recommendation instead of relying on it)
- WebSearch: "Vercel Python runtime waitUntil background tasks... FastAPI BackgroundTasks unsupported" — community reports of FastAPI `BackgroundTasks` reliability issues on Vercel corroborate this project's own Phase 6 empirical finding

### Tertiary (LOW confidence)
- None relied upon for load-bearing claims in this document.

## Metadata

**Confidence breakdown:**
- Standard stack / vercel.json restructuring: MEDIUM-HIGH — the `services` mechanism is confirmed from current official docs, but its availability on this specific Vercel account/plan is unverified (A1); recommendation includes an explicit fallback and a mandatory checkpoint
- BackgroundTasks -> inline-await: HIGH — this exact pattern is already shipped and proven in this codebase (Phase 6, `rides.py`); the 3 remaining sites are a mechanical, low-risk repeat of a known-working change
- DB indexing: HIGH — verified by exhaustive grep across all 6 migration files; zero ambiguity in what's missing
- README/CLAUDE.md corrections: HIGH — every claimed gap (missing env vars, wrong key name, stale Railway sections, wrong HTTP method) was verified directly against source code, not assumed

**Research date:** 2026-07-03
**Valid until:** 30 days (Vercel platform features, especially `services`, are actively evolving; re-verify `services` availability/behavior if this phase is executed significantly later than the research date)
