---
phase: 04-ui-and-calendar
plan: "08"
subsystem: frontend-pwa
tags: [during-session, pwa, ios-banner, vercel, deploy]
dependency_graph:
  requires: [04-04, 04-05]
  provides: [DuringSessionScreen, IOSInstallBanner, PWAIcons, VercelConfig]
  affects: [frontend/src/screens, frontend/src/components/pwa, frontend/public]
tech_stack:
  added: []
  patterns: [static-step-hierarchy, ios-banner-gate, pwa-icons]
key_files:
  created:
    - frontend/src/components/session/SessionStepList.tsx
    - frontend/src/screens/DuringSessionScreen.tsx
    - frontend/src/components/pwa/IOSInstallBanner.tsx
    - frontend/public/apple-touch-icon.png
    - frontend/public/pwa-192x192.png
    - frontend/public/pwa-512x512.png
    - frontend/vercel.json
    - frontend/.env.example
    - frontend/src/tests/pwa.test.tsx
  modified:
    - frontend/src/router.tsx
    - frontend/src/components/AppLayout.tsx
    - frontend/src/stores/uiStore.ts
decisions:
  - "IOSInstallBanner delegates dismiss persistence to uiStore.setIOSBannerDismissed (single localStorage write path, consistent 'true' value)"
  - "uiStore localStorage read wrapped in try/catch for vitest v4 SSR/isolated-module environments"
  - "PWA icons generated programmatically via Python struct+zlib (no Pillow dependency)"
  - "DuringSessionScreen uses placeholder steps so layout is verifiable in Phase 4; Phase 5 wires live session data"
metrics:
  duration: "~25 min"
  completed: "2026-06-20"
  tasks_completed: 3
  tasks_total: 3
  files_created: 9
  files_modified: 3
status: complete
---

# Phase 04 Plan 08: During-Session Screen, iOS PWA Banner, and Vercel Deploy Summary

Static during-session stepper with placeholder timer, iOS install banner gated on UA plus ontouchstart, three PWA icon PNGs, and Vercel SPA deploy config.

## Tasks Completed

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | SessionStepList and static During-Session screen | 7f939df | SessionStepList.tsx, DuringSessionScreen.tsx, router.tsx |
| 2 | iOS install banner and PWA icon assets | 96bd390 | IOSInstallBanner.tsx, apple-touch-icon.png, pwa-192x192.png, pwa-512x512.png |
| 3 | Vercel deploy config, env example, and PWA/banner test | 0322fbd | vercel.json, .env.example, pwa.test.tsx |

## What Was Built

**SessionStepList** renders the three-tier static step hierarchy: current step at 40px bold with a 4px zone-color strip, next step at 20px semibold labeled "Next: ...", and remaining steps at 16px muted. No ticking, no auto-advance.

**DuringSessionScreen** is full-screen with `--color-bg-2` background, renders SessionStepList with representative placeholder steps, shows a static "00:00" timer with "Timer activates in next phase" caption, and an "End session" outline button (--color-bad) navigating to "/". The router now wires `/session` to the real screen.

**IOSInstallBanner** gates on: iOS UA regex + `'ontouchstart' in window` (excludes Mac Safari per Pitfall 5) + not in standalone mode + not previously dismissed. Dismiss writes via `uiStore.setIOSBannerDismissed(true)` which stores `'true'` in `localStorage['ios-banner-dismissed']`. Banner is rendered from AppLayout above BottomTabBar.

**PWA icons**: apple-touch-icon.png (180x180), pwa-192x192.png, pwa-512x512.png generated as valid PNGs with white background and blue-6 (#228BE6) "P" glyph. Referenced by the existing vite-plugin-pwa manifest config.

**vercel.json**: SPA rewrite sending all non-asset paths to `/index.html`, with explicit `buildCommand` and `outputDirectory`.

**.env.example**: documents VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_URL with explicit warning that service-role key and JWT secret must never appear here.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] uiStore localStorage access failed in vitest v4 test environment**
- **Found during:** Task 3 (running tests)
- **Issue:** `localStorage.getItem(IOS_BANNER_KEY)` at module init time caused `TypeError: localStorage.getItem is not a function` in vitest v4's isolated module context, breaking auth.test.tsx (pre-existing) and pwa.test.tsx
- **Fix:** Wrapped localStorage read in `try/catch` in `readDismissed()` helper; used `vi.stubGlobal('localStorage', makeLocalStorageMock())` in pwa.test.tsx
- **Files modified:** `frontend/src/stores/uiStore.ts`, `frontend/src/tests/pwa.test.tsx`
- **Commit:** 0322fbd

**2. [Rule 1 - Bug] IOSInstallBanner wrote conflicting localStorage values**
- **Found during:** Task 3 test debugging
- **Issue:** Component called `localStorage.setItem(BANNER_KEY, '1')` then `setIOSBannerDismissed(true)` which overwrote with `'true'`, creating inconsistent read-back
- **Fix:** Removed direct localStorage write from component; all persistence goes through `setIOSBannerDismissed(true)` in the store. `isBannerDismissed()` accepts both `'true'` and `'1'` for forward-compatibility
- **Files modified:** `frontend/src/components/pwa/IOSInstallBanner.tsx`
- **Commit:** 0322fbd

## Test Results

- `npm test -- --run`: 31/31 tests pass (5 test files)
- `npm run build`: exits 0, PWA precache 8 entries

## Self-Check

- [x] SessionStepList.tsx exists
- [x] DuringSessionScreen.tsx exists with "Timer activates in next phase" and no setInterval/Date.now
- [x] IOSInstallBanner.tsx exists with ontouchstart and ios-banner-dismissed checks
- [x] apple-touch-icon.png, pwa-192x192.png, pwa-512x512.png exist as valid PNGs
- [x] vercel.json exists with SPA rewrite
- [x] .env.example exists with VITE_SUPABASE_URL
- [x] pwa.test.tsx: 3 tests pass
- [x] All 31 tests pass; build exits 0

## Self-Check: PASSED
