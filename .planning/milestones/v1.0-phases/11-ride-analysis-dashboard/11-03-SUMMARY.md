---
phase: 11-ride-analysis-dashboard
plan: 03
subsystem: api
tags: [fastapi, python, supabase-storage, idor, tdd]

# Dependency graph
requires:
  - phase: 11-ride-analysis-dashboard
    provides: "parse_fit_stream(file_bytes) + detect_presence()/downsample() (11-01)"
  - phase: 11-ride-analysis-dashboard
    provides: "time_in_hr_zones(hr_array, lthr) sports-science tool (11-02)"
provides:
  - "GET /rides/{id}/stream: parse-on-demand endpoint returning series, channels, laps, hr_zone_distribution scoped to the caller"
affects: [11-04, 11-05, 11-06, 11-07, ride-analysis-dashboard-frontend]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Two-table dual-select route: rides (dual-filter IDOR) then profiles (lthr-only), mirrors sessions.py::export_session_zwo's rides/profiles(ftp) sequence exactly"
    - "Presence computed from the full series before downsample() is applied for charting -- downsampling must never affect a channel's detected presence"
    - "hr_zone_distribution computed from the full (non-downsampled) HR array for correctness, even though series in the response is downsampled"

key-files:
  created: []
  modified:
    - backend/routes/rides.py
    - tests/api/test_rides_stream.py

key-decisions:
  - "LTHR resolved exclusively from profiles.lthr; estimate_lthr_from_max_hr is never called from this route (RESEARCH.md Pitfall 3) -- hr_zone_distribution stays null whenever lthr is unset, even when heart_rate is present"
  - "IDOR guard mirrors sessions.py::export_session_zwo verbatim: dual .eq('id', ride_id).eq('user_id', user_id) filter, uniform 404 on any miss (never 403, which would leak ride existence to another user)"
  - "Storage download and parse failures both collapse to structured error responses (404 for missing/unreadable Storage object, 422 for a file that downloads but fails to parse) rather than a generic 500"

requirements-completed: [RIDE-05, RIDE-12]

coverage:
  - id: D1
    description: "GET /rides/{id}/stream returns 200 with series, channels, laps, and hr_zone_distribution for the caller's own ride"
    requirement: "RIDE-05"
    verification:
      - kind: integration
        ref: "tests/api/test_rides_stream.py#test_stream_happy_zwift_altitude_absent"
        status: pass
      - kind: integration
        ref: "tests/api/test_rides_stream.py#test_stream_happy_hilly_altitude_present"
        status: pass
    human_judgment: false
  - id: D2
    description: "A ride belonging to another user returns 404, never that user's data (IDOR, T-11-01)"
    requirement: "RIDE-05"
    verification:
      - kind: integration
        ref: "tests/api/test_rides_stream.py#test_stream_idor_returns_404"
        status: pass
    human_judgment: false
  - id: D3
    description: "A ride with null raw_fit_path returns 404; a corrupt stored file returns 422; a storage download failure returns 404; a malformed ride_id returns 400 before any DB call (T-11-02, T-11-03, V5)"
    requirement: "RIDE-12"
    verification:
      - kind: integration
        ref: "tests/api/test_rides_stream.py#test_stream_missing_raw_fit_path_404"
        status: pass
      - kind: integration
        ref: "tests/api/test_rides_stream.py#test_stream_storage_download_fails_404"
        status: pass
      - kind: integration
        ref: "tests/api/test_rides_stream.py#test_stream_corrupt_file_422"
        status: pass
      - kind: integration
        ref: "tests/api/test_rides_stream.py#test_stream_bad_uuid_400"
        status: pass
    human_judgment: false
  - id: D4
    description: "hr_zone_distribution is null when the profile has no LTHR, even if the ride has heart-rate samples; populated only when profiles.lthr is set AND heart_rate channel is present (RESEARCH Pitfall 3, A3)"
    requirement: "RIDE-05"
    verification:
      - kind: integration
        ref: "tests/api/test_rides_stream.py#test_stream_no_lthr_distribution_null"
        status: pass
      - kind: integration
        ref: "tests/api/test_rides_stream.py#test_stream_happy_zwift_altitude_absent"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-09
status: complete
---

# Phase 11 Plan 03: Ride Stream Endpoint Summary

**`GET /rides/{id}/stream` parse-on-demand endpoint wires together the 11-01 parser/util layer and the 11-02 `time_in_hr_zones` tool behind an IDOR-safe, Storage-scoped, LTHR-gated route, built test-first against all three phase threats.**

## Performance

- **Duration:** 20 min
- **Started:** 2026-07-09T16:31:00Z (approx, continuing wave 1 execution)
- **Completed:** 2026-07-09T16:51:33Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 2 (1 new-route addition to `rides.py`, 1 appended test file)

## Accomplishments

- Added `GET /rides/{ride_id}/stream` to `backend/routes/rides.py`: dual `.eq("id").eq("user_id")` IDOR guard, `validate_uuid` before any DB call, Storage download wrapped in try/except, `asyncio.to_thread(parse_fit_stream, ...)` off the event loop, channel presence detected from the full series before `downsample()`, and `hr_zone_distribution` computed from the full HR array via `time_in_hr_zones` -- gated strictly on `profiles.lthr` being set (no `estimate_lthr_from_max_hr` fallback).
- Appended 8 endpoint integration tests to `tests/api/test_rides_stream.py` covering both fixtures' happy paths (zwift altitude absent / hilly altitude present), the no-LTHR null-distribution case, IDOR (dual-filter miss), missing `raw_fit_path`, Storage download failure, corrupt-file 422, and malformed-UUID 400 -- with a shared `_make_stream_client_mock` helper dispatching the rides-then-profiles two-table `.execute()` sequence by call order, following `_make_rides_mock`'s `execute_dispatch` counter pattern from `test_rides.py`.
- RED confirmed: all 8 new tests failed with `404 Not Found` (route did not exist) before implementation.
- GREEN confirmed: all 17 tests in `tests/api/test_rides_stream.py` pass (9 from 11-01's data layer + 8 new endpoint tests); no regression in `tests/api/test_rides.py` (14 tests) or `tests/sports_science` (98 tests); `ruff check backend/routes/rides.py` clean.
- Verified live against both real fixtures that they carry `heart_rate` data (`detect_presence` True on both), confirming the happy-path/no-LTHR test design was sound before writing assertions.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing integration tests for the stream endpoint** - `a7b6281` (test)
2. **Task 2 (GREEN): Implement GET /{ride_id}/stream** - `8b7de64` (feat)

_TDD plan: RED confirmed via 404 Not Found on all 8 new endpoint tests (route did not exist); GREEN confirmed via full-suite pass with zero regressions._

## Files Created/Modified

- `backend/routes/rides.py` - Additive: `get_ride_stream` route (`GET /{ride_id}/stream`) appended after `list_rides`; three new imports (`detect_presence`, `downsample`, `time_in_hr_zones`) added to the top-of-file import block; no existing route touched.
- `tests/api/test_rides_stream.py` - Appended 8 endpoint integration tests plus a `_make_stream_client_mock` helper and `TEST_RIDE_ID` constant; new imports (`AsyncMock`, `MagicMock`, `httpx`, `ASGITransport`, `tests.api.conftest` fixtures).

## Decisions Made

- LTHR resolution reads `profiles.lthr` exclusively -- confirmed no call to `estimate_lthr_from_max_hr` appears anywhere in the route handler, per RESEARCH.md Pitfall 3.
- `hr_zone_distribution` is computed from the full (pre-downsample) HR array, not the downsampled `series` response payload, to avoid skewing zone-time percentages by the stride-sampling used for charting (TRUST-01 correctness).
- The two-table Supabase mock (`rides` then `profiles`) dispatches by call-order counter rather than by table-name argument, matching the existing `_make_rides_mock`/`execute_dispatch` convention already established in `test_rides.py` (`client_mock.table` is a single `MagicMock` regardless of the table name passed).
- IDOR test asserts a plain `[]` rides-SELECT result (dual-filter miss) rather than constructing a second user's JWT, matching the plan's explicit test-design guidance and mirroring how `sessions.py::export_session_zwo`'s own IDOR test is structured.

## Deviations from Plan

None - plan executed exactly as written. Both tasks matched the plan's `<action>` steps verbatim (dual-filter IDOR guard, Storage try/except -> 404, `asyncio.to_thread` parse, presence-before-downsample, profiles.lthr-only resolution, full-array `time_in_hr_zones` call).

## Issues Encountered

None. The worktree had no local `.venv`, so verification ran against the shared project `.venv` at `/Users/christianmoore/ai/pacer-ai/.venv/bin/python` (same interpreter/dependencies as the main checkout; `fitdecode` is not installed at the system Python level).

## User Setup Required

None - no external service configuration required. No new dependencies.

## Next Phase Readiness

- `GET /rides/{id}/stream` is live and ready for the frontend plans (11-04+) to consume via `getRideStream()` per `11-PATTERNS.md`'s documented response shape (`series`, `channels`, `laps`, `hr_zone_distribution`).
- The endpoint's response contract (`Record<channel, bool>` for `channels`, `RideZoneDistribution[] | null` for `hr_zone_distribution`, `number[]` for `laps`) exactly matches the TypeScript interfaces already drafted in `11-PATTERNS.md`, so no contract renegotiation is needed downstream.
- No blockers.

---
*Phase: 11-ride-analysis-dashboard*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: backend/routes/rides.py
- FOUND: tests/api/test_rides_stream.py
- FOUND: .planning/phases/11-ride-analysis-dashboard/11-03-SUMMARY.md
- FOUND: get_ride_stream in backend/routes/rides.py
- FOUND: commit a7b6281 (test RED)
- FOUND: commit 8b7de64 (feat GREEN)
