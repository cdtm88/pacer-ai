---
phase: 11-ride-analysis-dashboard
plan: 04
subsystem: frontend
tags: [typescript, api-client, fetch, contract]

# Dependency graph
requires:
  - phase: 11-ride-analysis-dashboard
    provides: "GET /rides/{id}/stream: parse-on-demand endpoint returning series, channels, laps, hr_zone_distribution scoped to the caller (11-03)"
provides:
  - "getRideStream(rideId): Promise<RideStream> typed fetcher + RideStream/RideStreamPoint/RideZoneDistribution interfaces in frontend/src/lib/api.ts"
affects: [11-05, 11-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "getRideStream mirrors getRides' apiFetch + !res.ok throw + res.json() as Promise<T> shape exactly -- no new fetch pattern introduced"

key-files:
  created: []
  modified:
    - frontend/src/lib/api.ts

key-decisions:
  - "Interfaces placed immediately before PmcEntry (after Ride, before the next existing interface) to keep declaration order matching the plan's 'near the other exported interfaces, after Ride' instruction; fetcher placed immediately before getLatestPmc, directly after getRides for adjacency with the sibling endpoint"
  - "No adapter/mapping layer added -- field names (series, channels, laps, hr_zone_distribution) and nested shapes (RideStreamPoint: t/power/heart_rate/cadence/speed/altitude/distance; RideZoneDistribution: zone/name/seconds/pct) were verified byte-for-byte against backend/routes/rides.py::get_ride_stream and backend/sports_science/zones.py::time_in_hr_zones before writing the types"

requirements-completed: [RIDE-06]

coverage:
  - id: D1
    description: "getRideStream(rideId) fetcher exists, calls apiFetch('/api/rides/{id}/stream'), and returns RideStream"
    requirement: "RIDE-06"
    verification:
      - kind: static
        ref: "frontend/src/lib/api.ts::getRideStream"
        status: pass
    human_judgment: false
  - id: D2
    description: "RideStream/RideStreamPoint/RideZoneDistribution types mirror the backend payload exactly (verified against get_ride_stream's return dict and time_in_hr_zones' row shape)"
    requirement: "RIDE-06"
    verification:
      - kind: static
        ref: "frontend/src/lib/api.ts interfaces vs backend/routes/rides.py:882-911, backend/sports_science/zones.py:81-89"
        status: pass
    human_judgment: false
  - id: D3
    description: "Project typechecks and lints clean with the new code"
    requirement: "RIDE-06"
    verification:
      - kind: automated
        ref: "npx tsc --noEmit (TYPECHECK-OK, exit 0)"
        status: pass
      - kind: automated
        ref: "npx eslint src/lib/api.ts (exit 0, no output)"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-07-09
status: complete
---

# Phase 11 Plan 04: Ride Stream Frontend Contract Summary

**Added `RideStream`/`RideStreamPoint`/`RideZoneDistribution` TypeScript interfaces and a `getRideStream(rideId)` fetcher to `frontend/src/lib/api.ts`, mirroring 11-03's `/rides/{id}/stream` backend response byte-for-byte with zero adapter logic.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-09T16:50:00Z (approx)
- **Completed:** 2026-07-09T16:56:27Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Added three interfaces (`RideStreamPoint`, `RideZoneDistribution`, `RideStream`) to `frontend/src/lib/api.ts`, placed after the `Ride` interface per the plan's placement instruction.
- Added `export async function getRideStream(rideId: string): Promise<RideStream>` modeled directly on the existing `getRides()` pattern: calls `apiFetch(\`/api/rides/${rideId}/stream\`)`, throws `Error(\`getRideStream failed: ${res.status}\`)` on `!res.ok`, returns `res.json() as Promise<RideStream>`.
- Before writing the types, read `backend/routes/rides.py::get_ride_stream` (lines 801-911) and `backend/sports_science/zones.py::time_in_hr_zones` (lines 56-96) directly to confirm the exact response shape: `series` row keys (`t`, `power`, `heart_rate`, `cadence`, `speed`, `altitude`, `distance`), `channels` as a plain dict over the six channel keys, `laps` as `list[int]`, and `hr_zone_distribution` rows as `{zone, name, seconds, pct}` — all match the plan's artifact spec verbatim, so no correction was needed.
- No new auth code added; reuses the existing `apiFetch` wrapper (Supabase JWT injection) exactly as every other GET fetcher in the file does.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add RideStream types + getRideStream fetcher** - `9ee66fc` (feat)

## Files Created/Modified

- `frontend/src/lib/api.ts` - Additive only: three new interfaces inserted before `PmcEntry`, one new fetcher inserted before `getLatestPmc` (directly after `getRides`). No existing export modified.

## Decisions Made

- Interface and fetcher placement chosen for adjacency with the closest existing analog (`Ride`/`getRides`) rather than strictly "end of file," per the plan's read_first guidance to match `getRides`' shape/placement.
- Verified the backend contract directly from source (not just from 11-03's SUMMARY prose) before typing the interfaces, since a byte-exact match was an explicit acceptance criterion.

## Deviations from Plan

None - plan executed exactly as written. All four artifacts (three interfaces + one fetcher) match the plan's `<artifacts_this_phase_produces>` spec exactly, including the `Record<'power'|'heart_rate'|'cadence'|'speed'|'altitude'|'distance', boolean>` channel type and the `RideZoneDistribution[] | null` nullability on `hr_zone_distribution`.

## Issues Encountered

- The worktree has no local `frontend/node_modules` (only the main checkout does). Ran `npx tsc --noEmit` via the main checkout's installed `tsc` binary (`/Users/christianmoore/ai/pacer-ai/frontend/node_modules/.bin/tsc`) against the worktree's `frontend/` directory — passed with zero errors. For `eslint` (whose flat config resolves plugins relative to CWD and failed with `ERR_MODULE_NOT_FOUND` when pointed at the worktree file from outside it), temporarily symlinked `frontend/node_modules` to the main checkout's `node_modules`, ran `eslint src/lib/api.ts` (exit 0, clean), then removed the symlink immediately after — gitignored, not committed, no trace left in the worktree.

## User Setup Required

None - no external service configuration required. No new dependencies.

## Next Phase Readiness

- `getRideStream()` and the `RideStream`/`RideStreamPoint`/`RideZoneDistribution` types are the typed seam 11-05 (chart component) and 11-06 (Analysis screen) consume directly — no contract renegotiation needed, response shape was verified against the live backend implementation, not just documentation.
- No blockers.

---
*Phase: 11-ride-analysis-dashboard*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: frontend/src/lib/api.ts
- FOUND: getRideStream in frontend/src/lib/api.ts
- FOUND: commit 9ee66fc (feat)
