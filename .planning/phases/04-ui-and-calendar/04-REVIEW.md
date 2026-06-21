---
phase: 04
status: issues_found
critical: 1
warning: 4
info: 2
reviewed_at: 2026-06-21
---

# Phase 04 Gap-Closure: Code Review

**Depth:** standard
**Files reviewed:** 5

---

## [CRITICAL] sessions.py: update_session does not guard against re-completing already-closed sessions

**File:** `api/routes/sessions.py:245-252`
**Issue:** The PATCH handler applies `update({"status": "completed"})` filtered only by `id` and `user_id`. There is no `.eq("status", "planned")` guard. Any session already in `"completed"` or `"missed"` state will be silently overwritten back to `"completed"` if the client re-submits. For the missed-session flow this is a data-integrity defect: a session correctly recorded as `"missed"` can be clobbered to `"completed"` by accident (double-click, retry, offline replay). The IDOR protection is intact (dual filter on id + user_id), but the state-machine invariant is not enforced.

**Fix:** Add a status precondition to the update filter:
```python
result = await (
    supabase.table("sessions")
    .update({"status": "completed"})
    .eq("id", session_id)
    .eq("user_id", user_id)
    .eq("status", "planned")   # only planned sessions can transition to completed
    .select(_SESSION_COLUMNS)
    .execute()
)
```
The existing 404 path will then correctly reject re-completion attempts.

---

## [WARNING] useAuth.ts: pathname guard uses `includes` instead of exact match

**File:** `frontend/src/hooks/useAuth.ts:19`
**Issue:** `window.location.pathname.includes('/auth/callback')` matches any path containing that substring (e.g. `/user/auth/callback-logs`). More critically, the guard only fires at mount time. If `useAuth` is mounted from a persistent layout component that renders on a different route while the PKCE exchange is still in progress on a navigated-to `/auth/callback`, the guard does not fire and the null seed will bounce the user to `/login`. The guard should use exact equality.

**Fix:**
```ts
const onAuthCallback = window.location.pathname === '/auth/callback'
```

---

## [WARNING] useAuth.ts: onAuthStateChange null guard documentation is misleading

**File:** `frontend/src/hooks/useAuth.ts:47`
**Issue:** The comment says the guard prevents "INITIAL_SESSION races" from clobbering a valid session, but the guard suppresses ALL null events except `SIGNED_OUT`. This means a legitimate `TOKEN_REFRESHED` event that fires with a null session (e.g. a revoked refresh token) would be silently dropped rather than signing the user out. The guard is wider than documented. A user with a revoked token on a non-callback page would remain in an authenticated-looking state until their next full page load triggers `getSession()` to re-evaluate.

**Fix:** Either narrow the guard to suppress only `INITIAL_SESSION` with null:
```ts
if (newSession === null && event === 'INITIAL_SESSION') return
```
Or document precisely which events are intentionally suppressed and why each is safe to ignore.

---

## [WARNING] full-uat.spec.ts: mark-missed test asserts the wrong endpoint was called

**File:** `frontend/tests/e2e/full-uat.spec.ts:414-441`
**Issue:** The test "Yes mark missed closes dialog and fires PATCH" sets up a `patchCalled` flag on the `/sessions/session-today-id` PATCH route, then asserts `expect(patchCalled).toBe(true)`. But `handleMarkMissed` in `SessionCard.tsx` calls `markSessionMissed`, which hits `POST /adaptations/sessions/{id}/missed` — not `PATCH /sessions/{id}`. The PATCH route for sessions is only called by `handleMarkDone`. The test assertion will always fail in a clean environment (patchCalled remains false) and is testing the wrong control flow. The dialog does close correctly, but the API assertion is wrong.

**Fix:** Replace the PATCH assertion with one on the adaptations endpoint:
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

## [WARNING] api.ts: createConversation falls back to empty string `''` on missing id

**File:** `frontend/src/lib/api.ts:195`
**Issue:** `data.conversation_id ?? data.id ?? ''` returns an empty string if both fields are absent (e.g. a backend regression). Callers receive a `Conversation` object with `id: ''` and proceed to make requests like `POST /conversations//messages`, producing cryptic 404s rather than a meaningful error at the source.

**Fix:**
```ts
const id = data.conversation_id ?? data.id
if (!id) throw new Error('createConversation: backend returned no id')
return { ...data, id } as unknown as Conversation
```

---

## [INFO] full-uat.spec.ts: rides route LIFO ordering is correct but undocumented

**File:** `frontend/tests/e2e/full-uat.spec.ts:231-232`
**Issue:** The fix registers `/rides/` (line 231) before `/rides/upload` (line 232). With Playwright's LIFO semantics, the upload handler wins for upload requests. This is correct, but there is no comment documenting the ordering dependency. A future developer adding another `/rides/` route after line 232 would inadvertently shadow the upload handler and break upload tests silently.

**Fix:** Add a comment:
```ts
// Registration order matters: LIFO means /rides/upload (last) wins over /rides/ for upload requests.
await page.route(/\/rides\//, ...)
await page.route(/\/rides\/upload/, ...)
```

---

## [INFO] SessionCard.tsx: redundant `onClick` on AlertDialogCancel

**File:** `frontend/src/components/session/SessionCard.tsx:246`
**Issue:** `AlertDialogCancel` (shadcn/ui) already calls `onOpenChange(false)` internally via its Radix `DialogClose` root. The explicit `onClick={() => setMissedOpen(false)}` duplicates the close call. Harmless now but double-fires any future close-tracking side effects.

**Fix:**
```tsx
<AlertDialogCancel>Keep it</AlertDialogCancel>
```

---

_Reviewed: 2026-06-21_
_Reviewer: Claude (adversarial)_
_Depth: standard_
