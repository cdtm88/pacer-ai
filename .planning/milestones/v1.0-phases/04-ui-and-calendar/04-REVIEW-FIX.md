---
phase: "04"
padded_phase: "04"
status: "all_fixed"
fix_scope: "critical_warning"
findings_in_scope: 12
fixed: 12
skipped: 0
iteration: 2
fixed_at: "2026-06-21"
---

# Phase 04: Code Review Fix Report

**Fixed at:** 2026-06-21
**Source review:** `.planning/phases/04-ui-and-calendar/04-REVIEW.md`
**Iteration:** 2

**Summary:**
- Findings in scope: 12 (4 Critical, 8 Warning)
- Fixed: 12
- Skipped: 0

## Fixed Issues

### CR-01: `UnboundLocalError` crash in `mark_session_missed` when signal detection raises

**Files modified:** `api/routes/adaptations.py`
**Commit:** `fix(04): CR-01 pre-initialise scope to avoid UnboundLocalError on detection failure`
**Applied fix:** Added `scope = None` pre-initialisation before the `try` block, alongside the existing `signals` and `result` pre-initialisations. Also added `import logging` and `logger = logging.getLogger(__name__)` at module level (required by WR-02 fix).

---

### CR-02: JWT exposed in URL for POST requests in `OnboardingScreen`

**Files modified:** `frontend/src/screens/OnboardingScreen.tsx`
**Commit:** `fix(04): CR-02 replace sseUrl with Authorization header for POST requests in OnboardingScreen`
**Applied fix:** Removed `sseUrl` import, added `supabase` import. Both `runStream` and `handleConfirm` now call `supabase.auth.getSession()` directly and pass the token as an `Authorization: Bearer` header. The URL is constructed from `import.meta.env.VITE_API_URL` directly. No JWT appears in URLs or query strings for POST requests.

---

### CR-03: Google Calendar all-day events have identical start and end date

**Files modified:** `api/calendar_sync.py`
**Commit:** `fix(04): CR-03 set all-day event end date to start+1 day for Google Calendar API compliance`
**Applied fix:** Added `import datetime as _dt` and `from datetime import timedelta`. In `_build_event_body`, compute `end_date` as `start + 1 day` via `_dt.date.fromisoformat` with a `ValueError` fallback. The `end.date` field now always differs from `start.date` by one day, satisfying the Google Calendar API exclusive-end-date requirement.

---

### CR-04: `update_session` (PATCH) can clobber a `missed` session back to `completed`

**Files modified:** `api/routes/sessions.py`
**Commit:** `fix(04): CR-04 guard PATCH session to prevent overwriting missed status back to completed`
**Applied fix:** Added `.eq("status", "planned")` filter to the Supabase update query in the PATCH handler. The existing 404 response now naturally rejects any attempt to complete an already-missed or already-completed session.

---

### WR-01: OAuth callback HMAC key falls back to empty string when `SUPABASE_JWT_SECRET` is unset

**Files modified:** `api/routes/calendar.py`
**Commit:** `fix(04): WR-01 reject OAuth callback with 500 when SUPABASE_JWT_SECRET is unset`
**Applied fix:** In the callback handler, changed `os.environ.get("SUPABASE_JWT_SECRET", "")` to `os.environ.get("SUPABASE_JWT_SECRET")` and added an explicit `if not secret: raise HTTPException(500, ...)` guard before the HMAC computation.

---

### WR-02: Bare `except Exception: pass` in `mark_session_missed` hides all errors silently

**Files modified:** `api/routes/adaptations.py`
**Commit:** `fix(04): WR-02 replace silent except pass with logger.warning for signal detection failures`
**Applied fix:** Replaced `pass` with `logger.warning("Signal detection/adaptation failed for session %s (non-fatal)", session_id, exc_info=True)`.

---

### WR-03: `useAuth.ts` `onAuthStateChange` null guard is wider than documented

**Files modified:** `frontend/src/hooks/useAuth.ts`
**Commit:** `fix(04): WR-03 narrow auth null guard to INITIAL_SESSION only so revoked tokens sign users out`
**Applied fix:** Changed `event !== 'SIGNED_OUT'` to `event === 'INITIAL_SESSION'` in the null guard. Updated the comment to accurately describe the intent: only `INITIAL_SESSION` races are suppressed; other null events (e.g. revoked `TOKEN_REFRESHED`) now propagate to clear the session.

---

### WR-04: `useAuth.ts` callback guard uses `includes` instead of exact match

**Files modified:** `frontend/src/hooks/useAuth.ts`
**Commit:** `fix(04): WR-04 use exact pathname match for auth callback guard instead of includes`
**Applied fix:** Changed `window.location.pathname.includes('/auth/callback')` to `window.location.pathname === '/auth/callback'`.

---

### WR-05: Dual `duration` columns create split-brain after micro-adjustment

**Files modified:** `api/routes/adaptations.py`
**Commit:** `fix(04): WR-05 sync duration_mins alongside duration_minutes in micro-adjustment`
**Applied fix:** Added `"duration_mins": new_dur` to the `apply_micro_adjustment` Supabase update dict, keeping both columns in sync after every adjustment.

---

### WR-06: `apiFetch` silently constructs malformed URLs when `VITE_API_URL` is undefined

**Files modified:** `frontend/src/lib/api.ts`
**Commit:** `fix(04): WR-06 throw clear error when VITE_API_URL is not set`
**Applied fix:** Added `if (!BASE) throw new Error('VITE_API_URL is not set. Add it to .env.local.')` immediately after the `const BASE` assignment. The error is thrown at module load time.

---

### WR-07: E2E test `full-uat.spec.ts` mark-missed assertion tests the wrong endpoint

**Files modified:** `frontend/tests/e2e/full-uat.spec.ts`
**Commit:** `fix(04): WR-07 fix mark-missed E2E test to assert adaptations endpoint not PATCH sessions`
**Applied fix:** Replaced the PATCH `/sessions/session-today-id` interception and `patchCalled` assertion with a `missedCalled` flag intercepting `POST /adaptations/sessions/session-today-id/missed`. Removed the unused PATCH route stub and updated the test name.

---

### WR-08: `createConversation` in `api.ts` silently returns `id: ''` on missing id field

**Files modified:** `frontend/src/lib/api.ts`
**Commit:** `fix(04): WR-08 throw on missing conversation id instead of silently returning empty string`
**Applied fix:** Extracted `const id = data.conversation_id ?? data.id` and added `if (!id) throw new Error('createConversation: backend returned no conversation id')`. Callers now receive a thrown error instead of a `Conversation` with `id: ''`.

---

## Skipped Issues

None.

---

_Fixed: 2026-06-21_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 2_
