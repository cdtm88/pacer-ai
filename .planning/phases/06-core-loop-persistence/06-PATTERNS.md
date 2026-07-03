# Phase 6: Core Loop Persistence - Pattern Map

**Mapped:** 2026-07-03
**Files analyzed:** 10
**Analogs found:** 9 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/agent/tools.py` (`_persist_generated_plan`, `dispatch_tool` extension) | service (orchestration hook) | CRUD (insert plans/sessions) | `backend/agent/tools.py::dispatch_tool` (same file, existing user_id-injection special case) | exact |
| `backend/routes/rides.py` (`upload_fit` dedup, FTP write-back, inline pipeline) | route/controller | file-I/O + CRUD | `backend/routes/rides.py::upload_fit`/`process_ride_background` (same file, current impl) | exact |
| `backend/pmc_recompute.py` (new) | service (batch orchestrator) | batch / transform | `backend/routes/rides.py::process_ride_background` steps 2-3-6 (PMC load/update/upsert block) | role-match (single-step -> batch pattern) |
| `backend/routes/adaptations.py` (`detect_signals`, `apply_micro_adjustment`, `apply_macro_replan`, new `POST /{id}/confirm`) | route/controller | CRUD + event-driven | `backend/routes/adaptations.py::mark_session_missed` (same file, existing ownership-check + re-detect pattern) | exact |
| `backend/routes/sessions.py` (verify only, no code change expected) | route/controller | request-response | N/A — verification pass only | n/a |
| `supabase/migrations/0005_phase6_persistence.sql` (new) | migration | schema DDL | `supabase/migrations/0003_phase4_schema.sql` | exact |
| `tests/api/test_rides.py` (new/extended cases: dedup, ftp_writeback, session_link, upload_returns) | test | request-response (integration, mocked Supabase) | `tests/api/test_rides.py` (existing tests in same file) + `tests/api/conftest.py::mock_supabase_factory` | exact |
| `tests/api/test_adaptations.py` (new/extended cases: idempotent, missed_status_value, confirm_macro) | test | request-response (integration, mocked Supabase) | `tests/api/test_adaptations.py` (existing tests in same file) + `tests/api/conftest.py::mock_supabase_factory` | exact |
| `tests/test_pmc_recompute.py` (new) | test | unit (batch/transform) | `tests/sports_science/test_pmc.py` (pure-function unit test style for `update_pmc`) | role-match |
| `backend/sports_science/plan.py`, `pmc.py` | service (pure compute) | transform | NO CHANGE — locked pure-function invariant; do not treat as a file to pattern-match against, just preserve as-is | n/a |

## Pattern Assignments

### `backend/agent/tools.py::dispatch_tool` (service, CRUD persistence hook)

**Analog:** same file, existing special-case block (lines 400-420) that injects `user_id` into `save_profile`/`generate_plan` inputs.

**Existing special-case pattern to extend** (`backend/agent/tools.py:414-441`):
```python
async def dispatch_tool(tool_use_block, audit_log: list, user_id: str | None = None) -> dict:
    name = tool_use_block.name
    inputs = tool_use_block.input
    tool_use_id = tool_use_block.id

    if user_id is not None and name in {"save_profile", "generate_plan"}:
        inputs = {**inputs, "user_id": user_id}

    fn = TOOL_REGISTRY.get(name)
    ...
    try:
        if asyncio.iscoroutinefunction(fn):
            result: ToolResult = await fn(**inputs)
        else:
            result: ToolResult = await asyncio.to_thread(fn, **inputs)

        audit_log.append({
            "tool_use_id": tool_use_id,
            "name": name,
            "result": result.model_dump(),
        })
        return {
            "type": "tool_result",
            "tool_use_id": tool_use_id,
            "content": [{"type": "text", "text": json.dumps(result.to_tool_response())}],
            "is_error": False,
        }
    except Exception as exc:
        audit_log.append({"tool_use_id": tool_use_id, "name": name, "error": str(exc)})
        return {"type": "tool_result", "tool_use_id": tool_use_id,
                "content": [{"type": "text", "text": f"Error: {exc}"}], "is_error": True}
```

**Extension point:** insert a `name == "generate_plan"` branch immediately after the `result` is obtained (before `audit_log.append`), calling `await _persist_generated_plan(user_id, result.value)` which mutates `result.value["plan_id"]` and `result.value["sessions"][i]["id"]` in place. Wrap the persistence call in its own try/except so a DB failure surfaces as a tool error (do not let it silently swallow like the `process_ride_background` `try/except Exception: logger.error` anti-pattern flagged in Pitfall 1 — RESEARCH.md explicitly calls that swallow-pattern out as the cause of Pitfall 1, so persistence failures here must propagate to the existing outer `except Exception as exc` in `dispatch_tool`, not be double-wrapped and hidden).

**Error handling pattern to reuse:** the outer `try/except Exception as exc: audit_log.append(...); return {..., is_error: True}` block already gives D-14 "never swallowed" semantics — let `_persist_generated_plan` raise naturally and rely on this existing wrapper rather than adding a second catch-and-log inside it.

---

### `backend/routes/rides.py` (route, file-I/O + CRUD)

**Analog:** same file, current `upload_fit` (lines 449-548) and `process_ride_background` (lines 248-419).

**Imports pattern already present** (top of file, reuse as-is):
```python
import asyncio, hashlib, logging
from datetime import date, datetime, timezone
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
```
Add `hashlib` usage (stdlib already imported project-wide in `agent/tools.py::dedup_key` at lines 384-392 — same `hashlib.sha256(...).hexdigest()` idiom to copy verbatim for content-hash dedup).

**Current upload flow to extend (lines 449-548):**
```python
file_bytes = await file.read(MAX_UPLOAD_BYTES + 1)
...
parsed = await asyncio.to_thread(parse_fit_file, file_bytes)
...
ftp_used, is_estimated = await get_user_ftp(user_id)
safe_filename = _sanitize_filename(file.filename or "upload.fit")
storage_path = f"fits/{user_id}/{safe_filename}"
```
**Insert dedup check** between `parsed = ...` and `ftp_used = ...`, computing `content_hash = hashlib.sha256(file_bytes).hexdigest()`, querying `rides` table `.eq("user_id", user_id).eq("content_hash", content_hash)`, and short-circuiting with a `duplicate=True` response if found — mirrors the existing "verify ownership before mutate" idiom used in `mark_session_missed` (`adaptations.py:670-682`, dual `.eq("id", ...).eq("user_id", ...)` pattern) applied here as a pre-check `.eq("user_id", ...).eq("content_hash", ...)`.

**FTP key-fix + write-back location** (`get_user_ftp`, lines 200-240): change `ftp_value.get("ftp_watts", COLD_START_FTP)` to `ftp_value.get("ftp", COLD_START_FTP)`, then add the same `supabase.table("profiles").update({"ftp": resolved_ftp}).eq("user_id", user_id).execute()` call inside a narrow `try/except Exception as exc: logger.warning(...)` — copy the exact best-effort logging idiom already used at line 513-515 (`except Exception as exc: logger.warning("Storage upload failed (best-effort): %s", exc)`).

**Inline-await conversion:** `process_ride_background` (lines 248-419) currently structured as sequential `try/except` blocks per step, each independently best-effort logged (e.g. lines 290-304, 351-359, 362-380). Keep this per-step try/except structure — it is the established resilience pattern in this file — but call the whole function with `await process_ride_background(...)` directly in `upload_fit` instead of `background_tasks.add_task(...)`, and change the response `"status"` field from `"processing"` to `"processed"` per Pitfall 3.

**Ride-session link fix (Pattern 4, replaces lines 318-337):** change `.eq("scheduled_date", date.today().isoformat())` to `.eq("scheduled_date", ride_date).eq("status", "planned")`, and after a match, add `await supabase.table("sessions").update({"status": "completed"}).eq("id", matched_session["id"]).eq("user_id", user_id).execute()` plus `ride_update["session_id"] = matched_session["id"]`, reusing the same `ride_update` dict pattern already at line 339-349.

---

### `backend/pmc_recompute.py` (new service, batch/transform)

**Analog:** the PMC section of `process_ride_background` (lines 286-381) — reuse the exact `update_pmc(prev_ctl, prev_atl, tss, days_of_data)` call signature and the exact `pmc_history` upsert shape (`on_conflict="user_id,date"`), just looped over a day-series instead of one step.

**Core pattern to copy (upsert call shape, lines 362-380):**
```python
await (
    supabase.table("pmc_history")
    .upsert(
        {
            "user_id": user_id,
            "date": date.today().isoformat(),
            "ctl": new_ctl,
            "atl": new_atl,
            "tsb": new_tsb,
            "tss": tss if tss is not None else 0.0,
            "tss_display_ready": tss_display_ready,
            "days_of_data": days_of_data + 1,
        },
        on_conflict="user_id,date",
    )
    .execute()
)
```
Extend to a **list** of dicts (bulk upsert, one call) per RESEARCH.md Pattern 2 — `supabase-py`'s `.upsert()` already accepts a list, confirmed via this same call shape. Import `update_pmc` from `backend.sports_science.pmc` exactly as `process_ride_background` already does at the top of `rides.py` (check existing `from backend.sports_science.pmc import update_pmc` style import at top of `rides.py` and copy verbatim into the new module).

**Error handling:** wrap the whole recompute in the same best-effort `try/except Exception as exc: logger.error(...)` idiom used at lines 380-381, since it is called inline from the upload pipeline and a PMC failure must not 500 the ride upload response (mirrors existing resilience philosophy in this file).

---

### `backend/routes/adaptations.py` (route, CRUD + event-driven)

**Analog:** same file, existing `mark_session_missed` (lines 651-720) for the ownership-check + re-detect pattern, and `log_adaptation` (line 284) for the insert-a-row pattern.

**Ownership-check pattern to copy for new `POST /{id}/confirm`** (`mark_session_missed`, lines 664-685):
```python
user_id = current_user["user_id"]
validate_uuid(user_id, "user_id")
validate_uuid(session_id, "session_id")  # -> validate_uuid(adaptation_id, "adaptation_id")
supabase = await _get_async_supabase()

session_resp = await (
    supabase.table("sessions")
    .select("id, user_id, status")
    .eq("id", session_id)
    .eq("user_id", user_id)
    .execute()
)
session_rows = session_resp.data or []
if not session_rows:
    raise HTTPException(
        status_code=404,
        detail={"error": "session_not_found", "detail": "Session not found or does not belong to this user."},
    )
```
For `/confirm`, replace the `.select(...)` target with `adaptations` and add a third filter `.eq("status", "proposed")`, and the 404 detail becomes `{"error": "proposal_not_found", "detail": "No pending macro-replan proposal for this id"}` (already spec'd exactly this way in RESEARCH.md Pattern 6 — copy verbatim).

**Best-effort, non-fatal exception pattern for calendar/signal side-effects** (lines 687-713):
```python
try:
    signals = await detect_signals(user_id)
    scope = decide_scope(signals)
    ...
except Exception:
    logger.warning("Signal detection/adaptation failed for session %s (non-fatal)", session_id, exc_info=True)
```
Reuse this exact non-fatal wrapper shape anywhere Phase 6 adds calendar-sync fire-and-forget calls around the new `trigger_session_ids` bookkeeping.

**`detect_signals` idempotency rewrite:** existing function signature at line 80 (`async def detect_signals(user_id: str, window_days: int = 7) -> list[dict]`) is kept; only its query body changes per RESEARCH.md Pattern 5 (add the `already_consumed`/`consumed_ids` pre-query, filter `sessions_resp` against it). No signature or calling-convention change needed elsewhere in the file.

---

### `supabase/migrations/0005_phase6_persistence.sql` (migration, schema DDL)

**Analog:** `supabase/migrations/0003_phase4_schema.sql` (full file, 54 lines) — copy its structure exactly.

**Style to copy verbatim:**
```sql
-- PacerAI: Phase 6 schema additions
-- Migration: 0005_phase6_persistence
-- Applied via: supabase db push --linked --yes
-- Purpose: <one-line summary>

-- ============================================================
-- 1. <table>: <purpose>
-- ============================================================
-- <column>: <why, cross-reference to code that already reads/writes it>
ALTER TABLE public.<table>
  ADD COLUMN IF NOT EXISTS <column> <type>;
```
All `ADD COLUMN` statements MUST use `IF NOT EXISTS` (idempotency against a live schema, per the `0003` file's own stated rationale in its header comment). Required additions per RESEARCH.md: `pmc_history.tss numeric`, `pmc_history.days_of_data int NOT NULL DEFAULT 0`, `sessions` CHECK constraint drop+recreate to add `'missed'`, `profiles.ftp numeric`, `profiles.lthr numeric`, `rides.content_hash text` + `UNIQUE (user_id, content_hash)`, `adaptations.trigger_session_ids uuid[]`, `adaptations.status text DEFAULT 'applied'` (for the proposed/applied/superseded lifecycle).

**CHECK constraint drop+recreate pattern** — no existing analog in `0001`-`0004` (none of them alter a CHECK constraint); use standard Postgres form:
```sql
ALTER TABLE public.sessions DROP CONSTRAINT IF EXISTS sessions_status_check;
ALTER TABLE public.sessions ADD CONSTRAINT sessions_status_check
  CHECK (status IN ('planned','completed','skipped','partial','missed'));
```
(Constraint name must be verified against `0001_initial_schema.sql`'s actual generated/explicit name before finalizing — flag for the planner to confirm the exact constraint name via `\d sessions` or re-reading `0001` if not already known.)

---

### Test files (`tests/api/test_rides.py`, `tests/api/test_adaptations.py`, `tests/test_pmc_recompute.py`)

**Analog:** `tests/api/conftest.py::mock_supabase_factory` (lines 77-110) — the single shared mocking seam for all route-level integration tests in this repo.

**Pattern to copy for every new integration test case:**
```python
from tests.api.conftest import TEST_USER_ID, auth_headers, mock_supabase_factory

def test_new_behavior(client, monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(module, "_get_async_supabase", mock_supabase_factory([{"id": "...", ...}]))
    response = client.post("/rides/upload", ..., headers=auth_headers())
    assert response.status_code == 200
```
Note the limitation explicitly called out in RESEARCH.md Pitfall 2/Pitfall 1: `mock_supabase_factory`'s mock client accepts any payload shape and cannot catch a CHECK-constraint or missing-column error — new tests asserting schema-legality (e.g. "missed_status_value") must assert on the **outgoing update payload's status value**, not on a live constraint round-trip (a separate manual/live verification step is required per Wave 0 gaps in RESEARCH.md, not automatable here).

**Pure-function unit test style to copy for `tests/test_pmc_recompute.py`:** follow `tests/sports_science/test_pmc.py`'s pattern of calling `update_pmc(...)` directly with fixed inputs and asserting on `.value` dict keys — no Supabase mock needed for the day-series-building logic itself; only test the DB-touching upsert call shape (if at all) via `mock_supabase_factory`.

## Shared Patterns

### Async Supabase singleton access
**Source:** `backend/routes/rides.py` / `backend/routes/adaptations.py` (both call `supabase = await _get_async_supabase()` at the top of each route/helper function)
**Apply to:** `backend/pmc_recompute.py`, `_persist_generated_plan` in `agent/tools.py`
```python
supabase = await _get_async_supabase()
```

### Dual-filter ownership check (IDOR mitigation)
**Source:** `backend/routes/adaptations.py:670-676` (`mark_session_missed`)
**Apply to:** new `POST /adaptations/{id}/confirm`, ride dedup lookup, any endpoint touching a row by id
```python
.select(...).eq("id", <row_id>).eq("user_id", user_id).execute()
```

### Best-effort / non-fatal side-effect wrapper
**Source:** `backend/routes/rides.py:513-515`, `:335-336`, `:380-381`; `backend/routes/adaptations.py:710-713`
**Apply to:** PMC recompute call from the ride pipeline, calendar sync fire-and-forget, ride-debrief conversation insert
```python
try:
    ...
except Exception as exc:
    logger.warning("<operation> failed (non-fatal): %s", exc)
```
Caution (Pitfall 1 lesson): do not use this wrapper around a write whose success the rest of the system silently depends on (e.g. the `pmc_history` upsert previously failed silently for this exact reason) — log loudly (`logger.error`, not `.warning`) and consider surfacing a status field when the swallowed failure would otherwise look like success downstream.

### Bulk upsert with `on_conflict`
**Source:** `backend/routes/rides.py:362-379` (`pmc_history` upsert, single-row form)
**Apply to:** `backend/pmc_recompute.py` (multi-row form, same `on_conflict="user_id,date"` key)
```python
await supabase.table("pmc_history").upsert(rows_to_upsert, on_conflict="user_id,date").execute()
```

### Migration file structure
**Source:** `supabase/migrations/0003_phase4_schema.sql` (full file)
**Apply to:** `supabase/migrations/0005_phase6_persistence.sql`
Numbered `-- ====` sections per table, header comment block with Migration/Applied-via/Purpose, `ADD COLUMN IF NOT EXISTS` throughout.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/routes/adaptations.py::POST /{id}/confirm` (new endpoint) | route/controller | event-driven (two-phase propose/confirm) | No prior two-phase propose/confirm flow exists anywhere in the codebase; closest structural analog is the ownership-check shape of `mark_session_missed`, but the "stored snapshot, later applied verbatim" semantics are novel to this phase — implement per RESEARCH.md Pattern 6 code example directly |
| CHECK constraint ALTER for `sessions.status` | migration | schema DDL | `0001`-`0004` never alter a CHECK constraint; standard Postgres `DROP CONSTRAINT IF EXISTS` / `ADD CONSTRAINT` form used instead, constraint name must be confirmed against `0001_initial_schema.sql` before finalizing |

## Metadata

**Analog search scope:** `backend/agent/`, `backend/routes/`, `backend/sports_science/`, `supabase/migrations/`, `tests/api/`, `tests/sports_science/`
**Files scanned:** `backend/agent/tools.py`, `backend/routes/rides.py`, `backend/routes/adaptations.py`, `supabase/migrations/0001-0004`, `tests/api/conftest.py`
**Pattern extraction date:** 2026-07-03
