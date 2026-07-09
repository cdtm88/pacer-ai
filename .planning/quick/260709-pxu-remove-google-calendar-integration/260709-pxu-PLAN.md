---
quick_id: 260709-pxu
title: Remove Google Calendar integration
date: 2026-07-09
---

# Quick Task 260709-pxu: Remove Google Calendar integration

Feature cut, no longer a requirement. Remove the Google Calendar integration from
code, config, and forward-looking docs while keeping the build green.

## Tasks

1. **Backend feature removal.** Delete `backend/calendar_sync.py`, `backend/routes/calendar.py`; unmount the calendar router in `main.py`; remove the `/onboarding/plan-calendar-sync` endpoint + import; strip all calendar-sync blocks and `calendar_event_id` selects from `adaptations.py`; drop `calendar_event_id` from the `sessions.py` select; fix the `db.py` module-list docstring.
2. **Frontend feature removal.** Delete `CalendarStatus.tsx`, `useCalendarStatus.ts`; remove the Google Calendar section + import from `SettingsScreen.tsx`; remove `CalendarSettings`/`getCalendarSettings`/`disconnectCalendar` from `api.ts`. Keep the lucide `Calendar` icon (Agenda tab) untouched.
3. **Tests.** Delete `tests/api/test_calendar.py`; remove the 5 calendar-specific tests from `test_adaptations.py`/`test_onboarding.py` and the `calendar_event_id` mock lines from `test_sessions.py`/`test_contracts.py`.
4. **Config + docs.** Drop `google-*` + `cryptography` deps from `requirements.txt`; scrub Google Calendar from `.claude/CLAUDE.md`, `REQUIREMENTS.md` (CAL-01..04), `ROADMAP.md` (Phase 12), `PROJECT.md`, `README.md`, `docs/prd.md`, `STATE.md`; delete the `project-gcal-verification` memory.

## Verify
- Backend imports load; `pytest` green.
- Frontend `tsc -b` clean; `vitest` green.
- `grep` shows no live code imports the deleted modules; only false-positive "calendar day/date" + lucide-icon refs remain.

## Out of scope (left as-is)
- Applied Supabase migrations (oauth_states table, calendar_event_id column) — immutable history; drop migration is a follow-up.
- Completed Phase 4 "UI and Calendar" historical planning artifacts.
- `.env.example` GOOGLE_*/CALENDAR_FERNET_KEY vars — permission-protected, manual removal.
