---
phase: 04-ui-and-calendar
plan: 16
subsystem: fit-upload
status: complete
tags: [gap-closure, fit-upload, rides, api]
dependency_graph:
  requires: [04-06]
  provides: [accurate-fit-duration, structured-upload-error]
  affects: [history-screen, fit-upload-zone]
tech_stack:
  added: []
  patterns:
    - timestamp-based FIT duration computation
    - structured backend error surfacing in fetch wrapper
key_files:
  modified:
    - api/routes/rides.py
    - frontend/src/lib/api.ts
    - frontend/src/tests/history.test.tsx
decisions:
  - id: D-16-01
    decision: "Use (last_record_ts - first_record_ts) + 1 for duration when both timestamps present; fall back to len(power_samples)"
    rationale: "Smart-recording devices emit fewer than 1 record/sec; sample count underestimates duration on those files"
  - id: D-16-02
    decision: "Extract backend detail.detail string from structured 422 body; fall back to bare status code"
    rationale: "Backend already returns {detail: {error, detail}}; surfacing it gives the user a meaningful error message"
metrics:
  duration: "8min"
  completed_date: "2026-06-21"
  tasks_completed: 2
  files_modified: 3
requirements: [UI-04]
---

# Phase 04 Plan 16: FIT Upload 422 Fix Summary

Closed UAT GAP 4 (Tests 12 and 13): FIT upload was failing with a bare "uploadRide failed: 422" for every upload. Root causes were (a) potential duration undercount on smart-recording devices and (b) uploadRide in api.ts using a wrong response type and swallowing the backend's structured error detail.

## Diagnosis

**File used:** `tests/fixtures/sample_zwift.fit` (8228 bytes, the fixture used by the existing test suite).

**parse_fit_file results on sample_zwift.fit:**
- Returned: non-None (parse succeeded)
- power_samples count: 900
- duration_secs (old, sample-count method): 900
- duration_secs (new, timestamp method): 900
- first_record field names: logged at INFO level on first parse
- start_time: 2025-01-01 00:00:00+00:00

The fixture file records at exactly 1 Hz (900 frames spanning 899 seconds last-minus-first + 1 = 900), so both methods agree. The fixture works correctly today, meaning the UAT failure was most likely caused by a real Zwift export that uses smart recording (non-1Hz), which would produce fewer frames than seconds and cause the 10-minute gate to fire incorrectly on a valid file.

**Secondary confirmed issue:** uploadRide was typed as `Promise<Ride>` but the endpoint returns `{ride_id, status}`. On a non-ok response, it threw `new Error("uploadRide failed: 422")` with no reason, hiding the backend's specific detail message from the user.

## Task 1: Accurate Duration Computation (api/routes/rides.py)

Added `last_record_ts` tracking alongside the existing `first_record_ts`. After iterating all frames, duration is now computed as:

```
if first_record_ts and last_record_ts and last_record_ts > first_record_ts:
    duration_secs = int((last_record_ts - first_record_ts).total_seconds()) + 1
else:
    duration_secs = len(power_samples)
```

The `+ 1` accounts for the last second of data (a frame timestamped at T=899 represents the 900th second of activity). This correctly handles:
- Garmin auto-pause / smart recording (fewer records than seconds)
- Wahoo ELEMNT variable-rate recording
- Zwift files with any non-1Hz cadence

All security guards remain intact: 25MB cap (T-03-11), 10-minute duration gate (T-03-12, now accurate), filename sanitization (T-03-13), user-scoped inserts (T-03-14).

## Task 2: Fix uploadRide Response Type and Error Detail (frontend/src/lib/api.ts)

Added `UploadRideResponse` interface:
```typescript
export interface UploadRideResponse {
  ride_id: string
  status: string
}
```

Changed `uploadRide` to return `Promise<UploadRideResponse>` and to surface backend error detail on non-ok responses:
- Attempts `res.json()` to parse the error body
- Reads `body?.detail?.detail` (the human-readable string from backend)
- Throws that message if present; falls back to `uploadRide failed: ${res.status}` only when absent

FitUploadZone's `toast.error(\`Upload failed. ${message}. Try again.\`)` now shows the precise reason (e.g. "File too short or unreadable (minimum 10 minutes of data required)") instead of a bare "422".

Updated `history.test.tsx` to mock `uploadRide` with an `UploadRideResponse` shape and import `UploadRideResponse` type.

## Verification

- `api/routes/rides.py`: syntax clean, 8/8 test_rides.py tests pass
- `frontend/src/lib/api.ts`: `ride_id` and `uploadRide` present, `npm run build` shows no new errors
- All 6 history.test.tsx tests pass including the `uploadRide` mock test
- 11 pre-existing failures in session.test.tsx / useSessionTimer.test.ts / zwo-modal.test.tsx unrelated to this plan

## Deviations from Plan

None. Plan executed exactly as written. The diagnosis confirmed the timestamp-duration fix was the right approach; the sample_zwift.fit fixture happens to be 1Hz so both methods agree on that file, but real Zwift exports at smart-recording rates would have been undercounted.

## Self-Check: PASSED

- api/routes/rides.py modified: FOUND
- frontend/src/lib/api.ts modified: FOUND
- Commit 3c2b9a0: FOUND (rides.py timestamp fix)
- Commit 393a928: FOUND (api.ts uploadRide fix)
