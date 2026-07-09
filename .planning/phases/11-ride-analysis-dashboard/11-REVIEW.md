---
phase: 11-ride-analysis-dashboard
reviewed: 2026-07-09T00:00:00Z
depth: standard
files_reviewed: 15
files_reviewed_list:
  - backend/routes/_stream_utils.py
  - backend/routes/rides.py
  - backend/sports_science/zones.py
  - frontend/src/components/AppLayout.tsx
  - frontend/src/components/history/RideRow.tsx
  - frontend/src/components/nav/BottomTabBar.tsx
  - frontend/src/components/nav/DesktopSidebar.tsx
  - frontend/src/components/rides/RideChart.tsx
  - frontend/src/lib/api.ts
  - frontend/src/router.tsx
  - frontend/src/screens/AnalysisScreen.tsx
  - frontend/src/tests/history.test.tsx
  - frontend/src/tests/rideChart.test.tsx
  - tests/api/test_rides_stream.py
  - tests/sports_science/test_zones.py
findings:
  critical: 0
  warning: 5
  info: 1
  total: 6
status: issues_found
---

# Phase 11: Code Review Report

**Reviewed:** 2026-07-09T00:00:00Z
**Depth:** standard
**Files Reviewed:** 15
**Status:** issues_found

## Summary

Reviewed the ride-analysis-dashboard diff (`backend/routes/rides.py::parse_fit_stream` + `GET /rides/{id}/stream`, `backend/sports_science/zones.py::time_in_hr_zones`, `backend/routes/_stream_utils.py`, and the new `AnalysisScreen`/`RideChart` frontend pair plus nav updates) against `982c2228a11de9dbb55ae8dc34c02be5058bd821`. The IDOR/UUID/404/422 security controls on `GET /rides/{id}/stream` are correctly implemented and well covered by tests, and the TRUST-01 boundary (zone maths only in `backend/sports_science/zones.py`) is respected throughout. No critical/security defects found in this diff.

Five real correctness/UX bugs were found, all in the newly-added code paths, none of which are covered by the new test suite: a stale-state bug in `RideChart` when the `stream` prop changes without a remount, a silent blank-screen error path in `AnalysisScreen`, a navigation-highlight inconsistency between the new `/rides/:rideId` route and the tab bar components, and two edge-case data-integrity gaps in `parse_fit_stream` (dropped lap boundaries, inconsistent time axis) that only manifest on malformed/unusual FIT files.

## Warnings

### WR-01: RideChart's synced readout row shows stale data after the `stream` prop changes without a remount

**File:** `frontend/src/components/rides/RideChart.tsx:108`
**Issue:** `hovered` is initialized once from `stream.series[0] ?? EMPTY_POINT` via `useState`'s lazy initial value. Because `RideChart` is rendered unconditionally inside `AnalysisScreen` (no `key` tied to `rideId`), React does not remount it when `stream` changes — only re-renders it with new props. This is reachable today without any special navigation trick: a user sitting on `/analysis` (which resolves to "most recent ride") who uploads a new ride will have `ridesQuery` invalidated/refetched, `rideId` recompute to the new ride's id, and `streamQuery` fetch a fresh `stream` — but `RideChart`'s `hovered` state (and therefore the Lap badge, time, and all per-channel readout values at the top of the page) keeps displaying the *previous* ride's first data point until the user manually hovers over a chart line. This silently shows the wrong ride's numbers next to a chart that has already updated.
**Fix:**
```tsx
// Option A: force remount on ride change (simplest, matches AnalysisScreen's key data)
// In AnalysisScreen.tsx:
{streamQuery.data && <RideChart key={rideId} stream={streamQuery.data} />}

// Option B: reset hovered state inside RideChart when stream identity changes
useEffect(() => {
  setHovered(stream.series[0] ?? EMPTY_POINT)
}, [stream])
```

### WR-02: AnalysisScreen silently shows a blank page when `getRides` fails on the `/analysis` route

**File:** `frontend/src/screens/AnalysisScreen.tsx:26,41,68`
**Issue:** When visiting `/analysis` (no `routeRideId`) and `ridesQuery` (`getRides`) errors, `isLoading` becomes `false`, the "No rides yet" branch is skipped because it explicitly requires `!ridesQuery.isError`, `streamQuery` never becomes `isError` because it stays disabled (`enabled: !!rideId`, and `rideId` is `undefined` since `ridesQuery.data` is `undefined`), so execution falls through to the final `return` which renders an empty padded `<div>` with nothing inside (`{streamQuery.data && <RideChart .../>}` is falsy). The user sees a blank page with no error message and no retry affordance.
**Fix:**
```tsx
if (ridesQuery.isError) {
  return (
    <button onClick={() => ridesQuery.refetch()} /* same style as the streamQuery error button */>
      Could not load your rides. Tap to retry.
    </button>
  )
}
```

### WR-03: Bottom tab bar / desktop sidebar don't highlight "Analysis" while viewing `/rides/:rideId`

**File:** `frontend/src/components/nav/BottomTabBar.tsx:6-9`, `frontend/src/components/nav/DesktopSidebar.tsx:6-9`
**Issue:** `AppLayout.tsx` was updated to special-case the header title for `/rides/:rideId` (`pathname.startsWith('/rides/') ? 'Analysis' : ...`), but `BottomTabBar` and `DesktopSidebar` still only define a nav entry for `to: '/analysis'`. React Router's `NavLink` `isActive` matching does not treat `/rides/abc123` as nested under `/analysis` (they are sibling route patterns), so when a user taps "View analysis" from a `RideRow` (which links to `/rides/${ride.id}`), no tab/sidebar item highlights at all — the user loses their place in the primary navigation even though the header correctly says "Analysis".
**Fix:**
```tsx
// BottomTabBar.tsx / DesktopSidebar.tsx
<NavLink
  to={to}
  end={to === '/'}
  className={...}
  style={({ isActive }) => ({
    color: (isActive || (to === '/analysis' && pathname.startsWith('/rides/')))
      ? 'var(--color-brand)' : 'var(--color-ink-3)',
  })}
>
// requires importing useLocation() and reading pathname in both components,
// mirroring the check already present in AppLayout.tsx.
```

### WR-04: `parse_fit_stream` can silently drop lap boundaries when a lap frame precedes timestamp resolution

**File:** `backend/routes/rides.py:265-273`
**Issue:**
```python
if frame.name == "lap":
    lap_start = frame.get_value("start_time", fallback=None)
    if (
        lap_start is not None
        and isinstance(lap_start, datetime)
        and start_time is not None
    ):
        lap_bounds.append(int((lap_start - start_time).total_seconds()))
    continue
```
If a `lap` frame is encountered before `start_time` has been resolved (e.g., a FIT file whose `session` message is absent/appears late and whose first `lap` frame is emitted before the first `record` frame — some device firmware emits an initial zero-duration lap marker), the lap is silently dropped instead of being deferred/recorded. `lap_bounds` then under-reports the true number of laps with no log line, and the frontend's `ReferenceLine`/lap-numbering (`RideChart.tsx`'s `lapNumber` loop) would be off by however many laps were dropped, with no way for a caller to detect the discrepancy.
**Fix:** Buffer lap frames whose `start_time is None` and re-resolve them once `start_time` becomes known instead of discarding them:
```python
_pending_laps: list[datetime] = []
...
if frame.name == "lap":
    lap_start = frame.get_value("start_time", fallback=None)
    if lap_start is not None and isinstance(lap_start, datetime):
        if start_time is not None:
            lap_bounds.append(int((lap_start - start_time).total_seconds()))
        else:
            _pending_laps.append(lap_start)
    continue
# after the loop, once start_time is finally known:
lap_bounds = sorted(lap_bounds + [int((t - start_time).total_seconds()) for t in _pending_laps]) if start_time else lap_bounds
```

### WR-05: `parse_fit_stream`'s elapsed-seconds fallback mixes two incompatible time bases within one series

**File:** `backend/routes/rides.py:278-288`
**Issue:**
```python
ts = frame.get_value("timestamp", fallback=None)
...
if ts is not None and isinstance(ts, datetime) and start_time is not None:
    elapsed_secs = int((ts - start_time).total_seconds())
else:
    elapsed_secs = len(series)
```
For records with a valid timestamp, `t` is real elapsed seconds from `start_time`. For a record whose `timestamp` field is missing (fitdecode with `ErrorHandling.WARN` can produce partial/garbled records), `t` falls back to `len(series)` — the row's index. If this happens mid-file after several real-timestamp rows have already pushed the elapsed-time value well past the row count (e.g. row 50 has real `t=3000` because the device recorded at <1Hz), the very next row with a missing timestamp gets `t=51`, a large backward jump in the `t` axis. This breaks `Line` monotonicity in `RideChart` (non-monotonic X values render as a chart line that snaps backward) and corrupts the lap-boundary comparison (`hovered.t >= lapT`) for every subsequent hover in that region.
**Fix:** When a record lacks a usable timestamp, either skip appending it to `series` (since it cannot be honestly time-placed) or extrapolate from the last known elapsed time instead of the row index:
```python
if ts is not None and isinstance(ts, datetime) and start_time is not None:
    elapsed_secs = int((ts - start_time).total_seconds())
    last_elapsed_secs = elapsed_secs
elif last_elapsed_secs is not None:
    elapsed_secs = last_elapsed_secs + 1  # best-effort extrapolation, not array index
else:
    elapsed_secs = len(series)
```

## Info

### IN-01: `GET /rides/{id}/stream` always queries `profiles.lthr` even when `heart_rate` is absent

**File:** `backend/routes/rides.py:895-898`
**Issue:** The `profiles` SELECT runs unconditionally, even though its result is only used when `channels["heart_rate"]` is `True` (`hr_zone_distribution` stays `None` otherwise). This isn't a correctness bug (out of scope per project rules on performance), but it's a wasted round trip on every stream fetch for rides with no HR channel (e.g., pure indoor power-only Zwift rides).
**Fix:** Gate the query: `if channels["heart_rate"]: profile_result = await (...)` else skip and leave `lthr = None`.

---

_Reviewed: 2026-07-09T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
