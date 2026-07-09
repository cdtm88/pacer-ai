---
quick_id: 260709-pxu
title: Remove Google Calendar integration
date: 2026-07-09
status: complete
---

# Quick Task 260709-pxu: Remove Google Calendar integration — Summary

Google Calendar was cut (no longer a requirement) from code, config, and forward docs.

## Removed
- **Backend:** deleted `calendar_sync.py`, `routes/calendar.py`; unmounted the `/calendar` router (`main.py`); deleted the `/onboarding/plan-calendar-sync` endpoint + import; removed all three calendar-sync blocks, the import, and both `calendar_event_id` selects from `adaptations.py`; dropped `calendar_event_id` from `sessions.py` `_SESSION_COLUMNS`; fixed the `db.py` module-list docstring; removed a stray `CAL-04` code comment in `onboarding.py`.
- **Frontend:** deleted `CalendarStatus.tsx`, `useCalendarStatus.ts`; removed the Google Calendar section + import from `SettingsScreen.tsx`; removed `CalendarSettings` / `getCalendarSettings` / `disconnectCalendar` from `api.ts`.
- **Tests:** deleted `test_calendar.py`; removed 4 calendar tests from `test_adaptations.py`, 1 from `test_onboarding.py`, and the `calendar_event_id` mock lines from `test_sessions.py` / `test_contracts.py`.
- **Config:** dropped `google-api-python-client`, `google-auth-oauthlib`, `google-auth-httplib2`, and the now-orphaned `cryptography` from `requirements.txt`.
- **Docs:** scrubbed Google Calendar from `.claude/CLAUDE.md`, `PROJECT.md`, `README.md`, `docs/prd.md`; removed `CAL-01..04` requirement definitions + traceability rows from `REQUIREMENTS.md`; removed the Phase 12 "Google Calendar Production Verification" entry from `ROADMAP.md` (checklist, details, progress-table row) and its empty phase dir; removed the `project-gcal-verification` memory + its index line; logged the removal in `STATE.md`.

## Verification
- Backend imports load clean; **pytest: 334 passed** (was 334 + 5 calendar failures).
- Frontend **tsc -b clean; vitest: 134 passed**.
- `grep` confirms no live code imports the deleted modules; only false-positive `calendar day/date` and the lucide `Calendar` (Agenda tab) icon remain.

## Left as-is (intentional)
- **Applied Supabase migrations** (`oauth_states` table + `calendar_event_id` column) — immutable DB history; they are now unused. A `DROP` migration is a clean follow-up if you want the schema gone.
- **`.env.example`** `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `CALENDAR_FERNET_KEY` — the file is permission-protected; remove these vars manually (and from the Vercel project env).
- **Completed Phase 4 "UI and Calendar"** historical planning artifacts (goal/plan/verification records across `04-*`, and the Phase 4/6/7 goal descriptions in `ROADMAP.md`) — archival records of delivered work, not rewritten.
