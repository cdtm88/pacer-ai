---
phase: 12-athletic-redesign
plan: 06
subsystem: ui
tags: [react, recharts, zone-colors, design-system]

# Dependency graph
requires:
  - phase: 12-athletic-redesign (12-01, 12-02)
    provides: consolidated lib/zones.ts single-source zone map (ZONE_META, zoneColor, ZoneKey)
provides:
  - WeeklyLoadChart neutral-gray history bars with a brand-blue current-week highlight (replaces jump-detection amber coloring)
  - RideRow paired planned/actual horizontal bars + ComplianceChip (replaces HTML table)
  - AgendaScreen mini zone-colored bars (24x4px) sourced from lib/zones (local ZONE_VAR duplicate removed)
affects: [progress, history, agenda]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Zone color and duration bars (24x4px / 8px, 2-4px radius) as the single presentation pattern for zone-intensity encoding across Today hub, SessionCard, and Agenda rows"
    - "Paired horizontal bars (track + filled bar) as the standard planned-vs-actual comparison pattern, replacing ad-hoc tables"

key-files:
  created: []
  modified:
    - frontend/src/components/progress/WeeklyLoadChart.tsx
    - frontend/src/components/history/RideRow.tsx
    - frontend/src/screens/AgendaScreen.tsx

key-decisions:
  - "WeeklyLoadChart's current-week detection reuses the already-imported weekStartOf/weekKey helpers instead of adding new date logic"
  - "RideRow's Actual bar visual width is capped at min(150, compliance_pct)% so over-target rides (compliance > 150%) don't blow out the row layout"
  - "AgendaScreen imports ZONE_META/zoneColor/ZoneKey from @/lib/zones directly (not via the format.ts re-export) since sessionTypeLabel is the only symbol format.ts uniquely owns"

patterns-established:
  - "Mini zone bar (24x4px, 2px radius, zoneColor() fill) as the canonical compact zone indicator for list rows"

requirements-completed: [D-9, D-8, D-7]

coverage:
  - id: D1
    description: "WeeklyLoadChart replaces jump-detection amber coloring with neutral-gray history bars and a brand-blue current-ISO-week highlight"
    requirement: "D-9"
    verification:
      - kind: unit
        ref: "npx tsc --noEmit (frontend) — clean"
        status: pass
    human_judgment: true
    rationale: "Visual color/highlight correctness on a rendered chart is a design judgment call not covered by an existing automated visual test"
  - id: D2
    description: "RideRow replaces the planned-vs-actual HTML table with paired horizontal bars (Planned track + Actual filled bar) plus the existing ComplianceChip"
    requirement: "D-9"
    verification:
      - kind: unit
        ref: "src/tests/history.test.tsx — 10 passed"
      - kind: unit
        ref: "npx tsc --noEmit (frontend) — clean"
        status: pass
    human_judgment: false
  - id: D3
    description: "AgendaScreen's local ZONE_VAR/isValidZone duplicate is removed; row zone indicators become 24x4px mini bars sourced from @/lib/zones, matching the Today-hub treatment"
    requirement: "D-8"
    verification:
      - kind: unit
        ref: "npm test -- --run (frontend full suite) — 147 passed"
      - kind: unit
        ref: "npx tsc --noEmit (frontend) — clean"
        status: pass
    human_judgment: true
    rationale: "Visual sizing/alignment of the new mini zone bar within the Agenda row layout is a design judgment call, not asserted by an existing snapshot/visual test"

duration: 15min
completed: 2026-07-09
status: complete
---

# Phase 12 Plan 06: Progress + Agenda Polish Summary

**WeeklyLoadChart, RideRow, and AgendaScreen re-skinned onto the consolidated `lib/zones` zone-color system, replacing an HTML table and two off-pattern coloring schemes with bar-based data encoding.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments
- `WeeklyLoadChart.tsx`: removed `JUMP_FACTOR` jump-detection amber coloring; bars are now neutral gray (`var(--color-ink-3)`) except the current ISO week, which renders in `var(--color-brand)`. Reused the already-imported `weekStartOf`/`weekKey` helpers, no new imports.
- `RideRow.tsx`: replaced the entire `<table>`/`<thead>`/`<tbody>` planned-vs-actual block with two stacked 8px bars (Planned track at `--color-line`, Actual bar at `min(150, compliance_pct)%` width in `--color-good`/`--color-warn` per the existing >=90 threshold) plus the existing in-file `ComplianceChip`.
- `AgendaScreen.tsx`: deleted the local `ZONE_VAR`/`isValidZone` duplicate zone map; now imports `ZONE_META`, `zoneColor`, and `ZoneKey` from `@/lib/zones` (kept `sessionTypeLabel` from `@/lib/format`). Replaced the 12px round zone dot with a 24x4px, 2px-radius zone-colored bar matching the Today-hub/SessionCard treatment.

## Task Commits

Each task was committed atomically:

1. **Task 1: WeeklyLoadChart two-tone current-week highlight (D-9)** - `6b474b1` (feat)
2. **Task 2: RideRow paired-bar planned/actual block (D-9)** - `f5e7763` (feat)
3. **Task 3: AgendaScreen mini zone bars + zone-map dedup (D-9, D-8)** - `660a53e` (feat)

_Note: no separate plan-metadata commit — this SUMMARY is committed by the worktree executor per parallel-execution protocol; the orchestrator handles STATE.md/ROADMAP.md after merge._

## Files Created/Modified
- `frontend/src/components/progress/WeeklyLoadChart.tsx` - Two-tone current-week highlight replacing jump-detection coloring
- `frontend/src/components/history/RideRow.tsx` - Paired planned/actual bars + ComplianceChip replacing HTML table
- `frontend/src/screens/AgendaScreen.tsx` - Mini zone bars sourced from `@/lib/zones`, local zone-map duplicate removed

## Decisions Made
- Reused `weekStartOf`/`weekKey` (already imported in `WeeklyLoadChart.tsx`) to compute the current-week key rather than introducing new date-comparison logic.
- Capped `RideRow`'s Actual bar visual width at `min(150, compliance_pct)%` per plan spec, so an over-target ride's compliance percentage doesn't visually overflow the row.
- Imported `ZONE_META`/`zoneColor`/`ZoneKey` in `AgendaScreen.tsx` directly from `@/lib/zones` rather than through `@/lib/format`'s re-export, since `sessionTypeLabel` is the only format.ts-unique symbol still needed there.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

The worktree had no `node_modules` installed (fresh worktree checkout). Ran `npm install` in `frontend/` before verification could proceed (`tsc`/`vitest` require installed deps) — a standard worktree-setup step, not a plan deviation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three D-9/D-8/D-7-slice surfaces (WeeklyLoadChart, RideRow, AgendaScreen) are now on the single `lib/zones` zone-color source; no remaining local zone-map duplicates found in these files.
- `npx tsc --noEmit` clean; `npm test -- --run` full suite green (147/147); `npx vitest run src/tests/history.test.tsx` green (10/10).
- No blockers for downstream phase-12 waves depending on this plan.

---
*Phase: 12-athletic-redesign*
*Completed: 2026-07-09*
