---
phase: 04
phase_name: ui-and-calendar
status: issues_found
files_reviewed: 73
files_reviewed_list:
  - api/auth.py
  - api/calendar_sync.py
  - api/main.py
  - api/routes/_sse.py
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
  - frontend/src/components/session/ZwoExportModal.tsx
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
  - frontend/src/screens/AuthCallbackScreen.tsx
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
  - frontend/src/tests/session.test.tsx
  - frontend/src/tests/setup.ts
  - frontend/src/tests/today.test.tsx
  - frontend/src/tests/useSessionTimer.test.ts
  - frontend/src/tests/useWakeLock.test.ts
  - frontend/src/tests/zwo-modal.test.tsx
  - frontend/src/vite-env.d.ts
  - frontend/tests/e2e/full-uat.spec.ts
  - frontend/tests/e2e/phase4.spec.ts
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
  critical: 4
  warning: 8
  info: 4
  total: 16
reviewed_at: 2026-06-21T00:00:00Z
depth: standard
---

# Phase 04 Code Review

**Reviewed:** 2026-06-21
**Depth:** standard
**Files Reviewed:** 73
**Status:** issues_found

## Summary

Phase 4 delivers auth middleware, Google Calendar OAuth, session UI, ZWO export, and adaptive re-planning. The architecture is sound with good defense-in-depth patterns. Four blockers are present: an `UnboundLocalError` crash in the missed-session endpoint, a JWT unnecessarily exposed in POST request URLs, Google Calendar all-day events with identical start and end dates (violates the API spec and causes some clients to discard them), and a session state guard omission that allows a missed session to be overwritten back to completed. Eight warnings and four info items round out the findings.

## Structural Findings (fallow)

No structural pre-pass was provided.

## Narrative Findings (AI reviewer)

## Critical Issues

### CR-01: `UnboundLocalError` crash in `mark_session_missed` when signal detection raises

**File:** `api/routes/adaptations.py:712`

**Issue:** `scope` is assigned only inside the `try` block at line 689. `signals` and `result` are correctly pre-initialised before the `try` (lines 685-686), but `scope` is not. When `detect_signals` raises any exception, `except Exception: pass` at line 705 swallows it and execution reaches the `return` dict at line 708, which references `scope` at line 712 — producing `UnboundLocalError: local variable 'scope' referenced before assignment`. Every detection-failure path becomes a 500 instead of the intended graceful fallback.

**Fix:**
```python
# Pre-initialise all three variables before the try block:
signals: list = []
result = None
scope = None           # <-- add this line

try:
    signals = await detect_signals(user_id)
    scope = decide_scope(signals)
    ...
except Exception:
    logger.warning("Signal detection failed for session %s", session_id, exc_info=True)
```

---

### CR-02: JWT exposed in URL for POST requests in `OnboardingScreen`

**File:** `frontend/src/screens/OnboardingScreen.tsx:135`

**Issue:** Both `runStream` (line 135) and `handleConfirm` (line 297) call `sseUrl('/onboarding/start')` to construct the fetch URL. `sseUrl()` appends `?token=<full_jwt>` because it was designed for `EventSource` (GET only; cannot send headers). However, these callers use `fetch()` with `method: 'POST'` — a regular HTTP POST that can and should carry an `Authorization` header instead. The JWT lands in Uvicorn/Nginx/CDN access logs and browser history for every onboarding turn, not just SSE streams.

**Fix:** For POST fetches, use `apiFetch` or construct the request with `Authorization: Bearer` header directly, without `sseUrl()`:
```typescript
const { data } = await supabase.auth.getSession()
const token = data.session?.access_token ?? ''
const res = await fetch(`${BASE}/onboarding/start`, {
  method: 'POST',
  signal: controller.signal,
  headers: {
    'Authorization': `Bearer ${token}`,
    'Accept': 'text/event-stream',
    'Content-Type': 'application/json',
  },
  body: JSON.stringify(bodyPayload),
})
```

---

### CR-03: Google Calendar all-day events have identical start and end date

**File:** `api/calendar_sync.py:114-118`

**Issue:** The Google Calendar API requires that `end.date` for all-day events be the **exclusive** day after `start.date`. When `start.date == end.date` the event is zero-duration; several Google Calendar clients silently discard or fail to display such events, meaning synced sessions may not appear at all.

```python
return {
    "start": {"date": str(scheduled_date)},
    "end": {"date": str(scheduled_date)},   # BUG: must be start + 1 day
}
```

**Fix:**
```python
from datetime import timedelta
import datetime as _dt

sched_str = str(scheduled_date)
try:
    end_date = (_dt.date.fromisoformat(sched_str) + timedelta(days=1)).isoformat()
except ValueError:
    end_date = sched_str  # fall back on unparseable value

return {
    "start": {"date": sched_str},
    "end": {"date": end_date},
}
```

---

### CR-04: `update_session` (PATCH) can clobber a `missed` session back to `completed`

**File:** `api/routes/sessions.py:245-252`

**Issue:** The PATCH handler applies `update({"status": "completed"})` filtered only by `id` and `user_id` — no status precondition. A session already recorded as `missed` (via the adaptations endpoint) can be silently overwritten to `completed` by a double-click, network retry, or offline replay. The IDOR protection is intact but the state-machine invariant is not enforced.

**Fix:** Add a status guard so only planned sessions can transition:
```python
result = await (
    supabase.table("sessions")
    .update({"status": "completed"})
    .eq("id", session_id)
    .eq("user_id", user_id)
    .eq("status", "planned")   # only planned -> completed transitions are valid
    .select(_SESSION_COLUMNS)
    .execute()
)
```
The existing 404 response then naturally rejects re-completion of already-closed sessions.

---

## Warning Findings

### WR-01: OAuth callback HMAC key falls back to empty string when `SUPABASE_JWT_SECRET` is unset

**File:** `api/routes/calendar.py:284`

**Issue:** `secret = os.environ.get("SUPABASE_JWT_SECRET", "")` returns `""` when the var is absent. An HMAC computed with an empty key is trivially reproducible by any attacker who knows the `{nonce}.{user_id}.{hmac_hex}` format. The nonce database check (line 298) provides a secondary guard, but only if the attacker cannot observe a valid nonce from access logs.

**Fix:**
```python
secret = os.environ.get("SUPABASE_JWT_SECRET")
if not secret:
    raise HTTPException(
        status_code=500,
        detail={"error": "server_misconfigured", "detail": "SUPABASE_JWT_SECRET is required"},
    )
```

---

### WR-02: Bare `except Exception: pass` in `mark_session_missed` hides all errors silently

**File:** `api/routes/adaptations.py:705-706`

**Issue:** The blank except with no logging means the CR-01 `UnboundLocalError` — and any future bugs in `detect_signals`, `apply_micro_adjustment`, or `apply_macro_replan` — produce zero log output. The non-fatal intent is correct; the complete suppression of observability is not.

**Fix:**
```python
except Exception:
    logger.warning(
        "Signal detection/adaptation failed for session %s (non-fatal)", session_id, exc_info=True
    )
```

---

### WR-03: `useAuth.ts` `onAuthStateChange` null guard is wider than documented

**File:** `frontend/src/hooks/useAuth.ts:47`

**Issue:** `if (newSession === null && event !== 'SIGNED_OUT') return` suppresses all null-session events except `SIGNED_OUT`. The comment documents "INITIAL_SESSION races", but `TOKEN_REFRESHED` events that fire with a null session (revoked refresh token) are also silently dropped. A user with a revoked token on any non-callback page remains stuck in an authenticated-looking state until their next full page load.

**Fix:** Narrow the guard to the documented intent:
```ts
if (newSession === null && event === 'INITIAL_SESSION') return
```

---

### WR-04: `useAuth.ts` callback guard uses `includes` instead of exact match

**File:** `frontend/src/hooks/useAuth.ts:19`

**Issue:** `window.location.pathname.includes('/auth/callback')` matches any path containing that substring (e.g. `/admin/auth/callback-audit`). Exact equality is the correct check.

**Fix:**
```ts
const onAuthCallback = window.location.pathname === '/auth/callback'
```

---

### WR-05: Dual `duration` columns create split-brain after micro-adjustment

**File:** `supabase/migrations/0003_phase4_schema.sql:22-23` and `api/routes/adaptations.py:366-369`

**Issue:** The migration adds `duration_minutes int` alongside the existing `duration_mins` column. Phase 3 sessions were created with only `duration_mins` populated. The micro-adjustment code updates only `duration_minutes` (line 368). After adjustment, `duration_minutes` holds the new value and `duration_mins` still holds the original, creating a permanent inconsistency for any code querying only one of the two columns.

**Fix:** Update both columns in `apply_micro_adjustment`:
```python
await supabase.table("sessions").update({
    "tss_target": new_tss,
    "duration_minutes": new_dur,
    "duration_mins": new_dur,  # keep legacy column in sync
}).eq("id", session["id"]).execute()
```

---

### WR-06: `apiFetch` silently constructs malformed URLs when `VITE_API_URL` is undefined

**File:** `frontend/src/lib/api.ts:3`

**Issue:** When `VITE_API_URL` is not set, `BASE` is `undefined`. All fetch calls produce `undefined/profiles/me` which throws a `TypeError: Failed to fetch` with a message that does not indicate the missing env var. Development setup failures become opaque.

**Fix:**
```typescript
const BASE = import.meta.env.VITE_API_URL
if (!BASE) {
  throw new Error('VITE_API_URL is not set. Add it to .env.local.')
}
```

---

### WR-07: E2E test `full-uat.spec.ts` mark-missed assertion tests the wrong endpoint

**File:** `frontend/tests/e2e/full-uat.spec.ts:414-441`

**Issue:** The test "Yes mark missed closes dialog and fires PATCH" intercepts `PATCH /sessions/session-today-id` and asserts `patchCalled === true`. However, `handleMarkMissed` in `SessionCard.tsx` calls `markSessionMissed` which hits `POST /adaptations/sessions/{id}/missed`, not `PATCH /sessions/{id}`. The PATCH route is only called by `handleMarkDone`. `patchCalled` will always remain `false` in a correct environment.

**Fix:** Intercept the adaptations endpoint instead:
```ts
let missedCalled = false
await page.route(/\/adaptations\/sessions\/session-today-id\/missed/, (route) => {
  missedCalled = true
  route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
})
// ...
expect(missedCalled).toBe(true)
```

---

### WR-08: `createConversation` in `api.ts` silently returns `id: ''` on missing id field

**File:** `frontend/src/lib/api.ts:195`

**Issue:** `data.conversation_id ?? data.id ?? ''` returns an empty string when neither field is present (e.g. a backend regression). Callers receive a `Conversation` with `id: ''` and make requests like `GET /conversations//messages`, producing opaque 404s with no indication of the root cause.

**Fix:**
```ts
const id = data.conversation_id ?? data.id
if (!id) throw new Error('createConversation: backend returned no conversation id')
return { ...data, id } as unknown as Conversation
```

---

## Info Findings

### IN-01: `Content-Disposition` filename in ZWO export uses unsanitised DB value

**File:** `api/routes/sessions.py:345`

**Issue:** `session_type` comes from the database `sessions.type` column and is embedded directly into the `Content-Disposition` header value without sanitisation. A value containing `"` or `\r\n` would break or inject into the header. Low risk (data comes from trusted DB), but defence-in-depth is missing.

**Fix:**
```python
import re
safe_type = re.sub(r'[^A-Za-z0-9_-]', '_', session_type)
filename = f"{session.get('scheduled_date', '')}-{safe_type}.zwo"
```

---

### IN-02: `ChatScreen` calls `createConversation` on every cold cache mount

**File:** `frontend/src/screens/ChatScreen.tsx:63-70`

**Issue:** Using `createConversation` as the `queryFn` for the `active-conversation` query inserts a new `conversations` row every time the cache is cold (hard reload, cache eviction after 5 minutes GC time). Users accumulate orphaned conversation rows and lose conversation context across hard reloads.

**Fix:** Use `sessionStorage` to persist the active conversation ID across soft navigations but not across hard reloads:
```typescript
queryFn: async () => {
  const cached = sessionStorage.getItem('active-conversation-id')
  if (cached) return { id: cached } as Conversation
  const conv = await createConversation('Coaching session')
  sessionStorage.setItem('active-conversation-id', conv.id)
  return conv
},
```

---

### IN-03: `oauth_states` table has no TTL cleanup for stale nonces

**File:** `supabase/migrations/0003_phase4_schema.sql:44-53`

**Issue:** OAuth state nonces are deleted after a successful callback (line 337 of `calendar.py`) but have no expiry mechanism for abandoned flows (user closes the browser mid-OAuth, network failure before callback). Stale nonces accumulate indefinitely, creating a small but unbounded table growth and a potential confusion vector if a nonce ID is ever reused.

**Fix:** Add a `pg_cron` cleanup job or a `created_at < now() - interval '10 minutes'` filter in the callback handler, or set a Postgres trigger to auto-delete rows older than 15 minutes.

---

### IN-04: `AlertDialogCancel` in `SessionCard.tsx` has a redundant `onClick` handler

**File:** `frontend/src/components/session/SessionCard.tsx:246`

**Issue:** `AlertDialogCancel` (shadcn/ui) already closes the dialog via its Radix `DialogClose` root. The explicit `onClick={() => setMissedOpen(false)}` double-fires the close, which is harmless today but will trigger any future close side effects twice.

**Fix:**
```tsx
<AlertDialogCancel>Keep it</AlertDialogCancel>
```

---

_Reviewed: 2026-06-21_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
