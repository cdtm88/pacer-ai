---
phase: 12-athletic-redesign
plan: 01
subsystem: ui
tags: [css, tailwind, shadcn, typography, google-fonts, design-tokens]

# Dependency graph
requires: []
provides:
  - "shadcn button @theme token block (--color-primary/-foreground, --color-destructive, --color-secondary/-foreground, --color-accent/-foreground, --color-background, --color-foreground, --color-border, --color-input, --color-ring) mapped to the existing brand palette"
  - "--font-family-display token (Barlow Condensed, Inter fallback) + Barlow Condensed 600/700 loaded from Google Fonts CDN"
  - "--color-cockpit-* scoped dark tokens (bg/surface/ink/ink-2/line) for Slice B's DuringSessionScreen rebuild"
  - ".stat-num (Inter 700, corrected from unloaded 800) / .stat-num-hero (Barlow Condensed 700) class split; StatTile migrated to the hero class"
affects: [12-02, 12-03, 12-04, 12-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hero-scale numeric readouts (>=28px) use .stat-num-hero (Barlow Condensed display face); inline/tabular readouts stay on .stat-num (Inter)"
    - "shadcn Button variants now resolve against real palette tokens instead of undefined/browser-default values"

key-files:
  created: []
  modified:
    - frontend/index.html
    - frontend/src/index.css
    - frontend/src/components/ui/StatTile.tsx

key-decisions:
  - "No new hex colors invented for the button-token block; every entry references an existing palette token (--color-brand, --color-bad, --color-bg-2, --color-ink, --color-blue-0, --color-surface, --color-line)"
  - "--cockpit-* tokens defined but not applied to any screen in this plan (deferred to Slice B / 12-04) per plan scope"
  - "Only StatTile's value span migrates to .stat-num-hero; all other stat-num consumers (StatTile delta, SettingsScreen, AgendaScreen, WeeklyLoadChart, RideChart, PmcChart, WorkoutProfileChart) confirmed inline-scale (12-15px) and left on .stat-num"

patterns-established:
  - "Display-face token (--font-family-display) reserved exclusively for hero-scale numerals, never body/UI text"

requirements-completed: [D-5, D-8, D-1]

coverage:
  - id: D1
    description: "Barlow Condensed 600/700 loads from Google Fonts CDN alongside Inter in one combined link"
    requirement: D-5
    verification:
      - kind: unit
        ref: "grep -q 'Barlow+Condensed:wght@600;700' frontend/index.html"
        status: pass
    human_judgment: false
  - id: D2
    description: "Full shadcn button token set (--color-primary/-foreground, --color-destructive, --color-secondary/-foreground, --color-accent/-foreground, --color-background, --color-foreground, --color-border, --color-input, --color-ring) defined in @theme, mapped to existing palette, no new colors invented"
    requirement: D-8
    verification:
      - kind: unit
        ref: "grep -q -- '--color-primary:' frontend/src/index.css"
        status: pass
    human_judgment: false
  - id: D3
    description: "--color-cockpit-* scoped dark tokens (bg/surface/ink/ink-2/line) added to @theme, not applied anywhere yet, no pure black introduced"
    requirement: D-1
    verification:
      - kind: unit
        ref: "grep -q -- '--color-cockpit-bg:' frontend/src/index.css"
        status: pass
    human_judgment: false
  - id: D4
    description: ".stat-num/.stat-num-hero split live; StatTile value span on the display face; full frontend suite green"
    requirement: D-5
    verification:
      - kind: unit
        ref: "grep -q 'stat-num-hero' frontend/src/index.css && grep -q 'stat-num-hero' frontend/src/components/ui/StatTile.tsx"
        status: pass
      - kind: unit
        ref: "cd frontend && npm test -- --run (140/140 tests, 17/17 files)"
        status: pass
    human_judgment: false

duration: 3min
completed: 2026-07-09
status: complete
---

# Phase 12 Plan 01: Foundation Typography/Token Fixes Summary

**Fixed the shadcn Button undefined-token defect and the Inter-800 synthesized-bold defect by adding a real button-token @theme block, loading Barlow Condensed for hero numerals, and splitting `.stat-num` into inline vs. hero-scale classes; also pre-defined the scoped `--cockpit-*` dark tokens Slice B depends on.**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-07-09T18:34:01Z (approx, first commit at 22:34:01+04:00)
- **Completed:** 2026-07-09T18:36:55Z (approx, last commit at 22:36:55+04:00)
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- `frontend/index.html`'s font link now loads Barlow Condensed 600/700 alongside the existing Inter 400/500/600/700, single combined stylesheet request, `display=swap` preserved
- `frontend/src/index.css` `@theme` gained the complete shadcn button-token mapping (12 tokens) plus `--font-family-display`, fixing every `<Button>` variant that was previously rendering against undefined CSS custom properties
- `frontend/src/index.css` `@theme` gained the 5 `--color-cockpit-*` dark-surface tokens (D-1), defined but not yet consumed by any screen — unblocks Slice B (12-04)
- `.stat-num` corrected from an unloaded/synthesized `font-weight: 800` to the loaded `700`; new `.stat-num-hero` class added using `--font-family-display` for hero-scale numerals
- `StatTile.tsx`'s hero value span (`clamp(34px, 8vw, 52px)`) migrated to `.stat-num-hero`; its delta span and every other `.stat-num` consumer in the codebase (SettingsScreen, AgendaScreen, WeeklyLoadChart, RideChart, PmcChart, WorkoutProfileChart) confirmed inline-scale and left unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1: Load Barlow Condensed and add the @theme token blocks** - `b869212` (feat)
2. **Task 2: Split .stat-num and migrate hero-scale usage in StatTile** - `6b794ec` (feat)

_Note: no TDD tasks in this plan; both tasks are `type="auto"` config/CSS changes verified via grep + full test suite._

## Files Created/Modified
- `frontend/index.html` - combined Google Fonts link now includes `Barlow+Condensed:wght@600;700` alongside the existing Inter weights
- `frontend/src/index.css` - added shadcn button-token block, `--font-family-display`, `--color-cockpit-*` tokens; split `.stat-num` into `.stat-num` (Inter 700) and `.stat-num-hero` (Barlow Condensed 700)
- `frontend/src/components/ui/StatTile.tsx` - value span class changed from `stat-num` to `stat-num-hero`

## Decisions Made
- No new hex colors invented for the button tokens; all 12 map to already-existing palette tokens per UI-SPEC Foundation Fixes §3
- `--cockpit-*` tokens added but intentionally not wired into any component in this plan — explicitly deferred to Slice B (12-04) per the plan's scope boundary
- Only StatTile's value span (the one genuinely hero-scale `.stat-num` usage) migrated to `.stat-num-hero`; verified via `grep -rn "stat-num" frontend/src` that no other usage is hero-scale

## Deviations from Plan

None - plan executed exactly as written. One incidental setup step not itself a deviation: `frontend/node_modules` was absent in this fresh worktree checkout, so `npm ci` was run before `npm test` could execute (installs from the existing `package-lock.json`, no new packages added, not a Rule 3 package-install exception since no package name was introduced).

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Button token defect and typography defect both fixed at the foundation layer; Slices B-E can now consume `<Button>` correctly and use `.stat-num-hero` for any further hero-scale numerals.
- `--cockpit-*` tokens are ready for Slice B (12-04) to consume when rebuilding `DuringSessionScreen`.
- Full frontend suite green (140/140 tests, 17/17 files) — no regression to ProgressScreen or any StatTile consumer.
- No blockers identified.

---
*Phase: 12-athletic-redesign*
*Completed: 2026-07-09*
