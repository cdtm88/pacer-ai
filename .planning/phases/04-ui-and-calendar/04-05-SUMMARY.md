---
phase: 04-ui-and-calendar
plan: "05"
subsystem: frontend-nav-and-screens
status: complete
tags: [navigation, session-card, today-screen, agenda-screen, tsb-gate, zone-chips]
completed: 2026-06-20
duration: "5m"

dependency_graph:
  requires:
    - 04-04  # auth gates, router scaffold, api.ts
  provides:
    - AppLayout (responsive nav shell)
    - BottomTabBar / DesktopSidebar
    - SessionCard (Today card + 4-button action row)
    - ZoneChip / TsbChip (token-driven)
    - TodayScreen / AgendaScreen (data-connected)
    - today.test.tsx (TSB gate + mark-missed flow coverage)
  affects:
    - router.tsx (AppLayout + real screen imports wired in)

tech_stack:
  added:
    - shadcn/ui: badge, tooltip, alert-dialog, accordion, skeleton, separator
  patterns:
    - NavLink active state with style callback (React Router 7)
    - TanStack Query useQuery for session/PMC data
    - CSS custom property zone color lookup (no inline hex)
    - TSB gate: render null unless tss_display_ready === true

key_files:
  created:
    - frontend/src/components/AppLayout.tsx
    - frontend/src/components/nav/BottomTabBar.tsx
    - frontend/src/components/nav/DesktopSidebar.tsx
    - frontend/src/components/session/ZoneChip.tsx
    - frontend/src/components/session/TsbChip.tsx
    - frontend/src/components/session/SessionCard.tsx
    - frontend/src/screens/TodayScreen.tsx
    - frontend/src/screens/AgendaScreen.tsx
    - frontend/src/tests/today.test.tsx
    - frontend/src/components/ui/badge.tsx
    - frontend/src/components/ui/tooltip.tsx
    - frontend/src/components/ui/alert-dialog.tsx
    - frontend/src/components/ui/accordion.tsx
    - frontend/src/components/ui/skeleton.tsx
    - frontend/src/components/ui/separator.tsx
  modified:
    - frontend/src/router.tsx (AppLayout + TodayScreen + AgendaScreen imports)

decisions:
  - "ZoneChip uses color-mix(in srgb, var(--color-zone-*) 15%, transparent) for the 15% opacity background tint -- single CSS custom property lookup per zone, no inline hex"
  - "TsbChip thresholds: tsb > 5 = fresh, tsb < -10 = fatigued, -10..5 = balanced (documented inline)"
  - "BottomTabBar indicator dot positioned via absolute relative to the NavLink flex container"
  - "TooltipProvider placed in AppLayout to scope tooltip context to authenticated screens; also added to test Wrapper"
  - "shadcn components installed to frontend/@/components/ui/ by CLI (path alias bug); moved to frontend/src/components/ui/ manually"
  - "Export to Zwift wrapped in a span so disabled button can still be a TooltipTrigger child"

metrics:
  duration: "5m"
  tasks_completed: 3
  tasks_total: 3
  files_created: 15
  files_modified: 1
  tests_added: 14
  tests_passing: 14
---

# Phase 4 Plan 05: Navigation Shell and Today/Agenda Screens Summary

**One-liner:** Responsive nav shell (bottom tab bar + desktop sidebar) plus data-connected Today and Agenda screens with TSB gate enforcement, zone-color chips, and full test coverage for D-14 and Mark Missed flow.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | AppLayout, BottomTabBar, DesktopSidebar | 26de481 | AppLayout.tsx, nav/BottomTabBar.tsx, nav/DesktopSidebar.tsx, router.tsx |
| 2 | ZoneChip, TsbChip, SessionCard | 5c3b4d3 | session/ZoneChip.tsx, session/TsbChip.tsx, session/SessionCard.tsx |
| 3 | TodayScreen, AgendaScreen, gate/flow tests | c72fbdd | screens/TodayScreen.tsx, screens/AgendaScreen.tsx, tests/today.test.tsx |

## What Was Built

**Navigation shell:** BottomTabBar (56px + env(safe-area-inset-bottom), 4 tabs: Today/Agenda/History/Chat) shown below the 768px breakpoint. DesktopSidebar (240px fixed) shown at 768px and above with same destinations plus Settings at the bottom. AppLayout wraps both, renders a Settings gear icon in the screen header (not a 5th tab, per D-15), and provides TooltipProvider context for the Tooltip components used in SessionCard.

**Session components:**
- ZoneChip: single `ZONE_VAR` lookup map keyed to the CSS custom property name; background tint via `color-mix(in srgb, var(--color-zone-*) 15%, transparent)`; no inline hex anywhere.
- TsbChip: returns null unless `pmc.tss_display_ready === true` (D-14 enforced). When shown, classifies tsb > 5 as fresh (good-green tint), tsb < -10 as fatigued (amber tint), otherwise balanced (blue-0 tint).
- SessionCard: complete UI-SPEC Today card implementation. All four action buttons with verbatim copy. Export to Zwift is disabled with "Coming in the next update" tooltip (D-10). Mark Missed opens a shadcn AlertDialog with exact spec copy: title "Mark this session as missed?", body "This will trigger a re-plan. Your coach will adjust upcoming sessions.", CTA "Yes, mark missed" / Cancel "Keep it". No em dashes anywhere.

**Screens:**
- TodayScreen: fetches today session (`['session', 'today']`) and latest PMC (`['pmc', 'latest']`) via TanStack Query. Renders SessionCard when session exists. Next-few-days strip from `getUpcomingSessions`, horizontal scroll on mobile, vertical list on desktop, each row taps to /agenda. Empty state ("No session today" / "Your next ride is {day}. Rest up.") has no CTA. Error state has Retry.
- AgendaScreen: fetches upcoming sessions (`['sessions', 'upcoming']`). Groups by ISO week (Monday-anchored). Sticky week headers. Each row in shadcn Accordion: date column, type + truncated objective preview, 12px zone-color dot, duration, status icon (CheckCircle green if completed, XCircle red if missed/skipped). Accordion expands to full objective + structure + targets. Empty state ("No sessions planned yet" + "Go to Chat" CTA to /chat). Error state with retry.

**Tests (today.test.tsx):** 14 tests across TsbChip gate and SessionCard flows:
- TsbChip: 5 tests confirming null when tss_display_ready false or pmc null; fresh/fatigued/balanced rendered when true
- SessionCard: TSB chip absent when not ready; TSB chip present when ready; Export to Zwift disabled; Mark Missed dialog opens with correct title; dialog shows correct body copy

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] shadcn CLI path alias resolution**
- **Found during:** Task 1
- **Issue:** `npx shadcn@canary add` wrote components to `frontend/@/components/ui/` literally instead of resolving the `@` alias to `frontend/src/`
- **Fix:** Moved all component files from `frontend/@/components/ui/` to `frontend/src/components/ui/` manually
- **Files modified:** badge.tsx, tooltip.tsx, alert-dialog.tsx, accordion.tsx, skeleton.tsx, separator.tsx

**2. [Rule 1 - Bug] TooltipProvider missing in test wrapper**
- **Found during:** Task 3 test run
- **Issue:** SessionCard uses `<Tooltip>` which requires `<TooltipProvider>` in the React tree; tests failed with "Tooltip must be used within TooltipProvider"
- **Fix:** Added `TooltipProvider` import and wrapper to the test `Wrapper` component in today.test.tsx
- **Commit:** Included in c72fbdd

## Known Stubs

None. All screens are data-connected via TanStack Query calling real API helpers. Placeholder screens in router.tsx for History, Chat, DuringSession, Settings, and Onboarding are tracked in earlier plans and remain as intentional placeholders until their respective plans execute.

## Threat Flags

No new threat surface introduced beyond the plan's threat model. Data fetched via `apiFetch` (JWT injected); mark-missed and mark-done mutations protected by AlertDialog confirmation (T-04-15). TSB chip gated on `tss_display_ready` (T-04-16).

## Self-Check: PASSED

- frontend/src/components/AppLayout.tsx: EXISTS
- frontend/src/components/nav/BottomTabBar.tsx: EXISTS
- frontend/src/components/nav/DesktopSidebar.tsx: EXISTS
- frontend/src/components/session/ZoneChip.tsx: EXISTS
- frontend/src/components/session/TsbChip.tsx: EXISTS
- frontend/src/components/session/SessionCard.tsx: EXISTS
- frontend/src/screens/TodayScreen.tsx: EXISTS
- frontend/src/screens/AgendaScreen.tsx: EXISTS
- frontend/src/tests/today.test.tsx: EXISTS
- Commits: 26de481 / 5c3b4d3 / c72fbdd: VERIFIED
- `npm test -- --run`: 14/14 PASSED
- `npx tsc --noEmit`: NO ERRORS
