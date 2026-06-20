---
phase: 04-ui-and-calendar
reviewed: 2026-06-20T00:00:00Z
depth: quick
files_reviewed: 57
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
  - frontend/src/App.tsx
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
  - frontend/src/hooks/useAuth.ts
  - frontend/src/hooks/useCalendarStatus.ts
  - frontend/src/hooks/useSSEStream.ts
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
  - frontend/vite.config.ts
  - frontend/vitest.config.ts
  - tests/api/conftest.py
  - tests/api/test_adaptations.py
  - tests/api/test_auth.py
  - tests/api/test_calendar.py
  - tests/api/test_onboarding.py
  - tests/api/test_rides.py
  - tests/api/test_sessions.py
findings:
  critical: 4
  warning: 5
  info: 2
  total: 11
status: issues_found
---

# Phase 04: Code Review Report

**Reviewed:** 2026-06-20
**Depth:** quick (with targeted file reads on flagged areas)
**Files Reviewed:** 57
**Status:** issues_found

## Summary

Phase 04 introduces JWT auth, Google Calendar OAuth2, the SSE streaming layer, and the full React frontend. The highest-risk surface is the OAuth2 callback flow and the JWT-in-URL pattern used by both SSE clients and the Calendar connect flow. Four critical findings were confirmed by reading the code directly; five warnings cover logic gaps and missing hardening. The SSE ?token= fallback is an accepted architectural trade-off (EventSource cannot send headers), but the Calendar connect flow compounds the exposure unnecessarily.

---

## Critical Issues

### CR-01: Supabase JWT sent as URL query parameter to the backend OAuth /auth endpoint

**File:** `frontend/src/components/settings/CalendarStatus.tsx:30`
**Issue:** `window.location.href = \`${API_URL}/calendar/auth?token=${encodeURIComponent(token)}\`` navigates the browser to the backend OAuth redirect with the user's Supabase access token in the URL. This is distinct from the SSE case: here the browser navigates to a backend page, meaning the token appears in:
- Browser history (and any browser sync)
- Nginx/server access logs for the backend
- The HTTP `Referer` header sent to Google's authorization endpoint
- Any browser extensions or corporate proxies that log URLs

The SSE `?token=` design is a documented architectural trade-off (EventSource cannot send Authorization headers). This calendar case has no such constraint — the frontend could instead call a short-lived `POST /calendar/auth/session` endpoint that returns a one-time redirect URL (backend holds the JWT, returns the Google URL), or the backend could accept the token only in the body of a POST. Sending a long-lived access token in a navigation URL is a straightforward credential leak.

**Fix:** Change the OAuth initiation to a POST request. The backend generates the Google auth URL and returns it in the response body; the frontend then redirects to that URL.

```typescript
// CalendarStatus.tsx
async function handleConnect() {
  const res = await apiFetch('/calendar/auth', { method: 'POST' })
  if (!res.ok) { toast.error('Could not initiate connection.'); return }
  const { auth_url } = await res.json()
  window.location.href = auth_url
}
```

```python
# api/routes/calendar.py -- change @router.get("/auth") to @router.post("/auth")
@router.post("/auth")
async def calendar_auth(current_user: dict = Depends(get_current_user)) -> dict:
    ...
    return {"auth_url": auth_url}
```

---

### CR-02: OAuth callback endpoint is unauthenticated -- any caller can exchange a valid state token

**File:** `api/routes/calendar.py:208-266`
**Issue:** `GET /calendar/callback` takes only `code` and `state` query parameters; it has no `Depends(get_current_user)`. The CSRF state lookup does authenticate indirectly (state -> user_id), but the endpoint is exploitable if an attacker intercepts the code from a victim's OAuth flow: they can submit a valid `code` + valid `state` to the callback and have the tokens stored for the victim's account, since there is no second factor binding the request to a specific browser session or principal. Additionally, the `state` parameter is looked up by value in the database with no constant-time comparison, making it theoretically vulnerable to timing attacks (though Supabase's DB latency dwarfs timing differences in practice, this is still a correctness gap).

More concretely: if the victim's OAuth redirect is intercepted (e.g., via open redirect or network position), the attacker holds both `code` and `state` and can complete the exchange on behalf of the victim with no server-side protection beyond the state match.

**Fix:** Bind the OAuth state to a user-specific session cookie or PKCE verifier so that only the originating browser session can complete the exchange. At minimum, set a short TTL on `oauth_states` rows (e.g., 10 minutes) and delete them immediately after first use (which the code does do on line 264, but the TTL enforcement is missing).

```python
# In oauth_states upsert, add an expiry column and enforce it in the callback:
await supabase.table("oauth_states").upsert(
    {"user_id": user_id, "state": state, "expires_at": (datetime.utcnow() + timedelta(minutes=10)).isoformat()}
).execute()

# In callback, check expiry:
if rows[0].get("expires_at") and rows[0]["expires_at"] < datetime.utcnow(tz=timezone.utc).isoformat():
    raise HTTPException(status_code=400, detail={"error": "state_expired", ...})
```

---

### CR-03: `markSessionDone` calls a PATCH /sessions/{id} endpoint that does not exist in the backend

**File:** `frontend/src/lib/api.ts:181-187` and `api/routes/sessions.py`
**Issue:** `markSessionDone` sends `PATCH /sessions/{sessionId}` with `{ status: 'completed' }`. No such endpoint is defined in `api/routes/sessions.py` or `api/main.py`. The sessions router only exposes GET endpoints (`/sessions/today`, `/sessions/upcoming`). This call will return 404 or 405 at runtime. The "Mark done" button in `SessionCard.tsx` is silently broken: `handleMarkDone` catches no errors (the `finally` block only clears loading state), so the user sees no feedback and the session status never changes.

**Fix:** Add the missing PATCH endpoint to the sessions router, or route it through the adaptations router for consistency:

```python
# api/routes/sessions.py
@router.patch("/sessions/{session_id}")
async def update_session(
    session_id: str = Path(...),
    body: dict = Body(...),
    current_user: dict = Depends(get_current_user),
) -> dict:
    user_id = current_user["user_id"]
    validate_uuid(session_id, "session_id")
    allowed_fields = {"status"}
    update_data = {k: v for k, v in body.items() if k in allowed_fields}
    if not update_data:
        raise HTTPException(status_code=422, detail={"error": "no_valid_fields"})
    supabase = await _get_async_supabase()
    # Verify ownership before update
    check = await supabase.table("sessions").select("id").eq("id", session_id).eq("user_id", user_id).execute()
    if not check.data:
        raise HTTPException(status_code=404, detail={"error": "session_not_found"})
    result = await supabase.table("sessions").update(update_data).eq("id", session_id).execute()
    return result.data[0]
```

---

### CR-04: `process_ride_background` queries `training_sessions` table but the rest of the codebase uses `sessions`

**File:** `api/routes/rides.py:309`
**Issue:** The session compliance check in `process_ride_background` queries `.table("training_sessions")`, but every other query in the codebase (adaptations.py, sessions.py) uses `.table("sessions")`. If the actual table name is `sessions` (the dominant usage), the compliance check silently returns no rows every time, meaning `compliance_result` is always `None`, `compliance_pct` is never written to the ride row, and session compliance is never validated. This is a silent data correctness failure.

**Fix:**
```python
# api/routes/rides.py:309 -- change table name to match the rest of the codebase
session_result = await (
    supabase.table("sessions")  # was: "training_sessions"
    .select("tss_target, session_type")
    .eq("user_id", user_id)
    .eq("scheduled_date", date.today().isoformat())
    .execute()
)
```

Also note: the query selects `tss` but the sessions table column is `tss_target` (used everywhere else). Fix the select to `tss_target`:
```python
.select("tss_target, session_type")
# then:
planned={"tss": planned_session.get("tss_target", 0)},
```

---

## Warnings

### WR-01: Error swallowed silently in `handleMarkDone` -- user gets no failure feedback

**File:** `frontend/src/components/session/SessionCard.tsx:72-79`
**Issue:** `handleMarkDone` has no `catch` block. If `markSessionDone` throws (404 from the missing endpoint in CR-03, or any network error), the error is silently swallowed. The loading spinner clears but the user has no indication the action failed. The `handleMarkMissed` function on line 83 has the same pattern.

**Fix:**
```typescript
async function handleMarkDone() {
  setIsDoneLoading(true)
  try {
    await markSessionDone(session.id)
    queryClient.invalidateQueries({ queryKey: ['session', 'today'] })
    queryClient.invalidateQueries({ queryKey: ['sessions', 'upcoming'] })
    toast.success('Session marked complete.')
  } catch {
    toast.error('Could not mark session done. Try again.')
  } finally {
    setIsDoneLoading(false)
  }
}
```

---

### WR-02: `getUpcomingSessions` returns an object `{ sessions: [] }` but callers expect `Session[]`

**File:** `frontend/src/lib/api.ts:121-125` and `api/routes/sessions.py:141`
**Issue:** `GET /sessions/upcoming` returns `{"sessions": [...]}` (a dict with a key). The frontend helper `getUpcomingSessions` casts the response directly as `Promise<Session[]>` without unwrapping the `sessions` key. This means `useQuery` data in `TodayScreen.tsx` and `AgendaScreen.tsx` will be the raw object `{ sessions: [...] }`, not an array. Downstream, `upcoming?.find(...)` and `sessions.length === 0` behave as if the array is empty or undefined depending on the JS coercion. The `AgendaScreen` casts with `sessions as unknown as SessionRow[]` which would silently give a non-array value.

**Fix:**
```typescript
// api.ts
export async function getUpcomingSessions(): Promise<Session[]> {
  const res = await apiFetch('/sessions/upcoming')
  if (!res.ok) throw new Error(`getUpcomingSessions failed: ${res.status}`)
  const data = await res.json() as { sessions: Session[] }
  return data.sessions ?? []
}
```

---

### WR-03: `apply_macro_replan` shifts every session by +1 day unconditionally, then checks the 30% guard

**File:** `api/routes/adaptations.py:527`
**Issue:** The macro replan shifts every session out by 1 day (`new_date = (sched + timedelta(days=1)).isoformat()`), which means 100% of sessions shift by exactly 1 day. The `check_shift_limit` function counts sessions that shift by **more than** 1 day (`delta_days > 1`), so the guard never fires (0% of sessions shift by >1 day when all shift by exactly 1). The 30% guard is effectively dead code for the current replan logic. If the intent is to detect any shift at all, the threshold in `check_shift_limit` should be `>= 1` not `> 1`, or the replan should vary shift amounts. As-is, the guard required by ADAPT-03/D-19 is bypassed.

**Fix:** Either change the guard threshold to `delta_days >= 1` to match the actual shift amounts, or implement variable shift logic that can produce multi-day shifts so the guard has meaningful input to test.

---

### WR-04: `getLatestPmc` returns `null` silently when the `date` field is missing, masking valid data

**File:** `frontend/src/lib/api.ts:139-143`
**Issue:** `getLatestPmc` checks `if (!data || !data.date) return null`. The backend `latest_pmc` returns an empty dict `{}` for cold-start, but a valid PMC row should always have a `date`. However, if the schema or ORM returns a different field name (e.g., `created_at` but no `date`), the function silently returns null and the TsbChip/SessionCard never show PMC data even though it exists. The empty-dict check on line 139 is sufficient; the `!data.date` guard adds fragility.

**Fix:**
```typescript
// Check only for empty dict (cold-start); don't gate on field presence
if (!data || Object.keys(data).length === 0) return null
return data as unknown as PmcEntry
```

---

### WR-05: `onboarding_start` creates a conversation row but ignores the returned ID -- SSE never loads prior history

**File:** `api/routes/onboarding.py:258-263`
**Issue:** `await create_conversation(user_id, context_type="onboarding")` creates a DB row and returns a UUID, but the return value is discarded. The `sse_generator` is then called with a static `messages` list that does not reference any conversation. This means the onboarding conversation is never loaded from DB on subsequent SSE calls (e.g., when the user sends their answer and `runStream(text)` re-POSTs to `/onboarding/start`). Each POST re-creates a fresh context with only the static opening message, losing all prior interview turns. The onboarding agent has no memory of the interview across multiple SSE calls.

This is distinct from the "new messages are NOT persisted" note in the docstring: the problem is that prior messages are not *loaded* either.

**Fix:** Either persist the conversation_id and use `load_conversation` before each `sse_generator` call (which requires passing the conversation_id from the frontend), or document explicitly that the entire onboarding interview is conducted in a single SSE stream (which contradicts the current frontend that re-POSTs per user message).

---

## Info

### IN-01: `App.tsx` is the Vite scaffold default -- never used, not wired to the router

**File:** `frontend/src/App.tsx:1-122`
**Issue:** This file is the stock Vite scaffold with a counter, hero image, and React/Vite logos. It is never imported by `main.tsx` or the router (the router is mounted directly via `RouterProvider`). Dead file.

**Fix:** Delete `frontend/src/App.tsx` and `frontend/src/App.css`. Also delete `frontend/src/assets/react.svg`, `frontend/src/assets/vite.svg`, and `frontend/src/assets/hero.png` if they are not used elsewhere.

---

### IN-02: `router.tsx` exports placeholder screen stubs that shadow real screen implementations

**File:** `frontend/src/router.tsx:114-128`
**Issue:** `router.tsx` exports `OnboardingScreen`, `HistoryScreen`, `ChatScreen`, and `SettingsScreen` as stub divs (`return <div>Onboarding</div>` etc.) even though real implementations exist in `src/screens/`. The router uses these stubs for `/onboarding`, `/history`, `/chat`, and `/settings`, not the real screens. The real screens in `frontend/src/screens/` are not imported by the router at all for these routes.

**Fix:** Remove the stubs and import the real screen implementations:
```typescript
import { OnboardingScreen } from './screens/OnboardingScreen'
import { HistoryScreen } from './screens/HistoryScreen'
import { ChatScreen } from './screens/ChatScreen'
import { SettingsScreen } from './screens/SettingsScreen'
```

---

_Reviewed: 2026-06-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: quick (with targeted reads on flagged security surfaces)_
