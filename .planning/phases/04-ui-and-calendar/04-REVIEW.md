---
phase: "04"
phase_name: "ui-and-calendar"
status: "issues_found"
depth: "standard"
files_reviewed: 68
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
  warning: 5
  info: 2
  total: 11
reviewed_at: "2026-06-20"
---

# Phase 04: Code Review Report

**Reviewed:** 2026-06-20
**Depth:** standard
**Files Reviewed:** 68
**Status:** issues_found

## Summary

Phase 04 delivers the UI shell (Today/Agenda/History/Chat/Settings/Onboarding/DuringSession screens), Google Calendar OAuth integration, PWA setup, and comprehensive test coverage. The auth middleware, SSE streaming fixes, and calendar HMAC-state guard are all correctly implemented. Four issues require immediate attention before this code ships: a broken `getRides()` API wrapper, a missing `oauth_states` database table, a `CalendarSettings` type/runtime mismatch, and a shift-guard boundary condition that prevents all macro replans from applying.

---

## Critical Issues

### CR-01: `getRides()` never unwraps the `{"rides": [...]}` response wrapper

**File:** `frontend/src/lib/api.ts:135-139`

**Issue:** The backend `GET /rides/` endpoint returns `{"rides": result.data}` (rides.py line 573). The `getRides()` function does `return res.json() as Promise<Ride[]>` without unwrapping the `rides` key. At runtime every caller receives `{"rides": [...]}` where a `Ride[]` array is expected. In `HistoryScreen`, `rides.map(...)` is called on the result — iterating over the keys of an object instead of an array — so no ride rows render. All ride history is silently broken. Compare `getUpcomingSessions()` which correctly uses `const data = await res.json() as { sessions: Session[] }; return data.sessions ?? []`.

**Fix:**
```typescript
export async function getRides(): Promise<Ride[]> {
  const res = await apiFetch('/rides/')
  if (!res.ok) throw new Error(`getRides failed: ${res.status}`)
  const data = await res.json() as { rides: Ride[] }
  return data.rides ?? []
}
```

---

### CR-02: `oauth_states` table is never created in any migration

**File:** `api/routes/calendar.py:196,244,299,337` / `supabase/migrations/0003_phase4_schema.sql`

**Issue:** Both the `/calendar/auth-redirect-url` and `/calendar/auth` endpoints call `supabase.table("oauth_states").upsert(...)` to store CSRF nonces, and the callback verifies nonces from that same table. The table is referenced across five call sites in calendar.py. However all three migrations (0001, 0002, 0003) contain no `CREATE TABLE oauth_states` statement. At runtime every OAuth initiation and callback will fail with a Postgres "relation does not exist" error, making Google Calendar connection completely non-functional.

**Fix:** Add to `supabase/migrations/0003_phase4_schema.sql`:
```sql
-- oauth_states: short-lived CSRF nonces for Google OAuth flow (T-04-21)
CREATE TABLE IF NOT EXISTS public.oauth_states (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    state      text NOT NULL UNIQUE,
    created_at timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.oauth_states ENABLE ROW LEVEL SECURITY;

-- Service role writes; no user read policy needed (nonces are server-internal)
```

---

### CR-03: `CalendarSettings` TypeScript interface declares fields the backend never returns

**File:** `frontend/src/lib/api.ts:104-108`

**Issue:** The interface declares:
```typescript
export interface CalendarSettings {
  connected: boolean
  calendar_id: string | null   // never in backend response
  sync_enabled: boolean        // never in backend response
}
```
The backend `/calendar/settings` returns only `{"connected": bool}`. Fields `calendar_id` and `sync_enabled` will always be `undefined` at runtime while TypeScript types them as `string | null` and `boolean` respectively, suppressing type errors in any future consumer. The E2E mock at `phase4.spec.ts:243` perpetuates this by matching the wrong shape.

**Fix:**
```typescript
export interface CalendarSettings {
  connected: boolean
}
```
If `calendar_id` or `sync_enabled` are planned, add them as `optional?: type` to signal they may not be present.

---

### CR-04: `check_shift_limit` uses `>= 1` boundary, causing every macro replan to require confirmation

**File:** `api/routes/adaptations.py:264`

**Issue:** The docstring at line 21 states sessions that "shift by **more than 1 day**" are counted. The implementation uses:
```python
if delta_days >= 1:
    shifted_count += 1
```
`apply_macro_replan` shifts every upcoming session by exactly 1 day (line 498: `new_date = (sched + timedelta(days=1))`). With `>= 1`, all sessions count as shifted, producing `shift_pct = 1.0`, which always exceeds the 30% threshold. Every macro replan returns `"needs_confirmation"` and never applies, permanently disabling the adaptation loop for 2+ signal events.

The unit test at `test_adaptations.py:143` also confirms the intended behavior: a +1 day move from `"2026-06-20"` to `"2026-06-21"` should produce `shifted_count == 0`. That test fails with the current `>= 1` implementation.

**Fix:**
```python
if delta_days > 1:   # "more than 1 day" as specified
    shifted_count += 1
```

---

## Warnings

### WR-01: `SettingsScreen` uses `React.useState` and `React.useEffect` before `React` is imported

**File:** `frontend/src/screens/SettingsScreen.tsx:34,36,121`

**Issue:** `SettingsScreenInner` calls `React.useState` (line 34) and `React.useEffect` (line 36) but the `import React from 'react'` statement appears at line 121 — the bottom of the file. ES module imports are hoisted by the spec so this works in current Vite/bundler tooling, but the pattern is unconventional and fragile. Linters and bundlers expecting imports at the top will flag or misprocess this.

**Fix:** Move the import to line 1:
```typescript
import React from 'react'
// ... rest of imports
```

---

### WR-02: `make_test_token` produces JWTs without an `exp` claim

**File:** `tests/api/conftest.py:47-51`

**Issue:** Test tokens omit `exp`. PyJWT's `decode()` does not reject tokens with no expiry by default, so all auth tests pass. However, no test exercises the expiry-validation path, and a future hardening of `get_current_user` that adds `options={"require": ["exp"]}` would silently break all tests. The test tokens also do not match real Supabase JWT structure (which always includes `exp`), reducing the fidelity of the auth test suite.

**Fix:**
```python
import time
jwt.encode(
    {
        "sub": user_id,
        "email": email,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
    },
    secret,
    algorithm="HS256",
)
```

---

### WR-03: E2E `mockBackendApis` — `/adaptations/sessions/.../missed` route shadowed by general `/adaptations/` (LIFO)

**File:** `frontend/tests/e2e/phase4.spec.ts:234-237`

**Issue:** The comment at line 220 explains Playwright's LIFO rule correctly, but the adaptations routes are ordered incorrectly. The specific missed handler is registered at line 234, then the general `/adaptations\/` handler at line 237. Since LIFO means the last-registered wins, the general handler intercepts all adaptations URLs including missed ones. The specific missed handler never fires. A future "Mark missed" E2E test would assert against an empty object response instead of the expected adaptation result.

**Fix:** Reverse the registration order:
```typescript
// General first so specific overrides it via LIFO
await page.route(/\/adaptations\//, (route) => route.fulfill(respond([])))
await page.route(/\/adaptations\/sessions\/[^/]+\/missed/, (route) =>
  route.fulfill(respond({})),
)
```

---

### WR-04: T18 E2E asserts a hardcoded absolute URL that breaks on any port other than 5174

**File:** `frontend/tests/e2e/phase4.spec.ts:640`

**Issue:**
```typescript
await expect(page).toHaveURL('http://localhost:5174/')
```
The default Vite dev port is 5173; 5174 is only used when 5173 is occupied. This test will fail consistently on any machine where 5173 is free. Playwright's `baseURL` config should be used for relative assertions.

**Fix:**
```typescript
await expect(page).toHaveURL('/')
```

---

### WR-05: `test_calendar.py` resets a `_supabase_client` attribute that does not exist in `calendar.py`

**File:** `tests/api/test_calendar.py:55,123`

**Issue:**
```python
cal_mod._supabase_client = None
```
`api/routes/calendar.py` has no `_supabase_client` module-level attribute. Setting it to `None` silently adds an attribute that is never read. This is dead code that creates a false impression of singleton reset. Tests pass because `_get_async_supabase` is separately monkeypatched, not because of this reset.

**Fix:** Remove both `cal_mod._supabase_client = None` lines (55 and 123).

---

## Info

### IN-01: `onboarding_start` uses an instantiated Pydantic model as a default parameter

**File:** `api/routes/onboarding.py:213`

**Issue:**
```python
async def onboarding_start(
    body: OnboardingStartBody = OnboardingStartBody(),
    ...
```
Using a constructed model instance as a default value is an unusual pattern in FastAPI — it works because Pydantic models are not mutated, but it diverges from idiomatic FastAPI. The idiomatic approach is to make the body optional and handle the `None` case explicitly, which makes the intent clearer.

**Fix:**
```python
async def onboarding_start(
    body: Optional[OnboardingStartBody] = None,
    current_user: dict = Depends(get_current_user),
):
    body = body or OnboardingStartBody()
```

---

### IN-02: `users.google_tokens` column is declared `jsonb` but stores Fernet ciphertext (text)

**File:** `supabase/migrations/0001_initial_schema.sql:13`

**Issue:** The column is `jsonb` but the code stores base64-encoded Fernet ciphertext (an opaque text blob) via `ciphertext_str = ciphertext.decode()`. Postgres's JSON parser should reject arbitrary base64 strings inserted into a `jsonb` column unless the Supabase REST client wraps the value in a JSON string literal. The storage works coincidentally if the client quotes the string, but the column type is semantically wrong and any direct SQL inspection or future type-aware access will behave unexpectedly.

**Fix:** Change the column to `text` in a follow-up migration:
```sql
ALTER TABLE public.users
  ALTER COLUMN google_tokens TYPE text USING google_tokens::text;
```

---

_Reviewed: 2026-06-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
