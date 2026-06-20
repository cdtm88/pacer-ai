---
phase: "04"
phase_name: "ui-and-calendar"
status: "issues-found"
depth: "standard"
files_reviewed: 66
files_reviewed_list:
  - api/auth.py
  - api/calendar_sync.py
  - api/main.py
  - api/routes/adaptations.py
  - api/routes/calendar.py
  - api/routes/chat.py
  - api/routes/onboarding.py
  - api/routes/rides.py
  - api/routes/sessions.py
  - frontend/.env.example
  - frontend/components.json
  - frontend/index.html
  - frontend/package.json
  - frontend/src/components/AppLayout.tsx
  - frontend/src/components/chat/ChatBubble.tsx
  - frontend/src/components/chat/ChatInput.tsx
  - frontend/src/components/history/CtlSparkline.tsx
  - frontend/src/components/history/FitUploadZone.tsx
  - frontend/src/components/history/RideRow.tsx
  - frontend/src/components/nav/BottomTabBar.tsx
  - frontend/src/components/nav/DesktopSidebar.tsx
  - frontend/src/components/pwa/IOSInstallBanner.tsx
  - frontend/src/components/session/SessionCard.tsx
  - frontend/src/components/session/SessionStepList.tsx
  - frontend/src/components/session/TsbChip.tsx
  - frontend/src/components/session/ZoneChip.tsx
  - frontend/src/components/settings/CalendarStatus.tsx
  - frontend/src/components/ui/accordion.tsx
  - frontend/src/components/ui/alert-dialog.tsx
  - frontend/src/components/ui/badge.tsx
  - frontend/src/components/ui/button.tsx
  - frontend/src/components/ui/separator.tsx
  - frontend/src/components/ui/skeleton.tsx
  - frontend/src/components/ui/tooltip.tsx
  - frontend/src/hooks/useAuth.ts
  - frontend/src/hooks/useCalendarStatus.ts
  - frontend/src/hooks/useSSEStream.ts
  - frontend/src/index.css
  - frontend/src/lib/api.ts
  - frontend/src/lib/supabase.ts
  - frontend/src/lib/utils.ts
  - frontend/src/main.tsx
  - frontend/src/router.tsx
  - frontend/src/screens/AgendaScreen.tsx
  - frontend/src/screens/ChatScreen.tsx
  - frontend/src/screens/DuringSessionScreen.tsx
  - frontend/src/screens/HistoryScreen.tsx
  - frontend/src/screens/LoginScreen.tsx
  - frontend/src/screens/OnboardingScreen.tsx
  - frontend/src/screens/SettingsScreen.tsx
  - frontend/src/screens/TodayScreen.tsx
  - frontend/src/stores/authStore.ts
  - frontend/src/stores/uiStore.ts
  - frontend/src/tests/auth.test.tsx
  - frontend/src/tests/history.test.tsx
  - frontend/src/tests/onboarding.test.tsx
  - frontend/src/tests/pwa.test.tsx
  - frontend/src/tests/setup.ts
  - frontend/src/tests/today.test.tsx
  - frontend/src/vite-env.d.ts
  - frontend/tsconfig.app.json
  - frontend/tsconfig.json
  - frontend/vercel.json
  - frontend/vite.config.ts
  - frontend/vitest.config.ts
  - supabase/migrations/0003_phase4_schema.sql
  - tests/api/conftest.py
  - tests/api/test_adaptations.py
  - tests/api/test_auth.py
  - tests/api/test_calendar.py
  - tests/api/test_onboarding.py
  - tests/api/test_rides.py
  - tests/api/test_sessions.py
findings:
  critical: 7
  warning: 9
  info: 4
  total: 20
reviewed_at: "2026-06-20"
---

# Phase 04 Code Review

## Summary

The Phase 4 implementation is architecturally sound on the auth and data-isolation axes, but carries several correctness defects that will cause crashes or silent data loss in production. The most severe issues are: a missing CORS middleware that blocks all browser API calls; JWT tokens exposed in server-side redirect URLs and browser history; a `BackgroundTasks()` instantiation anti-pattern that silently discards calendar sync work; unchecked DB insert results that crash the adaptation logging path; and a frontend API type mismatch where `getUpcomingSessions` deserializes to the wrong shape. The JWT verification implementation is correct; the calendar OAuth CSRF guard and Fernet encryption are solid.

---

## Findings

### CR-001 — CORS middleware absent: all browser API calls blocked [CRITICAL]

**File:** `api/main.py:27`
**Issue:** The FastAPI application has no `CORSMiddleware` registered. The frontend runs at a different origin from the API server (`VITE_API_URL`); every `fetch` and `EventSource` request from the browser will be blocked by the browser's CORS preflight check. No REST endpoint or SSE stream is reachable from the browser in any deployed environment.
**Fix:**
```python
from fastapi.middleware.cors import CORSMiddleware
import os

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("FRONTEND_URL", "http://localhost:5173")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

### CR-002 — JWT access token exposed in browser redirect URL and server logs [CRITICAL]

**File:** `frontend/src/components/settings/CalendarStatus.tsx:30`
**Issue:** `handleConnect` constructs `window.location.href = \`${API_URL}/calendar/auth?token=${encodeURIComponent(token)}\`` which embeds the Supabase access token as a query parameter in a browser navigation. This causes the full JWT to appear in: (1) browser history, (2) server access logs on the API server, (3) any CDN or reverse-proxy request logs, and (4) the `Referer` header on subsequent requests. Access tokens are long-lived (typically 1 hour) and are full bearer credentials. The `/calendar/auth` backend endpoint already accepts `?token=` as an SSE fallback for `get_current_user`, so this technically authenticates, but the exposure is a security defect.
**Fix:** Replace the direct redirect with a fetch that passes the token in the Authorization header, then redirects to the returned URL:
```typescript
async function handleConnect() {
  const res = await apiFetch('/calendar/auth-redirect-url')
  if (res.ok) {
    const { url } = await res.json() as { url: string }
    window.location.href = url
  }
}
```
On the backend, add a `GET /calendar/auth-redirect-url` endpoint that builds and returns the Google OAuth URL (authenticated via `Depends(get_current_user)`) without performing a redirect, keeping the token out of the URL.

---

### CR-003 — `asyncio.ensure_future` in request handler: calendar push dropped under multi-worker deployments [CRITICAL]

**File:** `api/routes/onboarding.py:230`
**Issue:** `_asyncio.ensure_future(push_all_sessions_to_calendar(user_id))` schedules a coroutine on the current event loop without registering it with FastAPI's `BackgroundTasks` mechanism. Under Gunicorn with multiple Uvicorn workers, or when the worker process is recycled before the coroutine completes, the future is silently dropped. Additionally, `ensure_future` does not attach error handling; any exception inside `push_all_sessions_to_calendar` will produce an "unhandled exception in asyncio Future" warning and the caller will never know.
**Fix:**
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

### CR-004 — `BackgroundTasks()` as default parameter: calendar sync silently never executes [CRITICAL]

**File:** `api/routes/adaptations.py:679`
**Issue:** `mark_session_missed` declares `background_tasks: BackgroundTasks = BackgroundTasks()`. FastAPI injects a `BackgroundTasks` instance at request time and executes its registered tasks after the response is sent. A `BackgroundTasks()` created as a Python default parameter value is a stale empty instance that is never connected to FastAPI's response lifecycle. Calls to `background_tasks.add_task(update_calendar_event, ...)` on lines 729-730 register tasks on this disconnected object, which FastAPI will never execute. Every calendar sync triggered by `mark_session_missed` is silently dropped.
**Fix:**
```python
@router.post("/sessions/{session_id}/missed")
async def mark_session_missed(
    session_id: str = Path(...),
    background_tasks: BackgroundTasks,          # no default
    current_user: dict = Depends(get_current_user),
) -> dict:
```

---

### CR-005 — Unchecked DB insert result in `log_adaptation`: `IndexError` on empty response [CRITICAL]

**File:** `api/routes/adaptations.py:340`
**Issue:** `log_adaptation` returns `result.data[0]["id"]` without verifying that `result.data` is non-empty. If the Supabase insert fails silently (RLS rejection, constraint violation, transient network error), `result.data` is `[]` and `result.data[0]` raises `IndexError`. Unlike the `create_conversation` call in `onboarding.py` (which is wrapped in a best-effort try/except), `log_adaptation` is called from `apply_micro_adjustment` (line 424) and `apply_macro_replan` (line 578) with no surrounding exception handler — an `IndexError` here will propagate as a 500 response to the caller after sessions have already been mutated, leaving the system in a partially-applied state with no adaptation log entry.
**Fix:**
```python
if not result.data:
    raise RuntimeError("adaptations INSERT returned no rows — check RLS and schema")
return result.data[0]["id"]
```

---

### CR-006 — `getUpcomingSessions` returns wrong shape: `Session[]` vs `{sessions: Session[]}` [CRITICAL]

**File:** `frontend/src/lib/api.ts:121-125`
**Issue:** `getUpcomingSessions` does `return res.json() as Promise<Session[]>` but the backend `GET /sessions/upcoming` returns `{"sessions": [...]}` (a dict with a `sessions` key, not a bare array). Every caller receives the wrapper object typed as `Session[]`. `TodayScreen.tsx` line 90 calls `upcoming?.find(...)` which returns `undefined` (arrays have `find`; plain objects do not). `AgendaScreen.tsx` line 110 checks `sessions.length === 0` which is `undefined` (the `sessions` property of the deserialized wrapper is the actual array), causing the empty-state branch to never fire, and line 135 calls `sessions as unknown as SessionRow[]` then iterates with `for (const s of rows)` — this will iterate over the keys of `{"sessions": [...]}` rather than the session rows.
**Fix:**
```typescript
export async function getUpcomingSessions(): Promise<Session[]> {
  const res = await apiFetch('/sessions/upcoming')
  if (!res.ok) throw new Error(`getUpcomingSessions failed: ${res.status}`)
  const data = await res.json() as { sessions: Session[] }
  return data.sessions ?? []
}
```

---

### CR-007 — OAuth callback endpoint is unauthenticated: state token alone authorizes token storage [CRITICAL]

**File:** `api/routes/calendar.py:208-266`
**Issue:** `GET /calendar/callback` has no `Depends(get_current_user)`. The user whose `google_tokens` are updated is determined solely by a DB lookup on the `state` parameter (line 238: `user_id = rows[0]["user_id"]`). While the state is a 32-byte random value stored server-side (CSRF protection is present), the callback is completely unauthenticated. An attacker who observes the `state` value from an access log or referrer leak can call the callback endpoint with a valid OAuth `code` obtained from their own Google authorization and link Google tokens of their choosing to any victim user's account. The `/auth` endpoint correctly authenticates the user before generating the state; the callback must verify that the same user is completing the flow.
**Fix:** Embed the user_id in the state as an HMAC-signed binding, or require a short-lived session cookie set at `/auth` that the callback verifies:
```python
# At /auth: sign state with user_id
import hmac, hashlib
state_nonce = secrets.token_urlsafe(32)
state_sig = hmac.new(
    os.environ["SUPABASE_JWT_SECRET"].encode(),
    f"{state_nonce}:{user_id}".encode(),
    hashlib.sha256
).hexdigest()
state = f"{state_nonce}.{user_id}.{state_sig}"

# At /callback: verify signature before trusting user_id
parts = state.split(".")
if len(parts) != 3:
    raise HTTPException(status_code=400, ...)
nonce, claimed_user_id, sig = parts
expected = hmac.new(secret.encode(), f"{nonce}:{claimed_user_id}".encode(), hashlib.sha256).hexdigest()
if not hmac.compare_digest(sig, expected):
    raise HTTPException(status_code=400, detail={"error": "invalid_state"})
```

---

### WR-001 — `handleConfirm` stale closure: `queryClient` and `navigate` not in dependency array [WARNING]

**File:** `frontend/src/screens/OnboardingScreen.tsx:344`
**Issue:** `handleConfirm` is wrapped in `useCallback(async () => { ... }, [])` with an empty dependency array, but the inner function `pollForProfile` captures `queryClient` and `navigate` from the enclosing component scope. If React re-renders create new identities for these (possible in test environments or with React concurrent mode), the stale closure references the wrong values. Additionally, ESLint's exhaustive-deps rule will flag this, and future developers may be misled about what state the function captures.
**Fix:**
```typescript
const handleConfirm = useCallback(async () => {
  // ...
}, [queryClient, navigate])
```

---

### WR-002 — SSE error handler fires on normal stream close: shows "Stream error" after successful completion [WARNING]

**File:** `frontend/src/hooks/useSSEStream.ts:68-80`
**Issue:** When the backend closes the SSE connection after emitting the `done` event, `EventSource` fires its `error` event handler automatically (this is how EventSource signals connection closure). The `done` handler closes the EventSource (line 63: `es.close()`), but there is a microtask-scheduling race: the `done` event and the subsequent network close may both be queued before the `close()` call takes effect. If the `error` handler fires after `done`, it calls `setError('Stream error')` even though the stream completed successfully. This will show a red "Connection lost" banner to the user after every coaching turn that ends normally.
**Fix:** Track whether the stream has completed and ignore error events that follow a done:
```typescript
let streamCompleted = false

es.addEventListener('done', () => {
  streamCompleted = true
  setIsDone(true)
  setIsThinking(false)
  es.close()
})

es.addEventListener('error', (e: Event) => {
  if (streamCompleted) return   // ignore post-done connection close
  try {
    const data = JSON.parse((e as MessageEvent).data ?? '{}') as {
      code?: string; message?: string
    }
    setError(data.message ?? 'Stream error')
  } catch {
    setError('Stream error')
  }
  setIsThinking(false)
  es.close()
})
```

---

### WR-003 — Five independent Supabase client singletons: duplicated code, multiple connection pools [WARNING]

**File:** `api/routes/adaptations.py:53`, `api/routes/calendar.py:47`, `api/routes/onboarding.py:89`, `api/routes/rides.py:54`, `api/routes/sessions.py:34`, `api/calendar_sync.py:33`
**Issue:** Identical copy-paste `_supabase_client` singleton + `_get_async_supabase` function exists in six modules. Each creates its own httpx connection pool to Supabase. Any change to initialization logic (e.g., adding connection pool limits, lifespan management, or service role key rotation) requires changes in six places. Test monkeypatching must be applied per-module rather than centrally.
**Fix:** Extract to a single `api/db.py` module and import `get_async_supabase` everywhere.

---

### WR-004 — Macro replan shifts all sessions by exactly 1 day: 30% shift guard is unreachable dead code [WARNING]

**File:** `api/routes/adaptations.py:527`
**Issue:** `apply_macro_replan` shifts every upcoming session forward by exactly 1 day. `check_shift_limit` counts shifts only where `abs(delta_days) > 1` (strictly greater than). A shift of exactly 1 day does not count as "shifted." Therefore, the macro replan as implemented will always produce a `shifted_count` of 0, `shift_pct` of 0.0, and `requires_user_confirmation` of `False` — the 30% guard at D-19 is structurally unreachable with the current replan logic. This makes the ADAPT-03 requirement a no-op in practice.
**Fix:** Either change `check_shift_limit` to count shifts `>= 1` day, or change the macro replan to apply variable-day shifts so that some sessions exceed the 1-day boundary and the guard can meaningfully fire.

---

### WR-005 — `onboarding_start` creates a new conversation on every request: multi-turn context is lost [WARNING]

**File:** `api/routes/onboarding.py:262`
**Issue:** Every `POST /onboarding/start` call creates a new `conversations` row via `create_conversation`. Since the frontend calls this endpoint for every user message turn, each turn sees a fresh empty conversation and `load_conversation` returns `[]`, causing the agent to restart the interview from the beginning on every message. The onboarding cannot progress beyond the first exchange.
**Fix:** The backend should accept an optional `conversation_id` in the request body and only create a new conversation when it is absent. The frontend should create one conversation on mount and pass the same ID on every subsequent turn.

---

### WR-006 — JWT in SSE query param written to server access logs [WARNING]

**File:** `frontend/src/lib/api.ts:26-30`, `api/auth.py:41`
**Issue:** The SSE URL includes the full Supabase JWT as `?token=<jwt>`. Any access log from Uvicorn, Nginx, Railway, or a CDN will record the full token. Access tokens are valid bearer credentials for ~1 hour. This is a known constraint of `EventSource` (which cannot send custom headers), but it is currently unmitigated. A compromise of server logs yields all active user sessions.
**Fix:** Implement a short-lived exchange endpoint: the frontend POSTs (with Authorization header) to `POST /chat/token` and receives a one-time opaque token valid for 30-60 seconds. The SSE URL includes only this ephemeral token, which the backend maps to a user_id. This is the standard mitigation for the EventSource header limitation.

---

### WR-007 — `handleMarkDone` and `handleMarkMissed` swallow errors silently [WARNING]

**File:** `frontend/src/components/session/SessionCard.tsx:72-93`
**Issue:** Both action handlers use `try { ... } finally { setIsLoading(false) }` with no `catch`. API errors are discarded with no user feedback. For `handleMarkMissed`, `setMissedOpen(false)` is in `finally`, so the dialog closes on both success and failure — a network error appears identical to success from the user's perspective.
**Fix:**
```typescript
async function handleMarkDone() {
  setIsDoneLoading(true)
  try {
    await markSessionDone(session.id)
    queryClient.invalidateQueries({ queryKey: ['session', 'today'] })
    queryClient.invalidateQueries({ queryKey: ['sessions', 'upcoming'] })
  } catch {
    toast.error('Could not mark session as done. Please try again.')
  } finally {
    setIsDoneLoading(false)
  }
}

async function handleMarkMissed() {
  setIsMissedLoading(true)
  try {
    await markSessionMissed(session.id)
    queryClient.invalidateQueries({ queryKey: ['session', 'today'] })
    queryClient.invalidateQueries({ queryKey: ['sessions', 'upcoming'] })
    setMissedOpen(false)
  } catch {
    toast.error('Could not mark session as missed. Please try again.')
  } finally {
    setIsMissedLoading(false)
  }
}
```

---

### WR-008 — `ChatScreen` invalidates `active-conversation` after each turn: triggers new conversation creation [WARNING]

**File:** `frontend/src/screens/ChatScreen.tsx:101-103`
**Issue:** When a stream completes, `ChatScreen` calls `queryClient.invalidateQueries({ queryKey: ['active-conversation'] })`. The `queryFn` for `active-conversation` calls `createConversation(...)`, so invalidation triggers a new DB insert. On the next invalidation cycle, `conversation.id` changes and the subsequent message sends to a fresh conversation context with no history. The user appears to get a new coaching conversation after every turn.
**Fix:** Remove the `invalidateQueries` call for `active-conversation` from the stream completion handler. Only invalidate if a "New conversation" action is explicitly requested.

---

### WR-009 — `ride_date` uses upload timestamp instead of FIT file ride date [WARNING]

**File:** `api/routes/rides.py:506`
**Issue:** The ride stub insert sets `ride_date = datetime.now(timezone.utc).date().isoformat()`. This is the upload date, not the date the ride was performed. Users who upload rides retroactively (e.g., uploading last Tuesday's Zwift session on Friday) will have the ride recorded as today. The `detect_signals` function in `adaptations.py` matches rides to planned sessions by date within +/-1 day; rides recorded as "today" will never match a past-due planned session, breaking missed-session detection and underperformance detection for retroactive uploads.
**Fix:** Extract the session start timestamp from the FIT file during parsing and use it as `ride_date`. The FIT `session` message type contains a `start_time` field; alternatively, the minimum `timestamp` across all `record` frames gives the ride start. Fall back to `date.today()` only when no timestamp is present in the file.

---

### IN-001 — `_load_credentials` duplicated in `calendar.py` and `calendar_sync.py` [INFO]

**File:** `api/routes/calendar.py:131`, `api/calendar_sync.py:54`
**Issue:** Two nearly identical `_load_credentials` functions exist. Any change to credential loading (e.g., adding token refresh on expiry) must be applied in both places.
**Fix:** Extract to a shared `api/google_auth.py` module.

---

### IN-002 — `_parse_date` format-string length slice produces wrong index for all three strptime branches [INFO]

**File:** `api/routes/adaptations.py:95-98`
**Issue:** The loop tries `val[:len(fmt)]` where `fmt` is the format string literal (e.g., `"%Y-%m-%d"` has `len == 8`). The formatted output of a date like `"2026-06-20"` is 10 characters, so `val[:8] == "2026-06-"` will never parse. All three `strptime` branches in the loop are dead code; only the `fromisoformat` fallback at line 102 actually works. This is harmless in practice but the dead code is misleading.
**Fix:** Remove the `strptime` loop and use only `fromisoformat`:
```python
def _parse_date(val) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00")).date()
        except ValueError:
            pass
    return None
```

---

### IN-003 — `SettingsScreen` imports `React` at the bottom of the file after its usage [INFO]

**File:** `frontend/src/screens/SettingsScreen.tsx:121`
**Issue:** `import React from 'react'` appears at line 121, after `React.useState` and `React.useEffect` are used in `SettingsScreenInner`. This works due to module hoisting but violates standard TypeScript/React conventions and will be flagged by import-ordering linters.
**Fix:** Move the import to the top of the file, or switch to named imports: `import { useState, useEffect } from 'react'`.

---

### IN-004 — SSE parser resets `currentEvent` inside `data:` branch instead of on blank line only [INFO]

**File:** `frontend/src/screens/OnboardingScreen.tsx:208`, `OnboardingScreen.tsx:320`
**Issue:** In the SSE line loop, `currentEvent = ''` is reset after processing a `data:` line (line 208 and line 320). Per the SSE spec, the event name should persist until a blank-line event dispatch separator. If two events arrive in the same TCP chunk without intervening blank lines (possible under high-throughput streaming), the second event's `data:` line will be processed with `currentEvent = ''` and `parseSSELine('', ...)` returns `null`, silently dropping the event.
**Fix:** Remove `currentEvent = ''` from inside the `data:` handler and only reset it in the blank-line branch (which already exists at line 209/334).

---

_Reviewed: 2026-06-20T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
