---
phase: 12-athletic-redesign
plan: 07
subsystem: ui
tags: [react, tailwind, design-system, navigation, typography]

requires:
  - phase: 12-athletic-redesign
    provides: "lib/zones.ts canonical zone map (12-02), lib/format.ts re-exports"
provides:
  - "ZONE_SPECTRUM gradient constant hoisted to lib/zones.ts, the single canonical source"
  - "AppLayout screen titles at 28px/600 Display weight with a date eyebrow above the title"
  - "Filled-pill (999px, color-mix brand 12%) active nav state shared by BottomTabBar and DesktopSidebar"
  - "DesktopSidebar app-wide zone-spectrum brand mark (replaces plain 'PacerAI' logotype text)"
affects: [12-08, 12-09, ui, shell-chrome]

tech-stack:
  added: []
  patterns:
    - "Zone-spectrum gradient brand mark: 'Pace' wordmark + ZONE_SPECTRUM gradient bar, single source in lib/zones.ts, reused at two scales (Login 36px, Sidebar 20px)"
    - "Filled-pill nav active state: border-radius 999px + color-mix(in srgb, var(--color-brand) 12%, transparent), replacing both the bottom-tab dot indicator and the sidebar left-stripe indicator"

key-files:
  created: []
  modified:
    - frontend/src/lib/zones.ts
    - frontend/src/screens/LoginScreen.tsx
    - frontend/src/components/AppLayout.tsx
    - frontend/src/components/nav/BottomTabBar.tsx
    - frontend/src/components/nav/DesktopSidebar.tsx

key-decisions:
  - "ZONE_SPECTRUM appended to the existing lib/zones.ts (not recreated) per wave-1 12-02 consolidation; LoginScreen and DesktopSidebar both import it, no duplicate definitions remain"
  - "AppLayout's h-dvh height-chain wrapping divs (lines 32, 39) left untouched; only the <header> title/eyebrow markup changed"
  - "Sidebar brand mark scaled to 20px (from Login's 36px) per UI-SPEC; mobile header keeps contextual page titles, not the brand mark"

patterns-established:
  - "Shell chrome brand mark: single ZONE_SPECTRUM import point, scaled per surface, never redefined locally"
  - "Filled-pill active nav state used identically across BottomTabBar and DesktopSidebar (including the Settings row)"

requirements-completed: [D-10, D-8]

coverage:
  - id: D1
    description: "ZONE_SPECTRUM hoisted from LoginScreen into lib/zones.ts; LoginScreen imports it instead of defining it locally"
    requirement: "D-8"
    verification:
      - kind: unit
        ref: "grep -q ZONE_SPECTRUM src/lib/zones.ts && grep -q \"from '@/lib/zones'\" src/screens/LoginScreen.tsx"
        status: pass
    human_judgment: false
  - id: D2
    description: "AppLayout header title raised to 28px/600 Display weight; date moved above the title as a 12px/600 eyebrow; height-chain wrapping divs untouched"
    requirement: "D-10"
    verification:
      - kind: unit
        ref: "src/tests/AppLayout.test.tsx#both wrapping containers use h-dvh and neither uses min-h-screen"
        status: pass
    human_judgment: false
  - id: D3
    description: "BottomTabBar labels bumped to 11px/600; active dot replaced with a filled color-mix(brand 12%) 999px pill"
    requirement: "D-10"
    verification:
      - kind: unit
        ref: "grep -q 'fontSize: 11' src/components/nav/BottomTabBar.tsx && grep -q 'color-mix(in srgb, var(--color-brand) 12%' src/components/nav/BottomTabBar.tsx"
        status: pass
    human_judgment: false
  - id: D4
    description: "DesktopSidebar 3px left-stripe active indicator replaced with the same filled-pill treatment on nav rows and the Settings row; plain 'PacerAI' logotype replaced with the zone-spectrum brand mark"
    requirement: "D-10"
    verification:
      - kind: unit
        ref: "! grep -q '3px solid var(--color-brand)' src/components/nav/DesktopSidebar.tsx && grep -q ZONE_SPECTRUM src/components/nav/DesktopSidebar.tsx"
        status: pass
    human_judgment: false
  - id: D5
    description: "Full frontend suite green; tsc --noEmit clean"
    verification:
      - kind: unit
        ref: "npm test -- --run (147/147 passed) and npx tsc --noEmit (clean)"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-09
status: complete
---

# Phase 12 Plan 07: Shell Chrome — Display Titles, Filled-Pill Nav, Brand Mark Summary

**Raised AppLayout screen titles to 28px/600 Display weight with a date eyebrow, converted both navs (BottomTabBar + DesktopSidebar) to a shared filled-pill active state, and adopted the zone-spectrum wordmark as the app-wide brand mark in the sidebar by hoisting `ZONE_SPECTRUM` into `lib/zones.ts`.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-09T22:44:00Z
- **Completed:** 2026-07-09T22:56:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `ZONE_SPECTRUM` gradient constant hoisted from `LoginScreen.tsx` into `lib/zones.ts` (single canonical source); `LoginScreen` now imports it, no duplicate definition
- `AppLayout` header `<h1>` raised from 20px/700 to 28px/600 (Display role); the per-route date moved above the title as a 12px/600 `--color-ink-3` eyebrow; the frozen `h-dvh`/`md:ml-60` height-chain divs were untouched and `AppLayout.test.tsx` stays green
- `BottomTabBar` labels bumped to 11px/600 (from 10px/500); the small active dot removed and replaced with a `color-mix(in srgb, var(--color-brand) 12%, transparent)` 999px filled pill around the icon+label group
- `DesktopSidebar` active indicator changed from a 3px left stripe to the same filled-pill treatment (999px, 12% brand mix, no left border), applied identically to the Settings row; the plain "PacerAI" logotype text replaced with the zone-spectrum brand mark (20px "Pace" wordmark + `ZONE_SPECTRUM` gradient bar, imported from `lib/zones`)

## Task Commits

Each task was committed atomically:

1. **Task 1: Hoist ZONE_SPECTRUM to lib/zones.ts and adopt AppLayout display title + eyebrow** - `b8b0467` (feat)
2. **Task 2: Filled-pill active state for BottomTabBar and DesktopSidebar + sidebar brand mark** - `5f94b6b` (feat)

**Plan metadata:** committed in this SUMMARY commit (worktree mode — orchestrator handles STATE.md/ROADMAP.md centrally after merge)

## Files Created/Modified
- `frontend/src/lib/zones.ts` - Added `ZONE_SPECTRUM` gradient constant export (canonical source, appended to existing wave-1 zone map)
- `frontend/src/screens/LoginScreen.tsx` - Removed local `ZONE_SPECTRUM` const; imports from `@/lib/zones` instead
- `frontend/src/components/AppLayout.tsx` - Header `<h1>` 20px/700 -> 28px/600; date `<p>` moved above title as eyebrow; height-chain divs untouched
- `frontend/src/components/nav/BottomTabBar.tsx` - Labels 10px/500 -> 11px/600; active dot removed; filled-pill active state added
- `frontend/src/components/nav/DesktopSidebar.tsx` - 3px left-stripe replaced with filled-pill active state (nav rows + Settings row); logotype replaced with zone-spectrum brand mark

## Decisions Made
- `ZONE_SPECTRUM` appended to the existing `lib/zones.ts` (not recreated), preserving the canonical zone map consolidated in wave 1's 12-02 plan
- Sidebar brand mark scaled to 20px (vs. Login's 36px) per UI-SPEC's explicit sizing guidance for the 240px-wide sidebar
- `AppLayout`'s frozen height-chain wrapping divs (lines 32/39, `h-dvh`/`md:ml-60`) were left completely untouched per RESEARCH.md Pitfall 5; only the `<header>` internals changed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed frontend dependencies via `npm ci`**
- **Found during:** Task 1 verification
- **Issue:** The worktree checkout had no `node_modules`; `npx vitest` and `npx tsc` failed with `ERR_MODULE_NOT_FOUND` before any test could run
- **Fix:** Ran `npm ci` from the existing `package-lock.json` (no new packages added, no version changes — installs the exact locked dependency set)
- **Files modified:** none (node_modules is gitignored, not committed)
- **Verification:** `npx vitest run src/tests/AppLayout.test.tsx` and `npx tsc --noEmit` ran cleanly afterward
- **Committed in:** N/A (no file changes to commit; node_modules is gitignored)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Necessary environment setup only; no scope creep, no plan changes.

## Issues Encountered
- One `npm test -- --run` pass showed a single transient failure in `chat.test.tsx` (`ReferenceError: EventSource is not defined`), unrelated to any file this plan touches. Re-ran the full suite and it passed 147/147; running `chat.test.tsx` alone (both with and without this plan's changes stashed) also passed every time. This is pre-existing test-isolation flakiness in the SSE test setup, out of scope per the deviation rules' scope boundary (not caused by this plan's changes, not touched by this plan's `files_modified`).

## Next Phase Readiness
- Shell chrome (D-10) and the `ZONE_SPECTRUM` dedup (D-8) are complete; the app-wide brand mark and pill-nav pattern are established for any later screens that need the same treatment
- No blockers for subsequent Phase 12 plans

---
*Phase: 12-athletic-redesign*
*Completed: 2026-07-09*
