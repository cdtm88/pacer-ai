---
phase: 04-ui-and-calendar
plan: "01"
subsystem: backend-api
status: complete
tags: [api, supabase, migration, jwt, endpoints, sessions, pmc, profiles, rides, conversations]
dependency_graph:
  requires:
    - 04-02 (api/auth.py with get_current_user)
  provides:
    - supabase/migrations/0003_phase4_schema.sql (Phase 4 columns applied to live DB)
    - api/routes/sessions.py (four JWT-protected read endpoints)
    - GET /sessions/today
    - GET /sessions/upcoming
    - GET /pmc_history/latest
    - GET /profiles/me
    - GET /rides/ (added to rides.py)
    - POST /conversations/ (added to chat.py via conversations_router)
    - tests/api/test_sessions.py
  affects:
    - api/main.py (two new router includes)
    - api/routes/rides.py (new list endpoint)
    - api/routes/chat.py (conversations_router added)
tech_stack:
  added: []
  patterns:
    - WR-04 Supabase async singleton (module-level _supabase_client, acreate_client)
    - Depends(get_current_user) on all new endpoints; user_id from JWT sub claim
    - No-prefix router mounting in main.py for endpoints at non-/chat root paths
    - mock_supabase_factory_extended with .gte() and .limit() chain support in tests
key_files:
  created:
    - supabase/migrations/0003_phase4_schema.sql
    - api/routes/sessions.py
    - tests/api/test_sessions.py
  modified:
    - api/routes/rides.py (GET / list endpoint appended)
    - api/routes/chat.py (conversations_router + POST /conversations/ added)
    - api/main.py (sessions_router + conversations_router includes added)
decisions:
  - No-prefix router mounting chosen over three separate prefix mounts for
    sessions/pmc_history/profiles; cleaner than duplicating the same router
  - conversations_router defined in chat.py (alongside other conversation logic)
    and exported for no-prefix mounting in main.py
  - mock_supabase_factory_extended defined inline in test_sessions.py rather than
    patching conftest.py to avoid breaking existing test files
  - rides.py list endpoint uses .order("ride_date", desc=True, nullsfirst=False)
    to handle rides with null ride_date (older records before Phase 3 schema addition)
metrics:
  duration: "6 minutes"
  completed: "2026-06-20"
  tasks: 4
  files: 6
---

# Phase 04 Plan 01: Data Layer Endpoints Summary

Six backend read/create endpoints for the Phase 4 UI, backed by a DB migration applying five new columns to the live Supabase project.

## What Was Built

**DB migration** (`0003_phase4_schema.sql`): Added five columns across three tables using `ADD COLUMN IF NOT EXISTS` for idempotency. Applied to the live Supabase project `pxdfmlvrqveofguyxxfo` via `supabase db push --linked --yes`.

**`api/routes/sessions.py`** (new): Four JWT-protected GET endpoints using the WR-04 async Supabase singleton pattern.

**`api/routes/rides.py`** (modified): Added `GET /rides/` returning newest-first ride history with `compliance_pct` included.

**`api/routes/chat.py`** (modified): Added `conversations_router` with `POST /conversations/` calling the existing `create_conversation` helper from onboarding.py with `context_type='coaching'`.

**`api/main.py`** (modified): Two new `include_router` calls with no prefix so each endpoint resolves at its absolute URL path.

**`tests/api/test_sessions.py`** (new): 13 tests covering all 6 endpoints including unauthenticated rejection assertions on every new endpoint (T-04-01).

## Endpoint URLs Confirmed

| Endpoint | Handler | File |
|----------|---------|------|
| GET /sessions/today | today_session | api/routes/sessions.py |
| GET /sessions/upcoming | upcoming_sessions | api/routes/sessions.py |
| GET /pmc_history/latest | latest_pmc | api/routes/sessions.py |
| GET /profiles/me | profile_me | api/routes/sessions.py |
| GET /rides/ | list_rides | api/routes/rides.py |
| POST /conversations/ | create_chat_conversation | api/routes/chat.py |

## Tasks Completed

| Task | Name | Commit |
|------|------|--------|
| 1 | DB migration 0003 created and applied to live DB | da722f2 |
| 2 | api/routes/sessions.py with four JWT-protected GET handlers | 1de4c70 |
| 3 | GET /rides/ list + POST /conversations/ create endpoints | 3ffbf43 |
| 4 | Router mounting in main.py + test_sessions.py (13 tests passing) | bad936d |

## Verification

- `python -m pytest tests/api/test_sessions.py -x -q`: 13 passed
- `ast.parse` passes for all 4 modified Python files
- Migration applied: `Applying migration 0003_phase4_schema.sql... Finished supabase db push.`
- All 6 endpoints resolve at their documented URLs via router inspection

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Extended mock factory to support .gte() and .limit() chain methods**
- **Found during:** Task 4 test run
- **Issue:** `mock_supabase_factory` from conftest.py does not chain `.gte()` or `.limit()`, causing `TypeError: object MagicMock can't be used in 'await' expression` for the upcoming and pmc_history/latest endpoints
- **Fix:** Defined `mock_supabase_factory_extended` inline in test_sessions.py adding the missing chain methods; did not modify shared conftest.py to avoid breaking existing tests
- **Files modified:** tests/api/test_sessions.py
- **Commit:** bad936d

## Threat Surface Scan

No new network endpoints beyond those specified in the plan's threat model. All six new endpoints implement T-04-01 (Depends(get_current_user)) and T-04-03 (user_id filter on all Supabase queries). No new trust boundary crossings introduced.

## Known Stubs

None. All endpoints query live Supabase tables; there are no hardcoded placeholder values in any handler.

## Self-Check: PASSED

- supabase/migrations/0003_phase4_schema.sql: FOUND
- api/routes/sessions.py: FOUND
- tests/api/test_sessions.py: FOUND
- Commit da722f2: FOUND (migration)
- Commit 1de4c70: FOUND (sessions.py)
- Commit 3ffbf43: FOUND (rides + chat)
- Commit bad936d: FOUND (main.py + tests)
- All 13 tests: PASSED
