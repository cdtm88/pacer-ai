---
phase: 12-athletic-redesign
plan: 09
subsystem: ui
tags: [tailwind, shadcn, css-tokens, settings-screen]

# Dependency graph
requires:
  - phase: 12-athletic-redesign
    provides: D-8 Foundation Fixes (shadcn button/accent token mapping), D-12 Settings card redesign
provides:
  - "--color-card and --color-card-foreground @theme tokens backing shadcn's bg-card / text-card-foreground utilities"
  - "Explicit border-border utility on the Card primitive so border-color resolves to --color-line instead of falling back to currentColor"
affects: [SettingsScreen, ui-verification, 12-UAT]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "shadcn @theme token remap pattern (var(--color-x) -> semantic shadcn token) extended to card tokens, matching the existing button/accent token group"

key-files:
  created: []
  modified:
    - frontend/src/index.css
    - frontend/src/components/ui/card.tsx

key-decisions:
  - "Used explicit border-border utility on Card instead of a global `@layer base { * { @apply border-border } }` rule, to avoid repointing bare-border utilities on button/badge/separator/accordion/alert-dialog across every other screen (zero blast radius outside SettingsScreen, per plan's explicit instruction)"

requirements-completed: [D-8, D-12]

coverage:
  - id: D1
    description: "SettingsScreen's three Card sections render as white lifted surfaces (bg-card -> --color-surface) with light hairline borders (border-border -> --color-line) instead of transparent backgrounds with near-black borders"
    requirement: "D-12"
    verification:
      - kind: unit
        ref: "frontend/src/tests/SettingsScreen.test.tsx"
        status: pass
      - kind: manual_procedural
        ref: "grep assertions on index.css/card.tsx source; computed-style browser verification deferred to phase UAT re-run"
        status: pass
    human_judgment: true
    rationale: "Final closure of the 12-UAT.md Test 4 gap requires a live browser check of computed backgroundColor/border-color on /settings, per the plan's own verification section; source-level and test-level checks all pass here."

duration: 6min
completed: 2026-07-10
status: complete
---

# Phase 12 Plan 09: Card Theme Tokens Gap Closure Summary

**Added missing `--color-card` / `--color-card-foreground` @theme tokens and an explicit `border-border` utility on the shadcn Card primitive, closing the 12-UAT.md Test 4 gap where SettingsScreen's Cards rendered with a transparent background and a near-black border.**

## Performance

- **Duration:** 6 min
- **Started:** 2026-07-10T15:08:00Z
- **Completed:** 2026-07-10T15:14:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- `frontend/src/index.css` `@theme` block now defines `--color-card: var(--color-surface)` and `--color-card-foreground: var(--color-ink)`, backing the `bg-card` / `text-card-foreground` utilities already used by `card.tsx`.
- `frontend/src/components/ui/card.tsx` Card's className now includes `border-border` alongside the existing bare `border` utility, so the Card's border-color resolves to `--color-border` -> `--color-line` (#DFE0E2) instead of falling back to `currentColor` (near-black `--color-ink`).
- Closes the single outstanding 12-UAT.md gap (Test 4, major) for SettingsScreen's three Card sections.

## Task Commits

Each task was committed atomically:

1. **Task 1: Add missing card theme tokens and give the Card an explicit border color** - `10c53e3` (fix)

**Plan metadata:** committed separately per worktree protocol (SUMMARY.md only; STATE.md/ROADMAP.md owned by the orchestrator)

## Files Created/Modified
- `frontend/src/index.css` - Added `--color-card` and `--color-card-foreground` to the `@theme` block, in the same group as the existing shadcn button/accent token remaps.
- `frontend/src/components/ui/card.tsx` - Added `border-border` to the Card function's className (CardHeader/CardContent/CardTitle/etc. untouched).

## Decisions Made
- Chose the explicit `border-border` utility on the Card primitive over a global `@layer base { * { @apply border-border } }` rule, exactly as the plan specified, to keep the change scoped to the Card surface and avoid regressing bare-`border` usages on Button/Badge/Separator/Accordion/AlertDialog across the six already-passing screens.
- Did not add `--color-muted-foreground` or any other token; `CardDescription`/`text-muted-foreground` is unused by SettingsScreen and was explicitly out of scope per the plan.

## Deviations from Plan

None - plan executed exactly as written. One environment note: `frontend/node_modules` was not present in this worktree (fresh worktree checkout); ran `npm install` before the plan's verification commands (`npm run build`, `npm test`) so they could execute. This is routine worktree setup, not a code change, and is not tracked as a Rule 1-4 deviation.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- The 12-UAT.md Test 4 gap (SettingsScreen Card background/border) is closed at the source level: tokens defined, build clean, existing SettingsScreen test green.
- Final closure requires a live browser check on `/settings` confirming computed `backgroundColor: rgb(255,255,255)` and `border-color: rgb(223,224,226)` on the three Card sections — this is the phase's end-of-phase UAT re-run, not additional code work.

---
*Phase: 12-athletic-redesign*
*Completed: 2026-07-10*

## Self-Check: PASSED

- FOUND: frontend/src/index.css
- FOUND: frontend/src/components/ui/card.tsx
- FOUND: .planning/phases/12-athletic-redesign/12-09-SUMMARY.md
- FOUND commit: 10c53e3 (fix(12-09): add missing card theme tokens and Card border color)
- FOUND commit: 743a2f0 (docs(12-09): add plan summary for card theme tokens gap closure)
