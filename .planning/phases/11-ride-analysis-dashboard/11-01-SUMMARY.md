---
phase: 11-ride-analysis-dashboard
plan: 01
subsystem: api
tags: [fitdecode, fastapi, python, time-series, tdd]

# Dependency graph
requires:
  - phase: 01-sports-science-foundation
    provides: ToolResult pattern, sports_science calculation conventions
  - phase: 06-core-loop-persistence
    provides: rides table + raw_fit_path Storage persistence
provides:
  - "parse_fit_stream(file_bytes) -> Optional[dict]: index-aligned per-second series + lap_bounds"
  - "backend/routes/_stream_utils.py: detect_presence(), downsample() (stdlib-only)"
  - "tests/api/test_rides_stream.py: parser/util test coverage (9 tests)"
affects: [11-02, 11-03, 11-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Aligned-row FIT parsing: one dict per FIT record with identical keys across all rows, None for gaps -- never skip an index (contrasts with parse_fit_file's per-channel append-only-when-present pattern)"
    - "Elapsed seconds computed from (record.timestamp - start_time).total_seconds(), never array index"
    - "enhanced_altitude/enhanced_speed read first, fall back to legacy altitude/speed field names"

key-files:
  created:
    - backend/routes/_stream_utils.py
    - tests/api/test_rides_stream.py
  modified:
    - backend/routes/rides.py

key-decisions:
  - "parse_fit_stream built as a genuinely new sibling function (not reusing parse_fit_file's alignment logic), per RESEARCH.md Pitfall 1 -- avoids misaligned per-channel arrays"
  - "lap_bounds computed directly from each lap frame's own start_time field (verified present via direct fitdecode inspection of both fixtures), relative to the same ride start_time used for series[].t"

requirements-completed: [RIDE-01, RIDE-02, RIDE-03, RIDE-12]

coverage:
  - id: D1
    description: "parse_fit_stream returns index-aligned per-second channel arrays (power, heart_rate, cadence, speed, altitude, distance) where every row has identical keys and every channel array has the same length"
    requirement: "RIDE-01"
    verification:
      - kind: unit
        ref: "tests/api/test_rides_stream.py#test_parse_stream_channels_aligned"
        status: pass
    human_judgment: false
  - id: D2
    description: "Channel presence rule (D-11-03): 0/1 distinct non-null values reports absent, 2+ reports present; verified on both real fixtures (Zwift altitude absent, hilly altitude present)"
    requirement: "RIDE-02"
    verification:
      - kind: unit
        ref: "tests/api/test_rides_stream.py#test_detect_presence_rules"
        status: pass
      - kind: unit
        ref: "tests/api/test_rides_stream.py#test_parse_stream_zwift_altitude_absent"
        status: pass
      - kind: unit
        ref: "tests/api/test_rides_stream.py#test_parse_stream_hilly_altitude_present"
        status: pass
    human_judgment: false
  - id: D3
    description: "downsample never returns more than 4000 points, preserves the first record, and returns [] for an empty input"
    requirement: "RIDE-03"
    verification:
      - kind: unit
        ref: "tests/api/test_rides_stream.py#test_downsample_caps_at_4000"
        status: pass
      - kind: unit
        ref: "tests/api/test_rides_stream.py#test_downsample_preserves_first_and_stride"
        status: pass
      - kind: unit
        ref: "tests/api/test_rides_stream.py#test_downsample_default_interval_1800_rows"
        status: pass
    human_judgment: false
  - id: D4
    description: "lap_bounds contains exactly 6 elapsed-seconds boundaries for both zwift_ride_30min.fit and hilly_ride_30min.fit fixtures; corrupt bytes return None"
    requirement: "RIDE-12"
    verification:
      - kind: unit
        ref: "tests/api/test_rides_stream.py#test_parse_stream_lap_bounds_six"
        status: pass
      - kind: unit
        ref: "tests/api/test_rides_stream.py#test_parse_stream_corrupt_returns_none"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-09
status: complete
---

# Phase 11 Plan 01: Ride Stream Backend Data Layer Summary

**New `parse_fit_stream` sibling parser + stdlib-only `_stream_utils.py` (detect_presence, downsample) produce index-aligned per-second FIT arrays and a 6-boundary lap list, driven test-first against the two placed real fixtures.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-09T16:31:00Z
- **Completed:** 2026-07-09T16:43:18Z
- **Tasks:** 2 (TDD RED + GREEN)
- **Files modified:** 3 (1 new util module, 1 new test file, 1 additive edit to rides.py)

## Accomplishments

- `backend/routes/_stream_utils.py` created: `detect_presence()` (D-11-03: >1 distinct non-null value = present) and `downsample()` (D-11-04: stride-sample, cap 4000 points, always preserves index 0) -- both stdlib-only, zero framework coupling.
- `parse_fit_stream()` added to `backend/routes/rides.py` beside the existing `parse_fit_file`: builds one aligned row per FIT `record` frame keyed to real elapsed seconds (`(record.timestamp - start_time).total_seconds()`, not array index), inserts `None` for any missing channel value, and reads `enhanced_altitude`/`enhanced_speed` before falling back to legacy `altitude`/`speed`.
- `lap_bounds` computed directly from each `lap` frame's own `start_time` field (confirmed present on both fixtures via live fitdecode inspection), relative to the same ride `start_time` used for the series -- avoids the lap/series time-origin drift flagged in RESEARCH.md Pitfall 2.
- `tests/api/test_rides_stream.py` written test-first (RED confirmed via `ModuleNotFoundError` before implementation existed), then GREEN: all 9 tests pass against the real `zwift_ride_30min.fit` (altitude absent, 6 laps) and `hilly_ride_30min.fit` (altitude present, 6 laps) fixtures.
- Verified `parse_fit_file` is byte-for-byte unchanged (`git diff` on `rides.py` is a pure 125-line insertion, zero deletions) and the upload pipeline's existing tests (`tests/api/test_rides.py`, 14 tests) plus the full sports-science suite (`tests/sports_science`, 98 tests) still pass with zero regressions.

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for _stream_utils + parse_fit_stream** - `95b137b` (test)
2. **Task 2 (GREEN): Implement _stream_utils.py and parse_fit_stream** - `21a32ea` (feat)

_TDD plan: RED confirmed via `ModuleNotFoundError` on both new imports before GREEN implementation began._

## Files Created/Modified

- `backend/routes/_stream_utils.py` - New stdlib-only module: `detect_presence(channel_values)`, `downsample(series, target_interval_secs=3, max_points=4000)`
- `backend/routes/rides.py` - Additive: `parse_fit_stream(file_bytes)` added beside `parse_fit_file`; no existing code touched
- `tests/api/test_rides_stream.py` - New file: 9 tests covering presence rules, downsample stride/cap/empty-input, aligned-series shape, per-fixture channel presence, 6-lap-boundary assertion, corrupt-bytes-returns-None

## Decisions Made

- Built `parse_fit_stream` as a genuinely new sibling function rather than adapting `parse_fit_file`'s per-channel "append only when present" logic, per RESEARCH.md Pitfall 1 -- that logic produces channel arrays of different lengths that cannot be zipped into one per-second series, which would silently misalign the future synced chart's X axis.
- Resolved `lap_bounds` from each `lap` frame's own `start_time` field (verified directly against both fixtures via `fitdecode.FitReader` inspection during implementation) rather than deriving lap timing from `total_elapsed_time` accumulation -- simpler and equally correct since the field is populated and relative to the same ride `start_time` used for the series.
- `start_time` resolution mirrors `parse_fit_file`'s existing convention: prefer the `session` frame's `start_time`, fall back to the first `record` frame's `timestamp` if session arrives after records in file order (confirmed true for both fixtures: session message is the terminal frame in FIT files, so the fallback path is what actually fires on real fixtures, and it resolves to the identical timestamp either way).

## Deviations from Plan

None - plan executed exactly as written. Task 1 produced the required RED failure (`ModuleNotFoundError` on both `backend.routes._stream_utils` and `parse_fit_stream`); Task 2 implemented both modules to GREEN with no additional fixes needed. `ruff check` was clean after one line-length wrap (108 > 100 chars, non-functional formatting only, folded into the Task 2 commit).

## Issues Encountered

None. The two fixtures behaved exactly as RESEARCH.md predicted: `zwift_ride_30min.fit` has 0 distinct altitude values (all None, since the fixture has no `altitude`/`enhanced_altitude` fields on record frames) and `hilly_ride_30min.fit` has 635+ distinct altitude values; both fixtures have exactly 6 `lap` messages at 300-second intervals, confirming RESEARCH.md's Pitfall 4 correction (6, never 7).

## User Setup Required

None - no external service configuration required. No new dependencies (fitdecode already installed and used by `parse_fit_file`).

## Next Phase Readiness

- `parse_fit_stream`, `detect_presence`, and `downsample` are ready for 11-03 (`GET /rides/{id}/stream`) to import and orchestrate behind Storage download + IDOR scoping.
- `tests/api/test_rides_stream.py` is the file 11-03 appends its endpoint-integration tests to (per the plan's `<artifacts_this_phase_produces>` note).
- No blockers. 11-02 (`time_in_hr_zones` tool) is independent of this plan (same wave, no shared files) and can proceed in parallel.

---
*Phase: 11-ride-analysis-dashboard*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: backend/routes/_stream_utils.py
- FOUND: tests/api/test_rides_stream.py
- FOUND: .planning/phases/11-ride-analysis-dashboard/11-01-SUMMARY.md
- FOUND: parse_fit_stream in backend/routes/rides.py
- FOUND: commit 95b137b (test RED)
- FOUND: commit 21a32ea (feat GREEN)
- FOUND: commit 2d69e00 (docs summary)
