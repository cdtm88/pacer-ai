---
phase: 12-athletic-redesign
plan: 05
subsystem: ui
tags: [react, today-screen, session-card, stat-tile, zones, tokens]

# Dependency graph
requires: [12-01, 12-02]
provides:
  - "SessionCard redesign: 28px objective, Duration/TSS/IF StatTile row, WorkoutProfileChart at height=60 as card centerpiece"
  - "tss_target?: number | null on SessionData; getIntensityFactor() derives IF from tss_target + duration with no FTP dependency"
  - "Start ride / Export .zwo CTA copy (button text + aria-label + ZwoExportModal heading), rename landed with the coupled today.test.tsx assertions in the same commit"
  - "Single 'Log without riding' disclosure collapsing Mark done / Mark missed while keeping both mounted for accessible-name queries"
  - "WorkoutProfileChart optional height prop (default 34, backward compatible)"
  - "TodayScreen 'Coming up' strips (both empty-state and post-session) use 24x4px zoneColor() mini-bars instead of 8px dots; local ZONE_VAR/isValidZone removed in favor of @/lib/zones"
affects: [12-06, 12-07, 12-08]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "IF derivation without FTP: sqrt(tss_target / (duration_hr * 100)), rounded to 2dp, '—' fallback when data missing"
    - "Visually-collapsed-but-mounted disclosure pattern (max-height/opacity/pointer-events toggle, not conditional unmount) to satisfy both a quiet overflow UI and direct getByRole queries in existing tests"

key-files:
  created: []
  modified:
    - frontend/src/components/session/SessionCard.tsx
    - frontend/src/components/session/ZwoExportModal.tsx
    - frontend/src/tests/today.test.tsx
    - frontend/src/components/session/WorkoutProfileChart.tsx
    - frontend/src/screens/TodayScreen.tsx

key-decisions:
  - "Mark done/Mark missed stay mounted in the DOM at all times (visual collapse via CSS only) so the pre-existing today.test.tsx 'mark missed' tests keep working without an expand step first, per the plan's explicit DOM-presence constraint"
  - "TodayScreen's zone-dot -> mini-bar strips drop the isValidZone type-guard entirely and call zoneColor(type) directly, matching the plan's stated fallback behavior for unknown/invalid types"
  - "TodayScreen has no ftp query; SessionCard now receives ftp={null} explicitly (documented inline) rather than an implicit undefined, since IF derivation only needs tss_target + duration"

requirements-completed: [D-6, D-7, D-8]

coverage:
  - id: D1
    description: "SessionCard objective renders at 28px; SessionData declares tss_target; StatTile row (Duration/TSS/IF) renders under the profile chart with correct IF derivation and '—' fallback"
    requirement: D-6
    verification:
      - kind: unit
        ref: "cd frontend && npx vitest run src/tests/today.test.tsx (11/11 pass, includes new stat-tile assertion)"
        status: pass
    human_judgment: false
  - id: D2
    description: "Start CTA renamed to 'Start ride' with no inline backgroundColor override; Export CTA + ZwoExportModal heading renamed to 'Export .zwo' (button, aria-label, modal); rename and its two dependent test assertions land in the same commit"
    requirement: D-6
    verification:
      - kind: unit
        ref: "grep -q 'Start ride' frontend/src/components/session/SessionCard.tsx && ! grep -q 'Export to Zwift' frontend/src/components/session/SessionCard.tsx && ! grep -q 'Export to Zwift' frontend/src/components/session/ZwoExportModal.tsx"
        status: pass
    human_judgment: false
  - id: D3
    description: "Mark done / Mark missed collapse into a single quiet 'Log without riding' overflow affordance; both actions remain queryable by accessible name; Mark Missed AlertDialog copy unchanged"
    requirement: D-6
    verification:
      - kind: unit
        ref: "cd frontend && npx vitest run src/tests/today.test.tsx (mark-missed dialog tests pass unchanged)"
        status: pass
    human_judgment: false
  - id: D4
    description: "WorkoutProfileChart accepts optional height prop (default 34); TodayScreen drops local ZONE_VAR/isValidZone, imports zoneColor from @/lib/zones; both 'Coming up' strips render 24x4px 2px-radius zone-colored bars"
    requirement: D-7
    verification:
      - kind: unit
        ref: "grep -q 'height?: number' frontend/src/components/session/WorkoutProfileChart.tsx && ! grep -q 'ZONE_VAR' frontend/src/screens/TodayScreen.tsx && grep -q '@/lib/zones' frontend/src/screens/TodayScreen.tsx"
        status: pass
    human_judgment: false
  - id: D5
    description: "Full frontend suite green; tsc --noEmit clean"
    requirement: D-8
    verification:
      - kind: unit
        ref: "cd frontend && npx tsc --noEmit (clean) && npm test -- --run (148/148 tests, 18/18 files)"
        status: pass
    human_judgment: false

duration: 7min
completed: 2026-07-09
status: complete
---

# Phase 12 Plan 05: Today Hub Redesign (SessionCard + TodayScreen) Summary

**Rebuilt SessionCard as the Today hub's centerpiece — 28px objective, a Duration/TSS/IF stat-tile row driven by a no-FTP-required IF derivation, a taller centered WorkoutProfileChart, "Start ride"/"Export .zwo" CTAs, and a collapsed Mark-done/Mark-missed overflow — while repointing TodayScreen's two "Coming up" strips at shared zone-colored mini-bars and `lib/zones`.**

## Performance

- **Duration:** ~7 min
- **Started:** 2026-07-09T22:41:48+04:00 (approx, prior wave-1 tracking commit)
- **Completed:** 2026-07-09T22:48:55+04:00 (last task commit)
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `SessionCard.tsx`'s objective heading grows from 20px to 28px (Display role, Inter 600, line-height 1.15); `SessionData` gains `tss_target?: number | null`
- New `getEstTss()` / `getIntensityFactor()` helpers and a Duration/TSS/IF `StatTile` row render directly under `WorkoutProfileChart`, which now renders at `height={60}` as the card's visual centerpiece; IF is derived purely from `tss_target` + duration (`sqrt(tss_target / (durationHr * 100))`, 2dp), no FTP dependency, "—" fallback when data is missing
- Start CTA's inline `backgroundColor`/`color` override removed (12-01's token fix now brand-fills `variant="default"` correctly) and relabeled "Start session" → "Start ride"
- Export CTA and `ZwoExportModal`'s internal heading both renamed "Export to Zwift" → "Export .zwo" (button text, `aria-label`, and modal heading) in the same commit as the two dependent `today.test.tsx` assertion updates (D-6 Pitfall 1) plus a new `tss_target: 55` on `MOCK_SESSION` and a stat-tile-label assertion
- Mark done / Mark missed collapse behind a single "Log without riding" disclosure row with a rotating chevron; both actions remain mounted in the DOM at all times (visual collapse via `max-height`/`opacity`/`pointer-events`, not conditional unmount), so the existing `today.test.tsx` mark-missed tests continue to pass with a direct `getByRole` query and no expand step
- `WorkoutProfileChart` gained an optional `height?: number` prop (default 34, fully backward compatible with its other two callers)
- `TodayScreen.tsx` dropped its local `ZONE_VAR`/`isValidZone` duplicate zone map, importing `zoneColor` from `@/lib/zones` instead (D-8 dedup); both "Coming up" strips (empty-state and post-session) now render a 24×4px, 2px-radius zone-colored duration bar in place of the former 8px round dot
- `SessionCard` now receives `ftp={null}` explicitly from `TodayScreen` (documented inline — the screen has no ftp query today; the IF stat tile does not need it)

## Task Commits

Each task was committed atomically:

1. **Task 1: SessionCard redesign + Export copy rename + coupled test update** — `4996aa1` (feat)
2. **Task 2: WorkoutProfileChart height prop + TodayScreen mini-bars + zone dedup** — `fba1bc3` (feat)

_Note: no TDD tasks in this plan; both tasks are `type="auto"` and verified via grep + the full frontend suite._

## Files Created/Modified

- `frontend/src/components/session/SessionCard.tsx` — 28px objective, `tss_target` field, `getEstTss`/`getIntensityFactor` helpers, StatTile row, `height={60}` chart prop, Start/Export CTA renames, collapsed log-without-riding disclosure
- `frontend/src/components/session/ZwoExportModal.tsx` — internal heading "Export to Zwift" → "Export .zwo"
- `frontend/src/tests/today.test.tsx` — `MOCK_SESSION.tss_target: 55`; Export-copy assertions updated to `/export \.zwo/i` and `getAllByText('Export .zwo')`; new stat-tile-label test
- `frontend/src/components/session/WorkoutProfileChart.tsx` — optional `height` prop (default 34) replacing the fixed `height: 34`
- `frontend/src/screens/TodayScreen.tsx` — removed local `ZONE_VAR`/`isValidZone`; imports `zoneColor` from `@/lib/zones`; both strips render 24×4px mini-bars; `SessionCard` receives `ftp={null}`

## Decisions Made

- Kept Mark done / Mark missed permanently mounted (CSS-only visual collapse) rather than a true unmount/remount disclosure, because the plan's hard constraint ("BOTH actions must remain in the DOM with their exact accessible names") and the pre-existing test suite's direct `getByRole` queries (no expand-first step) require it
- Dropped the `isValidZone` type-guard in `TodayScreen.tsx` in favor of calling `zoneColor(type)` directly, per the plan's explicit option — `zoneColor` already falls back gracefully for unknown/null types
- Reused `frontend/node_modules` from the primary checkout via a local symlink in this worktree (lockfiles verified byte-identical) instead of a full `npm install`, since a fresh worktree checkout has no `node_modules` of its own — not a dependency change, purely a local build-environment shortcut

## Deviations from Plan

None — plan executed exactly as written. One incidental setup step, not itself a deviation: this worktree checkout had no `frontend/node_modules`; rather than run a fresh `npm ci`/`npm install`, the identical `node_modules` from the primary repo checkout was symlinked in (package-lock.json diffed byte-identical first) to save time — no packages were added, changed, or removed.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Today hub now matches the D-6 spec end-to-end: hero objective, populated stat tiles, taller centered profile chart, single dominant "Start ride" CTA, renamed "Export .zwo" secondary, collapsed log-without-riding overflow, and mini zone bars in both "Coming up" strips.
- `WorkoutProfileChart`'s new `height` prop and `@/lib/zones`' `zoneColor` are both now precedent for any remaining Slice D/E screens (Agenda, Progress) that still carry a local zone-color duplicate.
- Full frontend suite green (148/148 tests, 18/18 files); `tsc --noEmit` clean.
- No blockers identified.

---
*Phase: 12-athletic-redesign*
*Completed: 2026-07-09*

## Self-Check: PASSED

All created/modified files and task commit hashes verified present on disk / in git log.
