---
phase: 09-frontend-resilience
plan: 05
subsystem: ui
tags: [react, tanstack-query, tailwind, vitest, dvh, sonner]

requires:
  - phase: 04-ui-and-calendar
    provides: FitUploadZone component and AppLayout shell (mobile bottom tabs / desktop sidebar)
provides:
  - Indeterminate upload progress bar on FitUploadZone (additive to existing spinner)
  - Drag-drop .fit extension validation (mirrors file-picker accept=.fit path)
  - Full five-key query invalidation on upload success (rides, pmc/latest, pmc-history, session/today, sessions/upcoming)
  - AppLayout height chain fixed to h-dvh (both wrapping divs), unblocking pinned chat input and inner scroll panes on iOS Safari
affects: [history, today, chat, ios-pwa]

tech-stack:
  added: []
  patterns:
    - "Full query-key invalidation list at mutation success sites, not prefix-match shortcuts, when the codebase has inconsistent query-key naming (['pmc-history'] vs ['pmc','latest'])"
    - "h-dvh (not h-screen/min-h-screen) for any full-viewport wrapping container, matching DuringSessionScreen's existing 100dvh convention"

key-files:
  created:
    - frontend/src/tests/FitUploadZone.test.tsx
    - frontend/src/tests/AppLayout.test.tsx
  modified:
    - frontend/src/components/history/FitUploadZone.tsx
    - frontend/src/components/AppLayout.tsx
    - frontend/src/index.css

key-decisions:
  - "Indeterminate progress bar sweep implemented as a CSS @keyframes block in index.css (no existing keyframes precedent in this file), rather than inline style keyframes which CSSOM does not support"
  - "Progress bar rendered as a sibling below the fixed-height 80px dropzone box, not inside it, to avoid overflow/reflow of the existing spinner+text layout while still reading as 'beneath the dropzone content' per UI-SPEC"
  - "Upload-success invalidation switched from a single await to Promise.all of five explicit invalidateQueries calls, all still awaited before setIsUploading(false) via the existing finally block"
  - "AppLayout class-presence test placed in a new AppLayout.test.tsx file rather than appended to FitUploadZone.test.tsx (plan listed the latter as the file target) for clarity; both files are colocated and covered in the same task's verification command family"

patterns-established:
  - "Query invalidation comment convention: mutation call sites that fan out to multiple query keys should carry a comment pointing future authors at the full list (guards against Pitfall 2 recurring)"

requirements-completed: [item-14, item-09]

coverage:
  - id: D1
    description: "Indeterminate progress bar renders while uploading and unmounts on completion, additive to the existing Loader2 spinner"
    requirement: item-14
    verification:
      - kind: unit
        ref: "frontend/src/tests/FitUploadZone.test.tsx#renders an indeterminate progress bar while uploading, and unmounts it on completion"
        status: pass
    human_judgment: false
  - id: D2
    description: "Drag-drop of a non-.fit file is rejected with toast.error('Only .fit files are supported.') and never calls uploadRide"
    requirement: item-14
    verification:
      - kind: unit
        ref: "frontend/src/tests/FitUploadZone.test.tsx#rejects a non-.fit file on drop with a toast and never calls uploadRide"
        status: pass
    human_judgment: false
  - id: D3
    description: "Drag-drop of a valid .fit file calls uploadRide"
    requirement: item-14
    verification:
      - kind: unit
        ref: "frontend/src/tests/FitUploadZone.test.tsx#calls uploadRide when a .fit file is dropped"
        status: pass
    human_judgment: false
  - id: D4
    description: "Successful upload invalidates all five affected query keys (rides, pmc/latest, pmc-history, session/today, sessions/upcoming)"
    requirement: item-14
    verification:
      - kind: unit
        ref: "frontend/src/tests/FitUploadZone.test.tsx#invalidates every affected query key on successful upload"
        status: pass
    human_judgment: false
  - id: D5
    description: "AppLayout's outer and inner wrapping divs use h-dvh, not min-h-screen/h-screen"
    requirement: item-09
    verification:
      - kind: unit
        ref: "frontend/src/tests/AppLayout.test.tsx#both wrapping containers use h-dvh and neither uses min-h-screen"
        status: pass
    human_judgment: false
  - id: D6
    description: "Chat input stays pinned to bottom and auto-scroll follows new messages on a physical iOS Safari device, no bottom clipping when the address bar shows"
    requirement: item-09
    verification: []
    human_judgment: true
    rationale: "iOS Safari dynamic-viewport/scroll behavior cannot be verified in jsdom; per 09-VALIDATION.md this is a Manual-Only Verification queued for the phase gate (matches the existing IOS-03 physical-device-retest pattern in MEMORY.md)"

duration: 15min
completed: 2026-07-07
status: complete
---

# Phase 09 Plan 05: Upload UX + AppLayout Height Chain Summary

**Indeterminate upload progress bar, drag-drop .fit validation, and full five-key query invalidation on FitUploadZone; AppLayout wrapping divs switched from min-h-screen to h-dvh to unblock pinned chat input and iOS Safari scroll panes.**

## Performance

- **Duration:** ~15 min
- **Completed:** 2026-07-07T17:24:24Z
- **Tasks:** 2 completed
- **Files modified:** 5 (3 modified, 2 created)

## Accomplishments

- FitUploadZone now shows a 3px indeterminate progress bar beneath the dropzone while uploading, additive to the existing spinner and "Uploading ride..." text
- Drag-drop now validates the `.fit` extension before uploading (previously only the file-picker `accept=".fit"` attribute enforced this, and browsers do not enforce `accept` on drops), rejecting bad files with `toast.error('Only .fit files are supported.')`
- Upload success now invalidates all five affected query keys (`['rides']`, `['pmc','latest']`, `['pmc-history']`, `['session','today']`, `['sessions','upcoming']`) instead of just `['rides']`, so History, Today's PMC sparkline, and session cards all refresh after an upload
- AppLayout's outer and inner wrapping divs switched from `min-h-screen` to `h-dvh`, matching the codebase's existing `DuringSessionScreen` `100dvh` convention, unblocking the pinned chat input and inner scroll pane behavior on iOS Safari

## Task Commits

Each task was committed atomically:

1. **Task 1: Upload progress bar, drag-drop validation, and full invalidation (item 14)** - `36cdf24` (feat)
2. **Task 2: AppLayout height chain min-h-screen to h-dvh (item 9)** - `b4ec40a` (fix)

_Note: implementation and tests were authored together per task rather than as separate RED/GREEN commits; all tests were verified green before each task's single commit._

## Files Created/Modified

- `frontend/src/components/history/FitUploadZone.tsx` - Progress bar markup, drag-drop `.fit` extension check, five-key invalidation with guiding comment
- `frontend/src/components/AppLayout.tsx` - Both wrapping divs `min-h-screen` → `h-dvh`; `<main>` left unchanged
- `frontend/src/index.css` - New `@keyframes fit-upload-progress-sweep` + `.fit-upload-progress-sweep` utility class for the indeterminate bar animation
- `frontend/src/tests/FitUploadZone.test.tsx` - New; covers progress bar render/unmount, drag-drop rejection, drag-drop acceptance, and full invalidation key list (4 tests)
- `frontend/src/tests/AppLayout.test.tsx` - New; class-presence check that both wrapping containers use `h-dvh` and neither uses `min-h-screen` (1 test)

## Decisions Made

- Progress bar rendered as a sibling immediately after the 80px dropzone box (not inside its fixed-height flex column) to avoid disturbing the existing spinner+text layout while still satisfying "beneath the dropzone content" from 09-UI-SPEC.md §4
- Sweep animation implemented via a project-first `@keyframes` block added to `index.css` (no prior keyframes existed in this file; `ChatBubble`'s `StreamingEllipsis` used Tailwind's built-in `animate-bounce` instead) since inline React styles cannot declare `@keyframes`
- Invalidation calls wrapped in `Promise.all` (still awaited) rather than five sequential `await` statements, for the same coalesced-refetch behavior with less code
- Added a second test file (`AppLayout.test.tsx`) instead of appending to `FitUploadZone.test.tsx` as literally listed in the plan's `<files>` block, for readability; both are covered by the same `npx vitest run` verification family and ran together during Task 2 verification

## Deviations from Plan

None - plan executed exactly as written (one minor file-organization choice noted above under Decisions Made, not a behavioral deviation).

## Issues Encountered

The worktree had no `node_modules` installed for the frontend package (main repo checkout had it, this worktree did not). Ran `npm install` in `frontend/` before the first test run; this is local dev-environment setup, not a code change, so no commit was needed for it.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Both item-14 and item-9 fixes are complete and covered by passing automated tests (5/5 new tests, 84/84 total frontend tests green, no regressions). Item 9's definitive pinned-input/auto-scroll behavior on a physical iOS Safari device remains a Manual-Only Verification (D6 above), queued for the phase gate alongside the existing IOS-03 physical-device retest already tracked in MEMORY.md. No blockers for other 09-frontend-resilience plans.

---
*Phase: 09-frontend-resilience*
*Completed: 2026-07-07*
