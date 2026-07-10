---
phase: 11-ride-analysis-dashboard
plan: 06
subsystem: frontend
tags: [react, react-router, typescript, navigation, vitest]

# Dependency graph
requires:
  - phase: 11-ride-analysis-dashboard
    provides: "getRideStream(rideId): Promise<RideStream> typed fetcher (11-04)"
  - phase: 11-ride-analysis-dashboard
    provides: "RideChart({ stream }) component (11-05)"
provides:
  - "AnalysisScreen.tsx: /analysis (latest ride) and /rides/:rideId routes with loading/empty/three-distinct-error states, rendering RideChart"
  - "Analysis nav tab in BottomTabBar.tsx + DesktopSidebar.tsx (5th tab, Today/Agenda/Progress/Analysis/Coach)"
  - "\"View analysis\" link on each RideRow to /rides/:id"
affects: [11-07]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "AnalysisScreen resolves rideId as routeRideId ?? getRides()[0].id, no new backend endpoint (Don't Hand-Roll 'latest ride' lookup)"
    - "Error-state branching on getRideStream's Error('getRideStream failed: <status>') message string (404/422/generic), since apiFetch throws a plain Error, not a typed HTTP error class"

key-files:
  created:
    - frontend/src/screens/AnalysisScreen.tsx
  modified:
    - frontend/src/router.tsx
    - frontend/src/components/AppLayout.tsx
    - frontend/src/components/nav/BottomTabBar.tsx
    - frontend/src/components/nav/DesktopSidebar.tsx
    - frontend/src/components/history/RideRow.tsx
    - frontend/src/tests/history.test.tsx

key-decisions:
  - "AppLayout.tsx title resolver: pathname.startsWith('/rides/') ? 'Analysis' : (ROUTE_TITLES[pathname] ?? 'PacerAI') -- ROUTE_TITLES alone can't match the dynamic /rides/:rideId segment"
  - "View analysis link placed as a new block-level row directly below the existing full-width expand <button>, not wrapped alongside it in a new flex container -- preserves the button's existing width:100% style untouched while still keeping the Link outside the button (no nested interactive elements)"
  - "Error branching keys off the Error message string ('404'/'422' substring) rather than a typed exception, matching getRideStream's existing throw shape from 11-04 (no new error-type plumbing introduced)"

requirements-completed: [RIDE-10, RIDE-11]

coverage:
  - id: D1
    description: "Visiting /analysis shows the most recent ride's analysis; visiting /rides/:rideId shows that ride"
    requirement: "RIDE-10"
    verification:
      - kind: static
        ref: "frontend/src/screens/AnalysisScreen.tsx (rideId = routeRideId ?? ridesQuery.data?.[0]?.id); frontend/src/router.tsx (rides/:rideId, analysis routes)"
        status: pass
    human_judgment: false
  - id: D2
    description: "An Analysis tab appears in both the mobile bottom bar and the desktop sidebar, ordered Today, Agenda, Progress, Analysis, Coach"
    requirement: "RIDE-10"
    verification:
      - kind: static
        ref: "frontend/src/components/nav/BottomTabBar.tsx TABS array; frontend/src/components/nav/DesktopSidebar.tsx NAV_ITEMS array"
        status: pass
    human_judgment: false
  - id: D3
    description: "Each RideRow shows a 'View analysis' link to /rides/:id without changing the existing row layout"
    requirement: "RIDE-11"
    verification:
      - kind: unit
        ref: "frontend/src/tests/history.test.tsx#renders a \"View analysis\" link to /rides/:id"
        status: pass
      - kind: automated
        ref: "grep -c \"View analysis\" frontend/src/components/history/RideRow.tsx == 1"
        status: pass
    human_judgment: false
  - id: D4
    description: "AnalysisScreen shows loading, empty (no rides), and three distinct error states per the UI-SPEC"
    requirement: "RIDE-10"
    verification:
      - kind: static
        ref: "frontend/src/screens/AnalysisScreen.tsx (spinner block; 'No rides yet' empty block; 404/422/generic error blocks)"
        status: pass
    human_judgment: false
  - id: D5
    description: "The header title reads 'Analysis' on both /analysis and /rides/:rideId"
    requirement: "RIDE-10"
    verification:
      - kind: static
        ref: "frontend/src/components/AppLayout.tsx title resolver"
        status: pass
    human_judgment: false
  - id: D6
    description: "Project typechecks clean and existing nav/history tests pass with no regression"
    requirement: "RIDE-10, RIDE-11"
    verification:
      - kind: automated
        ref: "npx tsc --noEmit (TYPECHECK-OK)"
        status: pass
      - kind: automated
        ref: "npx vitest run src/tests/AppLayout.test.tsx src/tests/history.test.tsx (11/11 pass); full suite npx vitest run (140/140 pass)"
        status: pass

duration: 25min
completed: 2026-07-09
status: complete
---

# Phase 11 Plan 06: Analysis Screen, Routes, Nav Tab, RideRow Link Summary

**Wired the Analysis feature into the app: new `AnalysisScreen` at `/rides/:rideId` and default `/analysis` (latest ride via `getRides()[0]`), a fifth Analysis nav tab in both nav components, an `AppLayout` header title fallback for the dynamic route, and a "View analysis" link on each `RideRow`.**

## Performance

- **Duration:** 25 min
- **Started:** 2026-07-09T21:07:00Z (approx)
- **Completed:** 2026-07-09T21:08:45Z
- **Tasks:** 3
- **Files modified:** 7 (1 new, 6 modified)

## Accomplishments

- `AnalysisScreen.tsx`: resolves `:rideId` via `useParams` or falls back to `getRides()[0].id`; queries `['ride-stream', rideId]` with `staleTime: Infinity`, `enabled: !!rideId`; reuses the exact `AuthGate`/`FirstRunGate` spinner markup for loading; matches `ProgressScreen`'s "No rides yet" empty-state layout; renders three distinct error states (404 "This ride couldn't be found." + "Back to ride log" link, 422 "Could not read this ride file..." with no retry, generic "Could not load ride data. Tap to retry." button); renders `<RideChart stream={...} />` on success.
- `router.tsx`: added `rides/:rideId` and `analysis` routes under the existing `AppLayout` children array, both with `ErrorBoundary: RouteErrorFallback`; the `history` → `/progress` redirect and every other route were left untouched.
- `AppLayout.tsx`: added `'/analysis': 'Analysis'` to `ROUTE_TITLES`; changed the title resolver to `pathname.startsWith('/rides/') ? 'Analysis' : (ROUTE_TITLES[pathname] ?? 'PacerAI')` so the dynamic `/rides/:rideId` segment also shows "Analysis" in the header.
- `BottomTabBar.tsx` + `DesktopSidebar.tsx`: added an `Activity`-icon Analysis tab at `/analysis`, positioned between Progress and Coach (final order: Today, Agenda, Progress, Analysis, Coach). No new styling — the existing `.map` rendering and active-state treatment (dot indicator / left-border) apply automatically.
- `RideRow.tsx`: added a "View analysis" `Link` to `/rides/${ride.id}` as a separate block-level element directly below the existing full-width expand button (not nested inside it, so tapping it navigates without toggling row expansion), brand-colored, right-aligned. No existing element in the file was removed, restyled, or reordered.

## Task Commits

Each task was committed atomically:

1. **Task 1: AnalysisScreen with query, loading/empty/error states, and RideChart** - `e5050a1` (feat)
2. **Task 2: Add routes + header title mapping** - `3a2a22c` (feat)
3. **Task 3: Add Analysis nav tab (both nav components) + RideRow "View analysis" link** - `528c758` (feat)

## Files Created/Modified

- `frontend/src/screens/AnalysisScreen.tsx` - New. Exports `AnalysisScreen`.
- `frontend/src/router.tsx` - Added `AnalysisScreen` import + two new routes under `AppLayout`.
- `frontend/src/components/AppLayout.tsx` - Added `ROUTE_TITLES['/analysis']` and the `/rides/` `startsWith` title fallback.
- `frontend/src/components/nav/BottomTabBar.tsx` - Added `Activity` import + Analysis tab entry.
- `frontend/src/components/nav/DesktopSidebar.tsx` - Added `Activity` import + Analysis nav item entry.
- `frontend/src/components/history/RideRow.tsx` - Added `Link` import + "View analysis" link block.
- `frontend/src/tests/history.test.tsx` - Wrapped the three direct `RideRow` renders in `MemoryRouter` (see Deviations) + added a new test asserting the link's `href`.

## Decisions Made

- Kept the existing expand `<button>`'s `width: 100%` style completely untouched; the new "View analysis" link renders as a sibling block below it (not inside a new wrapping flex container), satisfying both "separate element, not nested inside the button" and "do not restyle any existing element."
- Error-state branching reads the `Error.message` string for `'404'`/`'422'` substrings, matching `getRideStream`'s existing `Error('getRideStream failed: <status>')` throw shape from 11-04 — no new typed-error class was introduced.
- Comment wording inside `RideRow.tsx` deliberately avoids repeating the literal phrase "View analysis" a second time, so `grep -c "View analysis" RideRow.tsx` returns exactly `1` as the plan's acceptance criterion requires.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] `history.test.tsx`'s three direct `RideRow` renders crashed after adding `<Link>`**
- **Found during:** Task 3 verification (`npx vitest run src/tests/AppLayout.test.tsx src/tests/history.test.tsx`)
- **Issue:** `RideRow.tsx` now imports and renders `<Link>` from `react-router`, which requires a router context. Three existing tests in `history.test.tsx` rendered `<RideRow ride={...} />` directly with no `MemoryRouter` wrapper, throwing `TypeError: Cannot destructure property 'basename' of 'React$1.useContext(...)' as it is null.`
- **Fix:** Wrapped all three `render(<RideRow ... />)` calls in `<MemoryRouter>`, matching the pattern already used in `AppLayout.test.tsx` and `auth.test.tsx` elsewhere in this codebase. Also added a fourth test asserting the new link's `href`.
- **Files modified:** `frontend/src/tests/history.test.tsx`
- **Commit:** `528c758`

## Issues Encountered

- The worktree has no local `frontend/node_modules` (same as 11-04/11-05). Temporarily symlinked `frontend/node_modules` → the main checkout's `node_modules` to run `tsc --noEmit` and `vitest`; removed the symlink immediately after each check (gitignored, confirmed `git status --short` clean before every commit).
- Ran the full `npx vitest run` suite (not just the plan's two named files) as an extra regression check since this plan modifies shared nav/router/layout files touched by other tests — 140/140 tests passed, no regressions beyond the one deviation above.

## User Setup Required

None — no external service configuration required. No new dependencies.

## Next Phase Readiness

- The Analysis feature is fully wired: `/analysis`, `/rides/:rideId`, the nav tab, and the `RideRow` link all exist and typecheck/test clean.
- 11-07 (verification wave) owns the manual visual smoke-check called out in the plan's `<verification>` section: 5-tab nav proportions, hover sync, absent-channel hiding.
- No blockers.

---
*Phase: 11-ride-analysis-dashboard*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: frontend/src/screens/AnalysisScreen.tsx
- FOUND: frontend/src/router.tsx
- FOUND: frontend/src/components/AppLayout.tsx
- FOUND: frontend/src/components/nav/BottomTabBar.tsx
- FOUND: frontend/src/components/nav/DesktopSidebar.tsx
- FOUND: frontend/src/components/history/RideRow.tsx
- FOUND: frontend/src/tests/history.test.tsx
- FOUND: commit e5050a1 (feat)
- FOUND: commit 3a2a22c (feat)
- FOUND: commit 528c758 (feat)
