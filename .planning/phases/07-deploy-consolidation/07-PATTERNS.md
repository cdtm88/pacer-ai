# Phase 7: Deploy Consolidation - Pattern Map

**Mapped:** 2026-07-03
**Files analyzed:** 9
**Analogs found:** 8 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `vercel.json` (root, rewrite) | config | request-response | `vercel.json` (current, self) | exact (restructure in place) |
| `frontend/vercel.json` (delete) | config | request-response | — | n/a (deletion) |
| `api/index.py` (strip SPA-serving code) | route/config | request-response | `api/index.py` (self, before state) | exact |
| `backend/routes/onboarding.py` (`onboarding_plan_calendar_sync`) | route | event-driven (post-response side effect) | `backend/routes/rides.py` (`upload_fit`) | exact — identical BackgroundTasks-to-inline-await transform, already shipped in Phase 6 |
| `backend/routes/adaptations.py` (`check_adaptations`) | route | event-driven | `backend/routes/rides.py` (`upload_fit`) | exact |
| `backend/routes/adaptations.py` (`mark_session_missed`) | route | event-driven | `backend/routes/rides.py` (`upload_fit`) | exact |
| `supabase/migrations/0007_fk_indexes.sql` | migration | batch (DDL) | `supabase/migrations/0006_pmc_unique_and_fits_bucket.sql` | exact — idempotent DDL style already established |
| `requirements.txt` (remove `gunicorn`) | config | n/a | self | exact |
| `README.md` (deploy + env-var sections) | config/docs | n/a | self (existing table) | exact |
| `.claude/CLAUDE.md` (Railway references) | config/docs | n/a | self (existing table) | exact |

## Pattern Assignments

### `backend/routes/onboarding.py` (route, event-driven) — PRIMARY PATTERN

**Analog:** `backend/routes/rides.py` — this is the already-shipped, proven Phase 6 reference. Copy this transform verbatim for all 3 remaining call sites.

**Current unsafe pattern in `rides.py` (historical, before Phase 6 fix — shown in comment form at `backend/routes/rides.py` docstring lines 463-465 and inline comment lines 615-616):**
```python
# BEFORE (unsafe under Vercel):
#   background_tasks.add_task(process_ride_background, ride_id, user_id, parsed, ftp_used, ride_date)
#   return {"ride_id": ride_id, "status": "processed"}
```

**Shipped fix — exact code to copy the shape of** (`backend/routes/rides.py` lines 450-455, 615-625):
```python
@router.post("/upload")
async def upload_fit(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    ...
    # --- Run the ride pipeline inline-awaited (Vercel serverless constraint: no
    #     BackgroundTasks, which Vercel freezes/kills after the response is sent) ---
    await process_ride_background(
        ride_id,
        user_id,
        parsed,
        ftp_used,
        ride_date,
    )

    return {"ride_id": ride_id, "status": "processed"}
```
Key elements to replicate exactly:
1. `BackgroundTasks` parameter removed entirely from the route signature (rides.py no longer takes it).
2. `background_tasks.add_task(fn, ...)` call replaced with `await fn(...)` at the same call site.
3. A one-line comment directly above the await citing the Vercel constraint (`rides.py` uses this exact phrasing — reuse verbatim for consistency): `# ... inline-awaited (Vercel serverless constraint: no BackgroundTasks, which Vercel freezes/kills after the response is sent) ---`
4. Docstring updated to describe the new synchronous-completion behavior (see `rides.py` lines 463-465 as the docstring-wording analog).

**Target for `onboarding.py`** (current unsafe code at lines 181-202):
```python
@router.post("/plan-calendar-sync")
async def onboarding_plan_calendar_sync(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
) -> dict:
    ...
    background_tasks.add_task(push_all_sessions_to_calendar, user_id)
    return {"status": "scheduled"}
```
Apply the `rides.py` transform: drop the `background_tasks: BackgroundTasks` param, replace with `await push_all_sessions_to_calendar(user_id)`, change the return literal from `"status": "scheduled"` to `"status": "completed"` (RESEARCH.md flags: check frontend for any code branching on the `"scheduled"` string literal before renaming). Update the docstring's "Fire-and-forget... Returns immediately" language to match `rides.py`'s "inline-awaited before responding" wording, and drop the unused `BackgroundTasks` import from `onboarding.py` line 37 if no other route in the file still uses it (check `adaptations.py`-style — `onboarding.py` currently only uses `BackgroundTasks` at this one call site).

**Imports pattern** — `onboarding.py` line 37 currently: `from fastapi import APIRouter, BackgroundTasks, Depends`. After conversion (assuming no other use), becomes: `from fastapi import APIRouter, Depends`.

---

### `backend/routes/adaptations.py` (route, event-driven) — two call sites

**Analog:** same `rides.py` pattern as above.

**Call site 1 — `check_adaptations`** (current unsafe code at lines 733-766):
```python
@router.post("/check")
async def check_adaptations(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
) -> dict:
    ...
    if result and result.get("status") == "applied":
        after_sessions = result.get("after", [])
        before_sessions = result.get("before", [])
        before_by_id = {s["id"]: s for s in before_sessions}
        for session in after_sessions:
            event_id = session.get("calendar_event_id") or before_by_id.get(session["id"], {}).get("calendar_event_id")
            if event_id:
                background_tasks.add_task(update_calendar_event, user_id, event_id, session)
```
Transform: replace `background_tasks.add_task(update_calendar_event, user_id, event_id, session)` with `await update_calendar_event(user_id, event_id, session)`. Since this is inside a `for` loop, each event updates sequentially before the response — acceptable per RESEARCH.md Pitfall 3 as long as `update_calendar_event` has a bounded per-call timeout (verify/add during implementation, not part of this mechanical transform). Drop the `background_tasks: BackgroundTasks` parameter from the route signature only if `mark_session_missed` (same file) is converted in the same change — otherwise the file-level `BackgroundTasks` import stays until both sites are done.

**Call site 2 — `mark_session_missed`** (current unsafe code at lines 840-909, identical inner shape to call site 1, lines 901-909):
```python
@router.post("/sessions/{session_id}/missed")
async def mark_session_missed(
    background_tasks: BackgroundTasks,
    session_id: str = Path(...),
    current_user: dict = Depends(get_current_user),
) -> dict:
    ...
    try:
        ...
        if result and result.get("status") == "applied":
            after_sessions = result.get("after", [])
            before_sessions = result.get("before", [])
            before_by_id = {s["id"]: s for s in before_sessions}
            for session in after_sessions:
                event_id = session.get("calendar_event_id") or before_by_id.get(session["id"], {}).get("calendar_event_id")
                if event_id:
                    background_tasks.add_task(update_calendar_event, user_id, event_id, session)
    except Exception:
        logger.warning(...)
```
Same transform as call site 1: `background_tasks.add_task(...)` -> `await update_calendar_event(user_id, event_id, session)`, still inside the existing `try/except Exception` block that already swallows errors non-fatally (CAL-04 compliant — no new error handling needed, matches `rides.py`'s established pattern of not adding new try/except when converting). After both sites in `adaptations.py` are converted, drop `background_tasks: BackgroundTasks` from both signatures and remove `BackgroundTasks` from the `fastapi` import at line 40: `from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path` -> `from fastapi import APIRouter, Depends, HTTPException, Path`.

---

### `supabase/migrations/0007_fk_indexes.sql` (migration, batch)

**Analog:** `supabase/migrations/0006_pmc_unique_and_fits_bucket.sql` — establishes the project's idempotent-DDL convention (`IF NOT EXISTS` guards, header comment block explaining *why*, dated).

**Pattern to copy** (header comment style + idempotency, from `0006_pmc_unique_and_fits_bucket.sql` lines 1-11):
```sql
-- 0006: Close two live-verification gaps found during Phase 6 UAT (2026-07-03).
--
-- 1. pmc_history was missing the composite unique key ...
--    Idempotent: skip if the constraint already exists.
```
`CREATE INDEX IF NOT EXISTS` is itself natively idempotent (unlike the `DO $$ ... IF NOT EXISTS` wrapper 0006 needed for a named constraint), so the new migration is simpler — RESEARCH.md's Code Examples section already has the exact statement list ready to use verbatim:
```sql
CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON public.profiles (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.sessions (user_id);
-- ... (full list in 07-RESEARCH.md "Code Examples" section)
```
Apply via `supabase db push --linked --yes` (established project pattern per STATE.md, also referenced in `0006`'s deploy history).

---

### `api/index.py` (route/config, request-response)

**Analog:** self (current file) — the SPA-serving block to delete is clearly bounded.

**Code to keep** (lines 1-17):
```python
from fastapi import FastAPI
from backend.main import app as _backend_app  # noqa: E402

app = FastAPI()
app.mount("/api", _backend_app)
```
Per RESEARCH.md Pattern 1, this `app.mount("/api", ...)` wrapper must be kept even after adopting Vercel `services`, because the service receives the full original path (`/api/rides/upload`) and this mount is what strips the `/api` prefix for the inner FastAPI routers.

**Code to delete** (lines 18-64): the `StaticFiles` mount, `_DIST_CANDIDATES` resolution logic, and the `@app.get("/{full_path:path}")` catch-all SPA-serving route — all explicitly called out in RESEARCH.md's Anti-Patterns section for removal once the `frontend` static service takes over serving `/`.

---

### `vercel.json` (root) (config, request-response)

**Analog:** self (current 6-line file) restructured per RESEARCH.md Pattern 1 (`services` key). No other file in the repo has this shape — copy the pattern from RESEARCH.md's Pattern 1 code block directly (already fully specified there with source citation to vercel.com/docs/services). `frontend/vercel.json` is deleted, not merged, once `services` owns routing (Pitfall 1 in RESEARCH.md: do not just delete `frontend/vercel.json` without restructuring root `vercel.json` in the same change).

---

### `requirements.txt` (config)

**Analog:** self — single-line removal, no pattern needed. Remove `gunicorn==22.*` (line 12). Keep `uvicorn==0.30.*` (still used for local dev per README's documented `uvicorn` command, per RESEARCH.md Open Question 3 resolution).

---

### `README.md` (docs) and `.claude/CLAUDE.md` (docs)

**Analog:** self — existing tables define the format to preserve (Markdown pipe tables), only content changes.

**README.md locations requiring edits** (verified via grep):
- Line 25: `### Backend (Railway via Docker)` heading and its body
- Line 72: `POST /chat/stream` -- wrong HTTP method; actual route is `@router.get("/stream")` in `backend/routes/chat.py:69` — must become `GET /chat/stream` per RESEARCH.md Pitfall 4
- Line 113: `SUPABASE_SERVICE_KEY` in the `cp .env.example .env` comment — wrong key name, should be `SUPABASE_SERVICE_ROLE_KEY`
- Lines 139-157: `## Deployment` section, `### Backend: Railway` subsection — replace with Vercel-only deployment instructions (services split)
- Lines 169-179: env-var table under `### Backend (.env or Railway env vars)` — rename heading to drop "Railway", fix `SUPABASE_SERVICE_KEY` -> `SUPABASE_SERVICE_ROLE_KEY`, add missing vars: `SUPABASE_JWT_SECRET`, `CALENDAR_FERNET_KEY`, `BACKEND_BASE_URL`, `ANTHROPIC_MODEL`; remove `PORT` (Gunicorn/Railway-specific, not used by Vercel's Python runtime)

**`.claude/CLAUDE.md` locations requiring edits** (verified via grep, 5 occurrences):
- Line 14: `Vercel (frontend) + Railway (API/DB)` -> `Vercel (frontend + backend)`
- Line 57: `Standard FastAPI production server; pair with Gunicorn for Railway` -> update rationale, Gunicorn no longer used
- Line 101: Railway row in Backend stack table -> remove or replace with Vercel Python Runtime row (if not already present elsewhere in the doc)
- Line 104: `PostgreSQL | Railway or Supabase` -> `PostgreSQL | Supabase`
- Line 149: Railway confidence-notes row -> remove (no longer a live decision)

## Shared Patterns

### BackgroundTasks -> inline-await (the single most important pattern in this phase)
**Source:** `backend/routes/rides.py` lines 450-455 (signature, no `BackgroundTasks` param) and lines 615-625 (inline await + comment + docstring wording)
**Apply to:** `backend/routes/onboarding.py::onboarding_plan_calendar_sync`, `backend/routes/adaptations.py::check_adaptations`, `backend/routes/adaptations.py::mark_session_missed`
```python
# Comment to reuse verbatim above each converted await call:
# --- ... inline-awaited (Vercel serverless constraint: no
#     BackgroundTasks, which Vercel freezes/kills after the response is sent) ---
await <target_fn>(...)
```
Mechanically safe because all target functions (`push_all_sessions_to_calendar`, `update_calendar_event`) already wrap their bodies in try/except and swallow errors silently (CAL-04-compliant) — matches how `process_ride_background` in `rides.py` was already safe to inline-await.

### Idempotent migration DDL
**Source:** `supabase/migrations/0006_pmc_unique_and_fits_bucket.sql`
**Apply to:** `supabase/migrations/0007_fk_indexes.sql`
```sql
CREATE INDEX IF NOT EXISTS idx_<table>_<column> ON public.<table> (<column>);
```

### Doc-table correction (names/purpose only, no real secret values)
**Source:** existing README.md env-var table format (pipe-table, `| Var | Purpose |`)
**Apply to:** README.md env-var section, `.claude/CLAUDE.md` stack tables
Preserve table structure; only cell content changes. RESEARCH.md's Security Domain section explicitly warns: document variable **names** and purpose only, never paste real `.env` values.

## No Analog Found

| File | Role | Data Flow | Reason |
|---|---|---|---|
| `vercel.json` `services` block | config | request-response | No existing file in this repo uses the `services` key — this is a net-new Vercel feature adoption; RESEARCH.md's Pattern 1 code block (cited from official Vercel docs) is the only available reference, not a codebase analog. Planner must gate this behind the `checkpoint:human-verify` task RESEARCH.md specifies (confirm `services` is available on the account/plan) before committing to this structure. |

## Metadata

**Analog search scope:** `backend/routes/`, `api/`, `supabase/migrations/`, root config files (`vercel.json`, `requirements.txt`, `README.md`, `.claude/CLAUDE.md`)
**Files scanned:** `backend/routes/rides.py`, `backend/routes/onboarding.py`, `backend/routes/adaptations.py`, `api/index.py`, `vercel.json`, `frontend/vercel.json`, `requirements.txt`, `supabase/migrations/0006_pmc_unique_and_fits_bucket.sql`, `README.md`, `.claude/CLAUDE.md`
**Pattern extraction date:** 2026-07-03
</content>
