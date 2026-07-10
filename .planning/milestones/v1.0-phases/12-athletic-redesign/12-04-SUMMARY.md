---
phase: 12-athletic-redesign
plan: 04
subsystem: ui
tags: [react, typescript, tailwind, design-system, during-session]

requires:
  - phase: 12-athletic-redesign (plan 01)
    provides: Barlow Condensed display font, --cockpit-* tokens, --color-achieve, button tokens
  - phase: 12-athletic-redesign (plan 02)
    provides: consolidated frontend/src/lib/zones.ts zone map (ZONE_META/zoneColor/zoneLabel)
provides:
  - Dark cockpit render-layer rebuild of DuringSessionScreen (D-1)
  - Watts-as-hero / timer-secondary hierarchy inversion (D-2)
  - No-FTP effort-word + RPE hero fallback (D-4)
  - Session profile rail with lit/dimmed/upcoming per-step zone segments (D-3)
  - Achieve-orange session-complete CTA (D-11)
  - ZONE_META consolidated to @/lib/zones (local duplicate removed)
affects: [athletic-redesign remaining plans touching session/progress UI, future dark-mode work (DARK-01)]

tech-stack:
  added: []
  patterns:
    - "Render-layer-only rebuild against a frozen state/effects boundary: restyle JSX without touching hooks, refs, or persistence effects"
    - "Cockpit dark surface exception scoped to a single screen via --cockpit-* tokens, not a global theme"
    - "Reuse a component's proportional-sizing geometry (flexBasis/flexGrow) without importing the component when the data shape differs"

key-files:
  created: []
  modified:
    - frontend/src/screens/DuringSessionScreen.tsx

key-decisions:
  - "Aliased the @/lib/zones zoneColor/zoneLabel imports (zoneColorFor/zoneLabelFor) to avoid a naming collision with this file's existing local zoneColor/zoneLabel destructured consts, rather than renaming ~10 downstream usages"
  - "Dropped the filled zone-color lozenge/pill styling from the power target now that it renders as hero-scale text (D-2), rather than keeping the pill at hero size"
  - "Effort-word vocabulary and short cues per zone (recovery=EASY/spin easy, endurance=STEADY/hold steady, tempo=BRISK/drive it, threshold=HARD/push, vo2=MAX EFFORT/empty it) filled in per the Copywriting Contract's stated assumption, consistent with the one given example (\"HARD, 8/10, push\")"
  - "Session profile rail placed as the last element inside the existing centred content column (inherits its bottom safe-area padding) rather than as a new sibling section, per the plan's literal 'bottom of the cockpit content column' wording"

patterns-established:
  - "Frozen-boundary render rebuilds: read state/refs as opaque inputs, restyle only JSX, gate every step on the pre-existing regression test"

requirements-completed: [D-1, D-2, D-3, D-4, D-7, D-11]

coverage:
  - id: D1
    description: "Dark cockpit surface (D-1): main SessionRunner background is var(--color-cockpit-bg), body/secondary text and dividers recolored to --color-cockpit-ink/-ink-2/-line, no pure black"
    requirement: D-1
    verification:
      - kind: unit
        ref: "frontend/src/tests/session.test.tsx (14 tests, all green)"
        status: pass
      - kind: other
        ref: "grep for var(--color-cockpit-bg) and absence of #000/#000000 in DuringSessionScreen.tsx"
        status: pass
    human_judgment: true
    rationale: "Visual legibility/contrast of a dark surface at arm's length is a genuine judgment call; tracked as a non-gating manual check in 12-VALIDATION.md per the plan's <verification> block."
  - id: D2
    description: "Hero hierarchy inversion (D-2): watt target renders at clamp(96px, 18vw, 160px) Barlow Condensed 700; timer demoted to clamp(48px, 10vw, 72px) Barlow Condensed 600, positioned below"
    requirement: D-2
    verification:
      - kind: unit
        ref: "frontend/src/tests/session.test.tsx (14 tests, all green)"
        status: pass
      - kind: other
        ref: "grep confirms watt-hero clamp max (160px) exceeds timer-secondary clamp max (72px); both use var(--font-family-display)"
        status: pass
    human_judgment: false
  - id: D4
    description: "No-FTP effort-word + RPE hero fallback: session-level rpe_target prop threaded into SessionRunner; when ftp is null, effort word + RPE/10 + short cue renders at the same hero scale/position as the watt target"
    requirement: D-4
    verification:
      - kind: unit
        ref: "frontend/src/tests/session.test.tsx (14 tests, all green; profile mock has ftp=null so this path exercises on every fixture run)"
        status: pass
      - kind: other
        ref: "grep rpe_target; tsc --noEmit clean"
        status: pass
    human_judgment: true
    rationale: "session.test.tsx's profile mock resolves ftp: null, so the fallback path renders in every test run, but no test asserts the specific effort-word/RPE/cue text content — a human visual check confirms the copy reads correctly at hero scale."
  - id: D3
    description: "Session profile rail (D-3): bottom rail with one flexBasis/flexGrow segment per SessionStep, current step lit, elapsed dimmed via color-mix(...35%, --color-cockpit-bg), upcoming at standard zone-color opacity; WorkoutProfileChart geometry reused, component not imported"
    requirement: D-3
    verification:
      - kind: unit
        ref: "frontend/src/tests/session.test.tsx (14 tests, all green) + full suite (npm test -- --run, 147/147 green)"
        status: pass
      - kind: other
        ref: "grep flexBasis|flexGrow, grep color-mix(in srgb, grep confirms WorkoutProfileChart not imported"
        status: pass
    human_judgment: false
  - id: D11
    description: "Session-complete CTA uses var(--color-achieve) instead of var(--color-blue-6); session-complete surface stays light-mode"
    requirement: D-11
    verification:
      - kind: unit
        ref: "frontend/src/tests/session.test.tsx (14 tests, all green)"
        status: pass
      - kind: other
        ref: "grep var(--color-achieve); grep confirms no var(--color-blue-6) remains on the session-complete CTA"
        status: pass
    human_judgment: false
  - id: D7
    description: "Zone colors reused as-is (no cockpit-specific variants); verified all 5 zone hexes maintain >=3.0:1 contrast against --color-cockpit-bg"
    requirement: D-7
    verification:
      - kind: other
        ref: "WCAG contrast calculation: recovery 4.18, endurance 5.05, tempo 8.36, threshold 5.01, vo2 3.29 (all >=3.0 against #14171D)"
        status: pass
    human_judgment: false

duration: 4min
completed: 2026-07-09
status: complete
---

# Phase 12 Plan 04: Cockpit Render-Layer Rebuild Summary

**DuringSessionScreen rebuilt into a dark cockpit with watts-as-hero (not timer), a no-FTP effort-word/RPE fallback, a bottom per-step zone-colored profile rail, and an achieve-orange complete CTA — persistence/iOS logic frozen and unchanged (session.test.tsx green throughout).**

## Performance

- **Duration:** 4 min
- **Started:** 2026-07-09T22:46:00+04:00 (approx.)
- **Completed:** 2026-07-09T22:51:23+04:00
- **Tasks:** 3
- **Files modified:** 1 (`frontend/src/screens/DuringSessionScreen.tsx`), plus a new `deferred-items.md`

## Accomplishments
- Dark cockpit surface (D-1): `DuringSessionScreen`'s active-session background, text, and dividers now use the scoped `--color-cockpit-*` token set instead of the light zone-tinted wash; no pure black anywhere
- Hierarchy inversion (D-2): watt target is now the hero at `clamp(96px, 18vw, 160px)` Barlow Condensed 700; the timer is demoted to `clamp(48px, 10vw, 72px)` Barlow Condensed 600, below the watts
- No-FTP fallback (D-4): a new session-level `rpe_target` prop drives an effort-word + RPE/10 + short-cue hero string (e.g. "HARD, 8/10, push") at the exact same hero scale/position, mutually exclusive with the watt hero
- Session profile rail (D-3): a new bottom rail renders one proportional zone-colored segment per `SessionStep`, with current/elapsed/upcoming visual states, reusing `WorkoutProfileChart`'s layout math without importing the component
- Achieve-orange CTA (D-11): the session-complete "Back to today" button now fills with `var(--color-achieve)` instead of `var(--color-blue-6)`
- Local `ZONE_META` duplicate removed in favor of the consolidated `@/lib/zones` import (D-7); all 5 zone hex colors verified to hold >=3.0:1 contrast against the new cockpit background
- Frozen persistence/timer/pause/fast-forward/iOS boundary (everything above line ~389 pre-edit) untouched at every step; `session.test.tsx` stayed green across all 3 task commits

## Task Commits

Each task was committed atomically:

1. **Task 1: Cockpit surface + hero inversion + zone-map swap + session-complete CTA** - `6f76a8b` (feat)
2. **Task 2: No-FTP effort-word + RPE hero fallback (D-4)** - `1c98ef3` (feat)
3. **Task 3: Session profile rail (D-3)** - `d5d3ea2` (feat)

_No TDD tasks in this plan (type="auto" throughout); no plan-metadata commit yet — this SUMMARY commit follows._

## Files Created/Modified
- `frontend/src/screens/DuringSessionScreen.tsx` - Render-layer rebuild: cockpit tokens, watts-hero/timer-secondary, no-FTP effort-word fallback, session profile rail, achieve-orange CTA; `@/lib/zones` import replaces local `ZONE_META`
- `.planning/phases/12-athletic-redesign/deferred-items.md` - New file logging a pre-existing, out-of-scope eslint finding discovered during Task 3 verification

## Decisions Made
- Aliased the `@/lib/zones` `zoneColor`/`zoneLabel` function imports as `zoneColorFor`/`zoneLabelFor` to avoid colliding with this file's existing local `zoneColor`/`zoneLabel` destructured consts (used in ~10 places downstream); assigned via `const zoneColor = zoneColorFor(zone)` so the import is used immediately (no unused-import `tsc --noEmit` failure) and all existing downstream usages needed no renaming
- Dropped the filled zone-color lozenge/pill treatment from the power target now that it's rendered as large hero text (D-2) — the pill made sense at the old 30px secondary scale but not at hero scale; the zone badge above the hero still carries the border+text zone-color identity
- Filled in the effort-word vocabulary and short imperative cues for all 5 zones (Copywriting Contract only specified the threshold example "HARD, 8/10, push"): recovery="EASY, spin easy", endurance="STEADY, hold steady", tempo="BRISK, drive it", threshold="HARD, push", vo2="MAX EFFORT, empty it" — consistent ordering, no em dashes
- Placed the session profile rail as the last element inside the existing centred content column (rather than a new sibling section outside it), so it inherits the column's existing `env(safe-area-inset-bottom)` padding without needing a duplicate safe-area rule

## Deviations from Plan

None - plan executed exactly as written. One out-of-scope, pre-existing issue was discovered and logged (not fixed) per the scope-boundary rule:

### Logged (not auto-fixed, out of scope)

**1. Pre-existing eslint react-hooks/refs + react-hooks/set-state-in-effect errors inside the frozen boundary**
- **Found during:** Task 3 verification (`npx eslint`)
- **Issue:** 7 eslint errors (reading `ref.current` during render in `useState`/`useRef` initializers; calling `setState` synchronously inside the live-resume fast-forward `useEffect`), all inside the plan's explicitly FROZEN persistence boundary (pre-edit lines <389)
- **Why not fixed:** verified identical at pre-12-04 commit `9c6ac2d` (before any of this plan's edits); fixing requires restructuring `restoredRef`/the fast-forward effect, which is an architectural change outside this render-layer-only plan's scope, and would risk the exact iOS persistence regression this plan's frozen-boundary rule exists to prevent
- **Logged in:** `.planning/phases/12-athletic-redesign/deferred-items.md`

## Issues Encountered
None - all three tasks' automated verification (vitest, tsc, grep checks) passed on the first pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `DuringSessionScreen.tsx`'s render layer is fully migrated to the cockpit/hero design system for this milestone's Slice B; `session.test.tsx` (14/14) and the full frontend suite (147/147) are green, and `tsc --noEmit` is clean
- Manual browser verification (dark cockpit legibility at arm's length, no-FTP effort-word copy, physical iOS Safari re-test) remains outstanding and non-gating per this plan's `<verification>` block — tracked in `12-VALIDATION.md`
- The pre-existing eslint findings inside the frozen persistence boundary remain open for a future plan explicitly scoped to that logic

---
*Phase: 12-athletic-redesign*
*Completed: 2026-07-09*

## Self-Check: PASSED

- FOUND: frontend/src/screens/DuringSessionScreen.tsx
- FOUND: .planning/phases/12-athletic-redesign/12-04-SUMMARY.md
- FOUND: .planning/phases/12-athletic-redesign/deferred-items.md
- FOUND commit: 6f76a8b (Task 1)
- FOUND commit: 1c98ef3 (Task 2)
- FOUND commit: d5d3ea2 (Task 3)
- FOUND commit: 4e11087 (SUMMARY.md)
