---
phase: 12-athletic-redesign
plan: 02
subsystem: ui
tags: [typescript, react, vitest, zones, design-tokens]

# Dependency graph
requires:
  - phase: 12-athletic-redesign (plan 01)
    provides: design token CSS custom properties (--color-zone-*, --color-ink-3)
provides:
  - "frontend/src/lib/zones.ts as the single canonical zone map (ZoneKey/ZoneMeta/ZONE_META/zoneColor/zoneLabel)"
  - "nullable pctHigh (number | null) reconciled from DuringSessionScreen's local variant"
  - "drift-guard smoke test locking the zone-map contract"
affects: [12-athletic-redesign plans B-E (per-screen zone map de-duplication)]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Re-export shim: lib/format.ts re-exports zone symbols from lib/zones.ts so existing importers are unaffected by extraction"

key-files:
  created:
    - frontend/src/lib/zones.ts
    - frontend/src/tests/zones.test.ts
  modified:
    - frontend/src/lib/format.ts

key-decisions:
  - "pctHigh reconciled to number | null across the canonical map (previously format.ts had vo2 pctHigh: 120, DuringSessionScreen had vo2 pctHigh: null) — the nullable variant wins so powerTarget()'s open-ended-upper-bound branch is preserved"

patterns-established:
  - "Downstream slices (B-E) repoint their local zone-map duplicate at lib/zones.ts and delete their own copy when restyling that screen"

requirements-completed: [D-8, D-7]

coverage:
  - id: D1
    description: "lib/zones.ts is the single canonical zone map exporting ZoneKey, ZoneMeta, ZONE_META, zoneColor(), zoneLabel()"
    requirement: "D-8"
    verification:
      - kind: unit
        ref: "frontend/src/tests/zones.test.ts#lib/zones — canonical zone map"
        status: pass
    human_judgment: false
  - id: D2
    description: "lib/format.ts re-exports ZONE_META/zoneColor/zoneLabel/ZoneKey from ./zones with zero break to existing importers (SessionCard.tsx, WorkoutProfileChart.tsx)"
    requirement: "D-8"
    verification:
      - kind: unit
        ref: "cd frontend && npx tsc --noEmit (clean)"
        status: pass
      - kind: unit
        ref: "cd frontend && npm test -- --run (147 tests, 18 files, all pass)"
        status: pass
    human_judgment: false

duration: 6min
completed: 2026-07-09
status: complete
---

# Phase 12 Plan 02: Zone Map Consolidation Summary

**Extracted the canonical zone-color/label/percent-range map into `lib/zones.ts`, reconciled `pctHigh` to `number | null`, added `zoneLabel()`, and locked it with a drift-guard smoke test — `lib/format.ts` now re-exports unchanged for existing consumers.**

## Performance

- **Duration:** 6 min
- **Tasks:** 2
- **Files modified:** 3 (1 new lib file, 1 new test file, 1 modified re-export shim)

## Accomplishments
- `frontend/src/lib/zones.ts` is the single source of truth for zone metadata: `ZoneKey`, `ZoneMeta` (with `pctHigh: number | null`), `ZONE_META`, `zoneColor()`, and the new `zoneLabel()`
- `frontend/src/lib/format.ts` reduced to a re-export shim for zone symbols — `SessionCard.tsx` and `WorkoutProfileChart.tsx` imports from `@/lib/format` continue to resolve unchanged
- Drift-guard smoke test (`frontend/src/tests/zones.test.ts`) asserts all 5 zone keys, color tokens, canonical labels, percent ranges (vo2 `pctHigh: null`), and `zoneColor`/`zoneLabel` fallback behavior — closes the Wave 0 gap from `12-VALIDATION.md`

## Task Commits

Each task was committed atomically (TDD RED → GREEN):

1. **Task 1: RED - drift-guard smoke test** - `c813555` (test) — confirmed failing because `@/lib/zones` did not resolve
2. **Task 2: GREEN - create lib/zones.ts and re-export from lib/format.ts** - `54d234d` (feat) — test passes, `tsc --noEmit` clean, full suite (147/147) green

## TDD Gate Compliance

- RED gate: `c813555 test(12-02): add failing zone-map drift guard` — confirmed failing (module not found) before implementation existed.
- GREEN gate: `54d234d feat(12-02): consolidate zone map into lib/zones.ts` — test suite passes after implementation.
- REFACTOR gate: not needed; implementation was a direct extraction with no follow-up cleanup required.

## Files Created/Modified
- `frontend/src/lib/zones.ts` - Canonical `ZoneKey`/`ZoneMeta`/`ZONE_META`/`zoneColor()`/`zoneLabel()` module
- `frontend/src/lib/format.ts` - Zone symbols replaced with a re-export shim from `./zones`; `titleCase`, `ZONE_LABELS`, `sessionTypeLabel`, `classifyTsb`, `TsbClass` unchanged
- `frontend/src/tests/zones.test.ts` - Drift-guard smoke test for the zone-map contract

## Decisions Made
- Reconciled `pctHigh` to `number | null` for the canonical `vo2` entry (the two pre-existing local copies disagreed: `lib/format.ts` had `pctHigh: 120`, `DuringSessionScreen.tsx` had `pctHigh: null`). The nullable variant is now canonical so `DuringSessionScreen.powerTarget()`'s open-ended upper-bound branch (`${lo}W+` / `${pctLow}%+ FTP`) is preserved when that screen is repointed at `lib/zones.ts` in a later slice.
- Zone hex/token values were not touched anywhere — `ZONE_META` continues to store `var(--color-zone-*)` references only; the actual PRD hex values remain defined solely in `index.css` (D-7 unchanged).

## Deviations from Plan

None - plan executed exactly as written.

One environment note (not a plan deviation): the worktree lacked a `node_modules` directory (git-ignored, not checked out by `git worktree add`). Symlinked `frontend/node_modules` to the main checkout's `frontend/node_modules` to run vitest/tsc; this is a local dev-environment artifact only, not a tracked or committed change.

## Issues Encountered
None.

## Next Phase Readiness
- `lib/zones.ts` is ready as the import target for downstream slices (B-E) to repoint their local zone-map duplicates (`ZoneChip.tsx`'s `ZONE_VAR`/`ZONE_LABEL`, `DuringSessionScreen.tsx`'s local `ZONE_META`) and delete their own copies when each screen is restyled.
- No blockers.

---
*Phase: 12-athletic-redesign*
*Completed: 2026-07-09*
