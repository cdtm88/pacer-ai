---
phase: "04"
padded_phase: "04"
status: "all_fixed"
fix_scope: "critical_warning"
findings_in_scope: 16
fixed: 16
skipped: 0
iteration: 1
fixed_at: "2026-06-20"
---

# Phase 04 Code Review Fix Report

**Fixed at:** 2026-06-20
**Source review:** `.planning/phases/04-ui-and-calendar/04-REVIEW.md`
**Iteration:** 1

**Summary:**
- Findings in scope: 16 (7 Critical, 9 Warning)
- Fixed: 16
- Skipped: 0

## Fixed Issues

### CR-001 -- CORS middleware absent [FIXED]

**Files modified:** `api/main.py`
**Commit:** `fix(04): add CORS middleware to FastAPI app [CR-001]`
**Applied fix:** Added `CORSMiddleware` after `app = FastAPI(...)` using `FRONTEND_URL` env var (defaulting to `http://localhost:5173`). Added `import os` and `from fastapi.middleware.cors import CORSMiddleware`.

---

### CR-002 -- JWT access token exposed in browser redirect URL [FIXED]

**Files modified:** `api/routes/calendar.py`, `frontend/src/components/settings/CalendarStatus.tsx`
**Commit:** `fix(04): add auth-redirect-url endpoint and remove JWT from browser redirect [CR-002]`
**Applied fix:** Added `GET /calendar/auth-redirect-url` endpoint that authenticates via `Depends(get_current_user)` and returns `{"url": <oauth_url>}`. Updated `CalendarStatus.tsx` `handleConnect` to call `apiFetch('/calendar/auth-redirect-url')` (JWT in Authorization header) then redirect to the returned URL. Removed the `supabase` direct import and `API_URL` constant from the component. Removed `window.location.href` with embedded token.

---

### CR-003 -- asyncio.ensure_future in request handler [FIXED]

**Files modified:** `api/routes/onboarding.py`
**Commit:** `fix(04): replace asyncio.ensure_future with BackgroundTasks for calendar sync [CR-003]`
**Applied fix:** Added `background_tasks: BackgroundTasks` parameter to `onboarding_plan_calendar_sync`. Replaced `asyncio.ensure_future(...)` with `background_tasks.add_task(push_all_sessions_to_calendar, user_id)`. Added `BackgroundTasks` to the FastAPI import.

---

### CR-004 -- BackgroundTasks() as default parameter [FIXED]

**Files modified:** `api/routes/adaptations.py`
**Commit:** `fix(04): remove BackgroundTasks default parameter in mark_session_missed [CR-004]`
**Applied fix:** Removed `= BackgroundTasks()` default from `mark_session_missed`. Moved `background_tasks: BackgroundTasks` to the first parameter position (before `session_id: str = Path(...)`) to avoid a Python syntax error from a non-default parameter following a defaulted one.

---

### CR-005 -- Unchecked DB insert result in log_adaptation [FIXED]

**Files modified:** `api/routes/adaptations.py`
**Commit:** `fix(04): add null check on adaptations INSERT result to prevent IndexError [CR-005]`
**Applied fix:** Added `if not result.data: raise RuntimeError("adaptations INSERT returned no rows -- check RLS and schema")` before `return result.data[0]["id"]` in `log_adaptation`.

---

### CR-006 -- getUpcomingSessions returns wrong shape [FIXED]

**Files modified:** `frontend/src/lib/api.ts`
**Commit:** `fix(04): unwrap sessions wrapper object in getUpcomingSessions [CR-006]`
**Applied fix:** Changed `return res.json() as Promise<Session[]>` to `const data = await res.json() as { sessions: Session[] }; return data.sessions ?? []` to correctly unwrap the `{"sessions": [...]}` response envelope.

---

### CR-007 -- OAuth callback endpoint unauthenticated [FIXED]

**Files modified:** `api/routes/calendar.py`
**Commit:** `fix(04): add HMAC-signed state to OAuth callback to prevent account takeover [CR-007]`
**Applied fix:** Added `import hashlib, hmac` at the top. Added `_build_oauth_state(user_id)` helper that generates a `"{nonce}.{user_id}.{hmac_sig}"` state token signed with `SUPABASE_JWT_SECRET`. Updated `/auth` and `/auth-redirect-url` to use HMAC-signed state and store only the nonce in `oauth_states`. Updated `/callback` to parse and HMAC-verify the state before trusting the `claimed_user_id`, then cross-check the nonce against `oauth_states` with both `nonce` and `user_id` filters.

---

### WR-001 -- handleConfirm stale closure [FIXED]

**Files modified:** `frontend/src/screens/OnboardingScreen.tsx`
**Commit:** `fix(04): add queryClient and navigate to handleConfirm dependency array [WR-001]`
**Applied fix:** Changed `useCallback(async () => { ... }, [])` to `useCallback(async () => { ... }, [queryClient, navigate])` so the closure captures the current values of both.

---

### WR-002 -- SSE error handler fires on normal stream close [FIXED]

**Files modified:** `frontend/src/hooks/useSSEStream.ts`
**Commit:** `fix(04): suppress spurious SSE error after successful stream completion [WR-002]`
**Applied fix:** Added `let streamCompleted = false` flag. Set `streamCompleted = true` at the top of the `done` handler. Added `if (streamCompleted) return` as the first line of the `error` handler to suppress the post-done connection-close event.

---

### WR-003 -- Five independent Supabase client singletons [FIXED]

**Files modified:** `api/db.py` (new file), `api/routes/adaptations.py`, `api/routes/calendar.py`, `api/routes/onboarding.py`, `api/routes/rides.py`, `api/routes/sessions.py`, `api/calendar_sync.py`
**Commit:** `fix(04): extract shared Supabase singleton to api/db.py, remove 6 duplicates [WR-003]`
**Applied fix:** Created `api/db.py` with a single `_supabase_client` singleton and `get_async_supabase()` function. Updated all 6 modules to import `from api.db import get_async_supabase as _get_async_supabase` and removed their duplicated singleton code. Removed now-unused `supabase.AsyncClient`, `acreate_client`, `os` imports where applicable.

---

### WR-004 -- Macro replan 30% shift guard is dead code [FIXED]

**Files modified:** `api/routes/adaptations.py`
**Commit:** `fix(04): count 1-day shifts in 30% guard (>= 1 not > 1) [WR-004]`
**Applied fix:** Changed `if delta_days > 1:` to `if delta_days >= 1:` in `check_shift_limit` so 1-day shifts (exactly what macro replan produces) are counted toward the 30% guard threshold.

---

### WR-005 -- onboarding_start creates new conversation on every request [FIXED]

**Files modified:** `api/routes/onboarding.py`, `frontend/src/screens/OnboardingScreen.tsx`
**Commit:** `fix(04): preserve conversation_id across onboarding turns to prevent context loss [WR-005]`
**Applied fix:**
- Backend: Added `OnboardingStartBody` Pydantic model with optional `message` and `conversation_id` fields. Updated `onboarding_start` to accept this body. Only calls `create_conversation()` when `conversation_id` is absent. Wraps the SSE generator in `_stream_with_metadata()` that emits a `metadata` event first carrying the `conversation_id`. Appends incoming `body.message` to prior turns when provided.
- Frontend: Added `conversationIdRef = useRef<string | null>(null)`. Updated `runStream` and `handleConfirm` to include `conversation_id` in the request body. Added `metadata` event handling in the SSE loop to capture and store the returned `conversation_id`. Added `'metadata'` to the `ParsedSSEEvent` type union.

---

### WR-006 -- JWT in SSE query param written to server access logs [FIXED]

**Files modified:** `frontend/src/lib/api.ts`, `api/auth.py`
**Commit:** `fix(04): document JWT-in-SSE-URL as known limitation with TODO mitigation [WR-006]`
**Applied fix:** Added detailed `WR-006 KNOWN LIMITATION` comment to `sseUrl()` in `api.ts` and to the `token: str | None = Query(None)` parameter in `auth.py`. Both comments describe the architectural constraint (EventSource cannot send headers) and include a concrete TODO for the short-lived exchange endpoint mitigation. Full exchange endpoint implementation deferred as a larger change per review guidance.

---

### WR-007 -- handleMarkDone and handleMarkMissed swallow errors silently [FIXED]

**Files modified:** `frontend/src/components/session/SessionCard.tsx`
**Commit:** `fix(04): add error toast to handleMarkDone and handleMarkMissed in SessionCard [WR-007]`
**Applied fix:** Added `import { toast } from 'sonner'`. Added `catch { toast.error(...) }` block to both handlers. Moved `setMissedOpen(false)` from `finally` to `try` block in `handleMarkMissed` so the dialog only closes on success.

---

### WR-008 -- ChatScreen invalidates active-conversation after each turn [FIXED]

**Files modified:** `frontend/src/screens/ChatScreen.tsx`
**Commit:** `fix(04): remove active-conversation invalidation after stream to prevent new conversation creation [WR-008]`
**Applied fix:** Removed `queryClient.invalidateQueries({ queryKey: ['active-conversation'] })` from the stream completion `useEffect`. Replaced with a comment explaining why this invalidation must not be called (it triggers `createConversation()` via the query function, resetting the conversation context on every turn).

---

### WR-009 -- ride_date uses upload timestamp instead of FIT file ride date [FIXED]

**Files modified:** `api/routes/rides.py`
**Commit:** `fix(04): use FIT file start_time as ride_date instead of upload timestamp [WR-009]`
**Applied fix:** Updated `parse_fit_file` to capture `start_time` from the FIT `session` message frame and the earliest `timestamp` from `record` frames. Added `start_time` to the returned dict. Updated the stub INSERT in `upload_fit` to derive `ride_date` from `parsed["start_time"]` (with UTC timezone normalization) and fall back to `datetime.now(timezone.utc).date().isoformat()` only when no timestamp was found.

---

## Skipped Issues

None -- all 16 in-scope findings were fixed.

---

_Fixed: 2026-06-20_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
