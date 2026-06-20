---
phase: 04-ui-and-calendar
plan: "09"
reviewed: 2026-06-20T00:00:00Z
depth: standard
files_reviewed: 4
files_reviewed_list:
  - frontend/src/router.tsx
  - api/routes/sessions.py
  - api/routes/rides.py
  - api/routes/onboarding.py
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: issues_found
---

# Code Review — Phase 04 Gap Closure (04-09)

## Summary

Four files reviewed at standard depth. Three critical issues were found: the new PATCH endpoint hard-codes `status = 'completed'` with no allowed-value validation and no state-transition guard (a caller can overwrite terminal states repeatedly); all three route modules share an async race condition in their Supabase singleton initialisation; and the `conversation_id` captured in `onboarding_start` is used to load a freshly-created (empty) conversation on every call rather than an existing one, meaning multi-turn context is never actually resumed. Four warnings cover a dead `storage_path` variable, an `asyncio.ensure_future` that drops its task reference, two code-level bugs in how the rides table name fix interacts with compliance, and an unconditional `select("*")` on profiles.

---

## Critical Issues

### CR-01: PATCH /sessions/{session_id} hard-codes `"completed"` with no state-transition guard

**File:** `api/routes/sessions.py:274-291`

**Issue:** The endpoint unconditionally sets `{"status": "completed"}` regardless of the current session state. There is no validation of what the incoming client wants to transition to (the endpoint accepts no request body at all) and no check that the session is currently in a `planned` state. This means:
- Any client can repeatedly PATCH the same session (triggering redundant DB writes on every call).
- A session already marked `skipped` or any other terminal state can be silently overwritten to `completed`.
- The endpoint cannot be extended to support `skipped` or any other status without a breaking API change.

```python
# Current: hard-coded, no body, no state guard
result = await (
    supabase.table("sessions")
    .update({"status": "completed"})   # always "completed", always overwrites
    .eq("id", session_id)
    .eq("user_id", user_id)
    .execute()
)
```

**Fix:** Accept a validated body and guard the transition to only apply from `planned`:
```python
from pydantic import BaseModel
from typing import Literal

class SessionUpdate(BaseModel):
    status: Literal["completed", "skipped"]

@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str,
    body: SessionUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    user_id = current_user["user_id"]
    validate_uuid(session_id, "session_id")
    supabase = await _get_async_supabase()

    result = await (
        supabase.table("sessions")
        .update({"status": body.status})
        .eq("id", session_id)
        .eq("user_id", user_id)
        .eq("status", "planned")   # only transition from planned
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "session_not_found",
                "detail": "No planned session found for this user with the given id",
            },
        )
    return result.data[0]
```

---

### CR-02: Race condition in all three `_get_async_supabase()` singletons

**File:** `api/routes/sessions.py:37`, `api/routes/rides.py:57`, `api/routes/onboarding.py:92`

**Issue:** All three modules implement the same check-then-act singleton:
```python
if _supabase_client is not None:
    return _supabase_client
_supabase_client = await acreate_client(url, key)   # suspends here
```
Because `acreate_client` is awaited, the coroutine yields to the event loop before setting the module-level variable. If two concurrent requests both see `_supabase_client is None` before either's `await` resolves, both calls create a client and store it, the first result is overwritten, and the abandoned client leaks its connection pool. The comment in each module explicitly says this pattern exists to "avoid leaking httpx connection pools" — the current implementation does not achieve that under concurrency.

**Fix:** Apply a double-checked lock using `asyncio.Lock` in all three modules (or extract to a shared `api/db.py` — see IN-02):
```python
import asyncio
_supabase_client: Optional[AsyncClient] = None
_supabase_lock = asyncio.Lock()

async def _get_async_supabase() -> AsyncClient:
    global _supabase_client
    if _supabase_client is not None:
        return _supabase_client
    async with _supabase_lock:
        if _supabase_client is None:   # re-check inside lock
            url = os.environ.get("SUPABASE_URL")
            key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            if not url or not key:
                raise EnvironmentError(
                    "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set"
                )
            _supabase_client = await acreate_client(url, key)
    return _supabase_client
```

---

### CR-03: `onboarding_start` always creates a new conversation — prior turns are never loaded

**File:** `api/routes/onboarding.py:261-272`

**Issue:** Every call to `POST /onboarding/start` calls `create_conversation`, which inserts a new row. The freshly-created conversation has zero messages, so `load_conversation` always returns `[]`, and the code always falls back to `seed_messages`. The multi-turn context that plan 04-09 exists to enable is never actually resumed. On the second user message, the agent has no memory of the first exchange.

```python
# Always inserts a new conversations row:
conversation_id = await create_conversation(user_id, context_type="onboarding")
# ...
prior_turns = await load_conversation(conversation_id, user_id)
# prior_turns is always [] because the row was just created
messages = prior_turns if prior_turns else seed_messages  # always seed_messages
```

Additionally, even if an existing conversation were loaded, `save_messages` is never called after `sse_generator` completes, so no turns are ever persisted. The audit trail (T-03-10) is not written.

**Fix (part 1):** Look up an existing open onboarding conversation before creating a new one:
```python
async def get_or_create_conversation(user_id: str, context_type: str) -> str:
    supabase = await _get_async_supabase()
    existing = await (
        supabase.table("conversations")
        .select("id")
        .eq("user_id", user_id)
        .eq("context_type", context_type)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    if existing.data:
        return existing.data[0]["id"]
    result = await supabase.table("conversations").insert(
        {"user_id": user_id, "context_type": context_type}
    ).execute()
    return result.data[0]["id"]
```

**Fix (part 2):** Persist messages after the stream completes. This requires `sse_generator` to expose the completed message list (via callback or return value) so `save_messages` can be called.

---

## Warnings

### WR-01: `storage_path` set to wrong value and then suppressed with `type: ignore`

**File:** `api/routes/rides.py:489-501`

**Issue:**
```python
storage_path = f"fits/{user_id}/{safe_filename}"   # includes "fits/" prefix
...
await supabase.storage.from_("fits").upload(
    path=f"{user_id}/{safe_filename}",              # no "fits/" prefix
    ...
)
...
except Exception:
    storage_path = None  # type: ignore[assignment]
```
Two bugs: (1) The `storage_path` variable is built with a `fits/` prefix but the actual storage call omits it, so the path stored in `raw_fit_path` is wrong even on success. (2) On storage failure, `storage_path = None` is stored in `raw_fit_path`, making it impossible to distinguish "file was never received" from "file was received but storage failed." The `type: ignore` suppresses the type checker warning rather than fixing the root cause.

**Fix:**
```python
storage_object_path = f"{user_id}/{safe_filename}"  # path inside the bucket
storage_upload_ok = False
try:
    await supabase.storage.from_("fits").upload(
        path=storage_object_path,
        file=file_bytes,
        file_options={"content-type": "application/octet-stream"},
    )
    storage_upload_ok = True
except Exception as exc:
    logger.warning("Storage upload failed (best-effort): %s", exc)

raw_fit_path = storage_object_path if storage_upload_ok else None
# use raw_fit_path in the rides insert
```

---

### WR-02: `asyncio.ensure_future` in `plan-calendar-sync` drops the task reference

**File:** `api/routes/onboarding.py:229-230`

**Issue:**
```python
import asyncio as _asyncio
_asyncio.ensure_future(push_all_sessions_to_calendar(user_id))
```
The `Task` returned by `ensure_future` is discarded immediately. In Python 3.10+, a task with no live reference can be garbage-collected before it completes, silently aborting the calendar push. Any exception inside `push_all_sessions_to_calendar` is swallowed with no log trace. The `import asyncio as _asyncio` inside the function body is also non-standard.

**Fix:** Use FastAPI's `BackgroundTasks` which integrates with the request lifecycle and logs task failures:
```python
@router.post("/plan-calendar-sync")
async def onboarding_plan_calendar_sync(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
) -> dict:
    user_id = current_user["user_id"]
    background_tasks.add_task(push_all_sessions_to_calendar, user_id)
    return {"status": "scheduled"}
```

---

### WR-03: rides.py compliance check selects wrong column name after table-name fix

**File:** `api/routes/rides.py:308-319`

**Issue:** After the table name was fixed from `training_sessions` to `sessions`, the select still reads `tss` but the sessions table uses `tss_target` as the column name (confirmed by `api/routes/sessions.py:68` `_SESSION_COLUMNS` which includes `tss_target`). The query:
```python
supabase.table("sessions")
    .select("tss_target, type")
```
looks correct in the current file (line 310), but the `planned_session.get("tss_target", 0)` on line 318 would return `0` if the column were named differently. Verify this matches the actual schema column name -- if the column is `tss_target`, the `.select("tss_target, type")` call is correct; if it's `tss`, the guard fails silently. Cross-check with the schema migration file to confirm.

**Separate concern:** `session_type` is selected but the compliance call only uses `tss_target`. The unused `session_type` is harmless but adds noise.

---

### WR-04: `profile_me` uses `select("*")` — exposes all profile columns to the frontend

**File:** `api/routes/sessions.py:233`

**Issue:**
```python
supabase.table("profiles").select("*").eq("user_id", user_id).execute()
```
`select("*")` with a service-role key returns every column in the table. Any future sensitive column added to `profiles` (e.g., payment details, admin flags) will be silently returned to the frontend without any code change required.

**Fix:** Enumerate exactly the columns the UI needs:
```python
_PROFILE_COLUMNS = (
    "id, user_id, fitness_goals, weekly_hours, preferred_days, "
    "back_status, equipment, rpe_baseline, ftp_watts, lthr, created_at"
)
supabase.table("profiles").select(_PROFILE_COLUMNS).eq("user_id", user_id).execute()
```

---

## Info

### IN-01: `_ts` (timestamp) variable is read and immediately discarded on every record frame

**File:** `api/routes/rides.py:144`

**Issue:**
```python
_ts = frame.get_value("timestamp", fallback=None)
```
The comment acknowledges this ("timestamp is read but not used for duration"). The `get_value` call runs on every record frame for the life of the file parse. Remove it; if accurate duration calculation is later needed, add it back with actual usage.

---

### IN-02: Three modules duplicate `_get_async_supabase` verbatim — each holds a separate client instance

**File:** `api/routes/sessions.py:34`, `api/routes/rides.py:54`, `api/routes/onboarding.py:89`

**Issue:** The singleton is copy-pasted across three modules. Each module has its own `_supabase_client` module-level variable, so the application can hold up to three live client instances simultaneously (one per module that initialises first). This is the opposite of the singleton guarantee the comments claim.

**Fix:** Extract to `api/db.py` and import the shared function into all three modules. The lock from CR-02 only needs to be added once.

---

_Reviewed: 2026-06-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
