---
phase: 03-coaching-loop
plan: "04"
subsystem: fit-ingestion, rides-endpoint, tss-pmc-pipeline
tags: [fitdecode, rides, TSS, PMC, FIT-01, FIT-02, FIT-03, FIT-04, FIT-05, FIT-06, D-12, D-14, D-15]
dependency_graph:
  requires: [03-01, 03-02, 03-03]
  provides: [api/routes/rides.py, api/main.py@rides-router, tests/api/test_rides.py@filled]
  affects: [03-05]
tech_stack:
  added: []
  patterns: [asyncio-to-thread-cpu-parse, background-tasks-pipeline, fitdecode-WARN, cold-start-ftp-150W, supabase-upsert-conflict, filename-sanitize-path-traversal]
key_files:
  created:
    - api/routes/rides.py
  modified:
    - api/main.py
    - tests/api/test_rides.py
decisions:
  - "parse_fit_file is sync and runs under asyncio.to_thread; all Supabase calls in process_ride_background are async and never wrapped in to_thread (Risk 4)"
  - "Cold-start FTP = 150.0W recorded in rides.ftp_used for audit trail and future backfill (T-03-15)"
  - "estimate_ftp_from_rides confidence must be 'medium' or 'high' before using calculated FTP; else falls back to 150W placeholder"
  - "validate_session_vs_actual is best-effort: training_sessions SELECT failure is logged and skipped, never blocks the pipeline"
  - "Ride debrief conversation (D-23) is best-effort: wrapped in try/except, never blocks the response"
  - "datetime.utcnow() replaced with datetime.now(timezone.utc) to eliminate deprecation warning"
  - "filename sanitized with os.path.basename + re.sub before building Storage path (T-03-13)"
metrics:
  duration: "8 minutes"
  completed: "2026-06-20"
  tasks_completed: 2
  files_created: 1
  files_modified: 2
status: complete
---

# Phase 03 Plan 04: FIT Ingestion Pipeline Summary

**One-liner:** `POST /rides/upload` built with fitdecode WARN parser in asyncio.to_thread, background TSS/PMC pipeline (compute_tss + update_pmc + validate_session_vs_actual), 150W cold-start placeholder in ftp_used, 25 MB size cap, and the FIT-06 real Zwift fixture acceptance test asserting TSS > 0.

## What Was Built

### Task 1: FIT parser + /rides/upload endpoint + background TSS/PMC pipeline

**`api/routes/rides.py`** (529 lines, created):

**`_get_async_supabase()`** -- module-level cached async Supabase client (WR-04 pattern from capability_gap.py).

**`parse_fit_file(file_bytes: bytes) -> Optional[dict]`** -- SYNC function for asyncio.to_thread:
- `fitdecode.FitReader(BytesIO, error_handling=fitdecode.ErrorHandling.WARN)` iterates FIT frames
- `frame.get_value('power', fallback=None)`, `get_value('heart_rate', fallback=None)`, `get_value('cadence', fallback=None)` (3 get_value calls with fallback)
- First record frame field names logged via `logging.info` (Risk 3 / Open Question 3 debug aid)
- Missing HR/cadence -> None -> not appended to hr_samples/cadence_samples (FIT-03 graceful handling)
- power None -> 0.0 (zeros valid for NP calculation)
- Returns `{power_array, hr_array, cadence_array, duration_secs, avg_power, avg_hr, avg_cadence}` or None on exception

**`get_user_ftp(user_id) -> tuple[float, bool]`** -- async FTP resolver:
- Queries user's recent rides and runs estimate_ftp_from_rides
- Returns (ftp, is_estimated=False) when confidence is 'medium' or 'high'
- Falls back to (150.0, True) for insufficient data (cold-start; is_estimated=True)

**`process_ride_background(ride_id, user_id, parsed, ftp_used)`** -- async background pipeline (D-15):
1. `compute_tss(power_array, duration_secs, ftp_used)` -> TSS, np_watts, intensity_factor
2. Load prev_ctl/prev_atl/days_of_data from pmc_history (cold-start: 0/0/0)
3. `update_pmc(prev_ctl, prev_atl, tss, days_of_data)` -> new CTL/ATL/TSB/tss_display_ready
4. `validate_session_vs_actual` on today's training_sessions row if present (FIT-05, best-effort)
5. UPDATE rides row: tss, np_watts, intensity_factor, avg_power, avg_hr, avg_cadence, ftp_used, compliance_pct
6. UPSERT pmc_history on conflict (user_id, date)
7. INSERT ride_debrief conversation row (D-23, best-effort, wrapped in try/except)

**`upload_fit` endpoint (POST /rides/upload)**:
- Size cap: reject > 25 MB before parse (T-03-11)
- `await asyncio.to_thread(parse_fit_file, file_bytes)` (D-12)
- 422 if parsed is None or duration_secs < 600 (D-14, T-03-12): `{"error": "fit_parse_failed", ...}`
- `_sanitize_filename`: os.path.basename + re.sub non-alphanumeric (T-03-13)
- Storage upload best-effort (continues even if storage fails)
- INSERT stub rides row; capture ride_id from result.data[0]["id"]
- `background_tasks.add_task(process_ride_background, ride_id, user_id, parsed, ftp_used)`
- Return `{"ride_id": ride_id, "status": "processing"}`

**`api/main.py`** (modified):
- Added `from api.routes.rides import router as rides_router`
- Added `app.include_router(rides_router, prefix="/rides", tags=["rides"])`
- Onboarding and chat routers untouched

### Task 2: Rides tests (all Wave 3 stubs filled)

**`tests/api/test_rides.py`** (all 6 stubs replaced + fixture check preserved, 8 tests total):

- `test_upload_returns_200` (FIT-01): POST with real fixture, mocked DB/bg, asserts 200 + ride_id + status=processing
- `test_fit_parse_warn` (FIT-02): parse_fit_file on real fixture; asserts power_array non-empty, duration >= 600, no exception raised
- `test_missing_fields` (FIT-03): patches fitdecode.FitDataMessage.get_value to return None for hr/cadence; asserts avg_hr=None, avg_cadence=None, power_array non-empty
- `test_tss_computed` (FIT-04): drives process_ride_background with real fixture parsed; captures rides UPDATE payload; asserts tss > 0, np_watts present, pmc_history UPSERT called
- `test_session_compliance` (FIT-05): mock returns a training_sessions row; asserts compliance_pct in rides UPDATE payload
- `test_fit_upload_integration` (FIT-06): real .FIT fixture end-to-end; captures bg args; drives compute_tss directly; asserts TSS > 0 (core FIT-06 assertion)
- `test_corrupt_fit_returns_422`: non-FIT bytes; asserts 422 + detail["error"] == "fit_parse_failed"
- `test_fixture_exists`: fixture existence assertion (preserved from Wave 0)

## Test Results

```
179 passed, 7 skipped, 2 warnings in 0.78s
```

7 new tests added (8 total in test_rides.py, 1 was pre-existing fixture check). No regressions.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] datetime.utcnow() deprecated in Python 3.12**
- **Found during:** Task 2 test run (DeprecationWarning visible in pytest output)
- **Issue:** `datetime.utcnow()` is deprecated and scheduled for removal; pytest emits DeprecationWarning
- **Fix:** Changed to `datetime.now(timezone.utc).date().isoformat()` in upload_fit
- **Files modified:** `api/routes/rides.py`
- **Commit:** 5f287f3

No other deviations -- plan executed as written. The cold-start FTP path (150W) and best-effort patterns matched the plan spec exactly.

## Threat Surface Scan

All mitigations from the plan's threat model are implemented:

| Threat ID | Mitigation | Location |
|-----------|-----------|----------|
| T-03-11 (DoS upload size) | `if len(file_bytes) > MAX_UPLOAD_BYTES: raise 422` before parse | upload_fit |
| T-03-12 (malformed FIT) | `ErrorHandling.WARN` + `duration_secs < 600` guard -> 422 | parse_fit_file + upload_fit |
| T-03-13 (path traversal) | `_sanitize_filename` with basename + re.sub | upload_fit |
| T-03-14 (cross-user data) | rides/pmc_history inserts scoped to supplied user_id | process_ride_background |
| T-03-15 (ftp_used audit) | `ftp_used=150.0` written in both INSERT and UPDATE | upload_fit + process_ride_background |

No new threat surface beyond the plan's threat model.

## Known Stubs

None -- all functions fully implemented. The ride_debrief conversation trigger (D-23) is intentionally best-effort per the plan; it creates a conversations row but does not start an SSE session (that is Phase 4 or 5 scope).

## Self-Check

### Files created/modified:
- /Users/christianmoore/ai/pacer-ai/api/routes/rides.py: FOUND
- /Users/christianmoore/ai/pacer-ai/api/main.py: FOUND
- /Users/christianmoore/ai/pacer-ai/tests/api/test_rides.py: FOUND

### Commits:
- 21ab055: feat(03-04): add FIT parser, /rides/upload endpoint, and background TSS/PMC pipeline
- 5f287f3: feat(03-04): fill in rides tests covering FIT-01 through FIT-06 acceptance test

## Self-Check: PASSED
