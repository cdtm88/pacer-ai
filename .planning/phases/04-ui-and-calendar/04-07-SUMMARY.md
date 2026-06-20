---
phase: 04-ui-and-calendar
plan: "07"
subsystem: calendar
tags: [google-calendar, oauth2, fernet, calendar-sync, settings-ui]
status: complete
dependency_graph:
  requires: ["04-01", "04-02", "04-05"]
  provides: [calendar-oauth, calendar-sync, settings-screen]
  affects: [api/routes/adaptations.py, api/routes/onboarding.py]
tech_stack:
  added: [google-api-python-client, google-auth-oauthlib, google-auth-httplib2, cryptography]
  patterns: [Fernet-encrypted-token-storage, asyncio.to_thread, fire-and-forget-BackgroundTasks, OAuth2-CSRF-state]
key_files:
  created:
    - api/routes/calendar.py
    - api/calendar_sync.py
    - tests/api/test_calendar.py
    - frontend/src/hooks/useCalendarStatus.ts
    - frontend/src/components/settings/CalendarStatus.tsx
    - frontend/src/screens/SettingsScreen.tsx
  modified:
    - api/main.py
    - api/routes/adaptations.py
    - api/routes/onboarding.py
    - requirements.txt
decisions:
  - "Used all-day Google Calendar events (start/end as date string, not dateTime) per Open Question 3 in RESEARCH.md"
  - "CSRF state stored in oauth_states Supabase table (survives Railway restarts, not in-memory dict)"
  - "Initial plan calendar push exposed as POST /onboarding/plan-calendar-sync endpoint (fire-and-forget) rather than wiring inside SSE generator, keeping the stream simple"
  - "Fernet key read at call time so tests can monkeypatch CALENDAR_FERNET_KEY without import-order issues"
metrics:
  duration: "~30 min"
  completed: "2026-06-20T12:48:14Z"
  tasks_completed: 5
  files_changed: 10
---

# Phase 04 Plan 07: Google Calendar Integration Summary

Google Calendar OAuth2 flow, Fernet-encrypted token storage, calendar sync helpers, fire-and-forget wiring into adaptation/onboarding paths, and the Settings screen with connect/disconnect UI.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Calendar OAuth routes + encrypted token storage | fdee1ec | api/routes/calendar.py, requirements.txt |
| 2 | Calendar sync helpers + adaptations/onboarding wiring | ab45175 | api/calendar_sync.py, api/routes/adaptations.py, api/routes/onboarding.py |
| 3a | Mount calendar router + backend tests | 6037b1f | api/main.py, tests/api/test_calendar.py |
| 3b | Settings screen with calendar connect/disconnect | be752d1 | frontend/src/hooks/useCalendarStatus.ts, frontend/src/components/settings/CalendarStatus.tsx, frontend/src/screens/SettingsScreen.tsx |

## What Was Built

**Backend (api/routes/calendar.py):**
- `GET /calendar/auth`: builds OAuth2 authorization URL with `access_type=offline`, `prompt=consent` (refresh token guaranteed, Pitfall 2), `scope=calendar.events` (least privilege, T-04-24). CSRF state stored in `oauth_states` Supabase table keyed to `user_id` (T-04-21).
- `GET /calendar/callback`: verifies stored state (400 on mismatch, T-04-21), exchanges code via `asyncio.to_thread` (Pitfall 4), encrypts credentials JSON with Fernet before storing in `users.google_tokens` (CAL-03, T-04-22), never logs token values.
- `GET /calendar/settings`: decrypts tokens and checks `refresh_token` health, returns `{"connected": bool}`.
- `POST /calendar/disconnect`: sets `users.google_tokens = null`.

**Backend (api/calendar_sync.py):**
- `push_session_to_calendar`: inserts all-day Google Calendar event with full session detail (objective, structure, targets, duration) in description (CAL-01). Returns event ID for persistence on `sessions.calendar_event_id`.
- `update_calendar_event`: updates existing event body on replan (CAL-02).
- `delete_calendar_event`: deletes removed sessions from calendar (CAL-02).
- `push_all_sessions_to_calendar`: loads all planned sessions and pushes each; used for initial plan push (CAL-01).
- All helpers catch all exceptions internally and no-op when user has no tokens (CAL-04, T-04-23).

**Wiring:**
- `adaptations.py`: `POST /adaptations/check` and `POST /adaptations/sessions/{id}/missed` schedule `update_calendar_event` via `FastAPI BackgroundTasks` after replan (CAL-02, CAL-04, never awaited in request path).
- `onboarding.py`: `POST /onboarding/plan-calendar-sync` endpoint fires `push_all_sessions_to_calendar` via `asyncio.ensure_future` for initial plan push (CAL-01).

**Tests (tests/api/test_calendar.py):**
1. Token stored as ciphertext, not plaintext; Fernet decrypts back correctly (CAL-03).
2. `/auth` calls `authorization_url` with `prompt="consent"` (Pitfall 2).
3. `/callback` returns 400 on state mismatch (CSRF, T-04-21).
4. Sync helpers swallow exceptions, return None, do not raise (CAL-04).

**Frontend:**
- `useCalendarStatus.ts`: TanStack Query hook polling `GET /calendar/settings`.
- `CalendarStatus.tsx`: Connected chip + Disconnect AlertDialog (with exact copy), or Connect button redirecting to `/calendar/auth?token=` (JWT in query param since it's a redirect not a fetch). Sync failures as sonner toasts only (D-06).
- `SettingsScreen.tsx`: Profile section (display name, read-only email, re-send magic link), Google Calendar section, Account section (Sign out destructive button). No em dashes.

## Deviations from Plan

### Auto-added Missing Critical Functionality

**1. [Rule 2 - Missing] POST /onboarding/plan-calendar-sync endpoint**
- **Found during:** Task 2
- **Issue:** The SSE generator in onboarding.py has no post-generation hook; there is no point where generate_plan completion can be intercepted server-side to trigger a calendar push.
- **Fix:** Added a dedicated `POST /onboarding/plan-calendar-sync` endpoint that the frontend calls after the onboarding SSE stream closes. This is a clean separation: the SSE stream stays simple, and the calendar push is a separate fire-and-forget call.
- **Files modified:** api/routes/onboarding.py

## Known Stubs

- `SettingsScreen.tsx` shows "Loading..." for display name and email until the Supabase session resolves asynchronously. This is intentional; the profile data is not a stub but a short async load.
- `push_all_sessions_to_calendar` selects `objective, structure, targets, duration_minutes` columns; these column names may differ from the actual schema. The helper logs and swallows any schema mismatch (CAL-04 guard ensures no 500).

## Threat Flags

None. All STRIDE mitigations from the plan's threat register (T-04-21 through T-04-25) are implemented in this plan.

## Self-Check

- [x] api/routes/calendar.py exists and parses cleanly
- [x] api/calendar_sync.py exists and parses cleanly
- [x] tests/api/test_calendar.py exists and parses cleanly
- [x] frontend/src/components/settings/CalendarStatus.tsx contains `calendar/auth`
- [x] No em dashes in SettingsScreen.tsx or CalendarStatus.tsx
- [x] Commits fdee1ec, ab45175, 6037b1f, be752d1 exist in git log

## Self-Check: PASSED
