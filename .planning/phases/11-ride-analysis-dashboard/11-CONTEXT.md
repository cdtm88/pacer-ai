---
phase: 11-ride-analysis-dashboard
title: Ride Analysis Dashboard
depends_on: [01-sports-science-foundation, 06-core-loop-persistence]
provides:
  - GET /api/rides/{id}/stream (parse-on-demand time series)
  - time_in_hr_zones tool (ToolResult, reuses calculate_hr_zones)
  - RideChart Recharts component (dynamic channels, syncId, lap lines)
  - AnalysisScreen at /rides/:rideId and /analysis
  - Analysis nav tab (BottomTabBar + DesktopSidebar)
requirements: [RIDE-01, RIDE-02, RIDE-03, RIDE-04, RIDE-05, RIDE-06, RIDE-07, RIDE-08, RIDE-09, RIDE-10, RIDE-11, RIDE-12]
decisions: [D-11-01, D-11-02, D-11-03, D-11-04, D-11-05, D-11-06, D-11-07]
threats: [T-11-01, T-11-02, T-11-03]
trust_model: TRUST-01 enforced — all zone maths server-side in ToolResult
no_migration: true
no_new_env: true
waves:
  0: [11-01, 11-02]   # backend data layer
  1: [11-03]          # stream endpoint
  2: [11-04, 11-05, 11-06]  # frontend
  3: [11-07]          # fixtures + tests
source: docs/phase-11-ride-analysis-roadmap.html (author-supplied PRD)
---

# Phase 11 — Ride Analysis Dashboard

## One-line intent

Add a Ride Analysis tab that renders a per-second visualisation of any uploaded
ride (power, HR, cadence, speed, elevation) with lap markers, a synced hover
readout, and a time-in-HR-zone breakdown. Charts appear only for channels
present in the file, so indoor Zwift rides with no elevation or GPS render
cleanly.

## PROJECT identity

- **Phase:** `11-ride-analysis-dashboard`
- **Depends on:** Phase 1 (sports-science tools: `calculate_hr_zones`), Phase 6
  (rides + Storage persistence), the existing `rides.py` FIT parse pipeline.
- **Stack touched:** FastAPI route, one new sports-science tool, React 19 +
  Recharts, React Router, TanStack Query, new nav tab.
- **New user setup:** None. No new env vars, no new services, no migration.

## Trust-model constraint (TRUST-01) — non-negotiable

Every physiological number (HR-zone boundaries, time-in-zone percentages) MUST
come from a deterministic tool in `backend/sports_science/` that returns a
`ToolResult` with a named methodology. No zone boundary or zone percentage may
be computed in TypeScript. The frontend renders values the backend already
calculated. Any zone maths in JS is a defect regardless of correctness.

## Architecture decisions (locked)

| ID | Decision | Rationale |
|----|----------|-----------|
| D-11-01 | Serve ride time series via parse-on-demand: a new `GET /api/rides/{id}/stream` re-downloads the stored `.fit` from Supabase Storage and re-parses it. No time-series persistence, no migration. | A 30-min ride parses in ~10ms. Persisting arrays adds a table, a write path, and storage cost for zero user-visible benefit at current ride lengths. |
| D-11-02 | Time-in-zone is computed by a new Python tool `time_in_hr_zones`, reusing `calculate_hr_zones` for boundaries. Returned as part of the stream payload. | TRUST-01. One definition of a zone in the codebase. |
| D-11-03 | Channel presence rule: a channel is "present" iff it has more than one distinct non-null value. Absent channels are omitted from the payload and get no chart, no card, no lap-table column. | This hides elevation and GPS on indoor Zwift files. Real sensors vary; a flat channel means no sensor. |
| D-11-04 | Server-side downsample to a target of ~1 point / 3s, capped so no payload exceeds ~4000 points. | Recharts on mobile Safari (the PWA target) degrades past ~4k points. A 3h ride stays under the cap. |
| D-11-05 | New top-level route `/rides/:rideId` under `AppLayout`; the History tab's rows link into it. A dedicated Analysis tab is added showing the most recent ride by default. | Keeps History as the list; Analysis is the deep-dive. Matches the existing tab pattern in `BottomTabBar` / `DesktopSidebar`. |
| D-11-06 | Recharts `syncId` provides cross-chart hover sync. No custom crosshair code. | Built-in. Deletes the fiddliest part of the prototype. |
| D-11-07 | The zone-model selector and power-smoothing toggle from the prototype are OUT of scope. | The selector conflicts with single-source-of-truth (D-11-02). Smoothing is a later nice-to-have. |

## Threats / mitigations

| ID | Threat | Mitigation |
|----|--------|------------|
| T-11-01 | Cross-user ride access via `/stream` | Query scoped to `user_id` from JWT sub (existing T-04-03 pattern). Return 404 if the ride isn't the caller's. |
| T-11-02 | Storage download of a missing/oversized object | 404 if `raw_fit_path` is null. Reuse the 25 MB cap already enforced at upload; no re-check needed since only already-accepted files are stored. |
| T-11-03 | Corrupt stored file crashes the stream parse | fitdecode `ErrorHandling.WARN` (same as upload). On unreadable file return 422 with structured detail. |

## Requirements

| REQ | Statement | Layer |
|-----|-----------|-------|
| RIDE-01 | A sibling parser extracts full per-second arrays for power, HR, cadence, speed, altitude, distance, plus lap-message boundaries, from raw FIT bytes. | BE |
| RIDE-02 | Channel presence is detected per D-11-03 and returned as a `channels` map. | BE |
| RIDE-03 | Series is downsampled per D-11-04 before serialisation. | BE |
| RIDE-04 | `time_in_hr_zones(hr_array, lthr)` returns a `ToolResult` of per-zone seconds and percentages, reusing `calculate_hr_zones`. | BE |
| RIDE-05 | `GET /api/rides/{id}/stream` returns the series, channels, laps, and HR-zone distribution, scoped to the caller. | BE |
| RIDE-06 | `RideStream` type and `getRideStream(id)` fetcher added to `api.ts`. | FE |
| RIDE-07 | `RideChart` component renders one chart per present channel using Recharts, shared `syncId`, lap `ReferenceLine`s, and CSS-var strokes. | FE |
| RIDE-08 | A synced readout row shows time (`Mm SSs`), lap number, and each present channel's value at the hovered point. | FE |
| RIDE-09 | A time-in-zone bar + row list renders from the backend distribution, using `--color-zone-*` tokens. Absent if HR is not present. | FE |
| RIDE-10 | New `AnalysisScreen` at route `/rides/:rideId` and a default `/analysis` (latest ride); new nav tab in both `BottomTabBar` and `DesktopSidebar`. | FE |
| RIDE-11 | History `RideRow` links each row to `/rides/:id`. | FE |
| RIDE-12 | Fixtures + tests: both `.fit` files land in `tests/fixtures/`; backend tests assert zone maths and no-elevation channel detection; a frontend test asserts the elevation chart is absent when `channels.altitude` is false. | BE + FE |

## Roadmap: waves and plans

### Wave 0 — Backend data layer
Independently testable with the two fixtures; no frontend yet.

- **11-01 — sibling parser + presence + downsample** (BE). RIDE-01, RIDE-02, RIDE-03.
  Files: `backend/routes/rides.py` (add `parse_fit_stream` beside `parse_fit_file`),
  `backend/routes/_stream_utils.py` (new: `detect_presence`, `downsample`).
  Keep per-sample speed/altitude/distance alongside power/HR/cadence; capture `lap`
  messages into `lap_bounds` (seconds from ride start). Do NOT modify
  `parse_fit_file` or the upload path (additive). Presence:
  `len({v for v in arr if v is not None}) > 1`.
- **11-02 — `time_in_hr_zones` tool** (BE). RIDE-04.
  Files: `backend/sports_science/zones.py`, `tests/sports_science/test_zones.py`.
  Reuses `calculate_hr_zones`; returns a `ToolResult` of per-zone seconds and
  percentages with a named methodology.

### Wave 1 — Stream endpoint
- **11-03 — `GET /rides/{id}/stream`** (BE). RIDE-05. Threats T-11-01, T-11-02, T-11-03.
  Files: `backend/routes/rides.py`. Scope the rides query to `user_id`; 404 on
  missing `raw_fit_path`; download from Storage; `parse_fit_stream` off-thread;
  422 on parse failure; downsample; compute `hr_zone_distribution` only when
  heart_rate is present; resolve LTHR via the existing profile /
  `estimate_lthr_from_max_hr` path (do not invent one in the route).

### Wave 2 — Frontend
- **11-04 — API type + fetcher** (FE). RIDE-06. Files: `frontend/src/lib/api.ts`.
  `RideStream` interface + `getRideStream(rideId)`.
- **11-05 — RideChart component** (FE). RIDE-07, RIDE-08, RIDE-09.
  Files: `frontend/src/components/rides/RideChart.tsx` (new). A `CHART_CONFIG`
  array, one chart per present channel; shared `syncId="ride"`; X axis in seconds
  (`Nm` ticks, `Mm SSs` tooltip); lap `ReferenceLine`s from `stream.laps`; strokes
  from CSS-var tokens; `isAnimationActive={false}`. Time-in-zone bar + rows from
  `stream.hr_zone_distribution` using `--color-zone-*`; render nothing if null.
- **11-06 — Analysis screen, route, nav tab** (FE). RIDE-10, RIDE-11.
  Files: `frontend/src/screens/AnalysisScreen.tsx` (new), `router.tsx`,
  `BottomTabBar.tsx`, `DesktopSidebar.tsx`, `RideRow.tsx`. `AnalysisScreen` reads
  `:rideId` (falls back to latest ride id); TanStack Query on
  `['ride-stream', rideId]` with `staleTime: Infinity`. Add routes
  `rides/:rideId` and `analysis`; add an Analysis tab (lucide `Activity`) to both
  nav components; link each `RideRow` to `/rides/:id`.

### Wave 3 — Verification
- **11-07 — fixtures + tests** (BE + FE). RIDE-12.
  Files: `tests/fixtures/{hilly_ride_30min,zwift_ride_30min}.fit` (already placed),
  `tests/sports_science/test_zones.py`, `tests/api/test_rides_stream.py` (new),
  `frontend/src/tests/rideChart.test.tsx` (new). Backend: `time_in_hr_zones` with
  a known HR array and hand-checked percentages; stream endpoint against
  `zwift_ride_30min.fit` asserts `channels["altitude"] is False` and
  `len(laps) == 7`; against `hilly_ride_30min.fit` asserts `channels["altitude"]
  is True`. Frontend: render `RideChart` with `channels.altitude=false`, assert no
  elevation chart in the DOM.

## Explicitly out of scope

- Time-series persistence (a `ride_streams` table). Revisit only if
  parse-on-demand latency becomes a problem.
- Zone-model selector (%max vs LTHR) and power-smoothing toggle (D-11-07).
- A local file-input loader. The tab reads from the DB via the stream endpoint;
  upload stays in History.

## Fixtures (placed)

- `tests/fixtures/zwift_ride_30min.fit` — indoor Zwift ride, no elevation/GPS
  (drives the absent-channel path, `channels["altitude"] is False`, 6 laps).
- `tests/fixtures/hilly_ride_30min.fit` — outdoor ride with elevation
  (`channels["altitude"] is True`).

## Reference

Author-supplied PRD copied to `docs/phase-11-ride-analysis-roadmap.html`.
