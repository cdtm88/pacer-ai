---
phase: 05-during-session-and-zwo-export
plan: "03"
subsystem: frontend/session
status: complete
tags: [during-session, timer, wake-lock, free-ride, react, zustand]
dependency_graph:
  requires: ["05-02"]
  provides: ["DuringSessionScreen-live", "DurationPickerModal", "freeRideDurationMins-slice"]
  affects: ["05-04", "05-05"]
tech_stack:
  added: []
  patterns:
    - "useSessionTimer composed in DuringSessionScreen for step-level countdown"
    - "useWakeLock called on mount (IOS-01); cleaned up on unmount"
    - "freeRideDurationMins: ephemeral Zustand slice, not persisted, reset on DuringSessionScreen unmount (T-05-09)"
    - "parseSteps maps session.structure warmup/main_set/cooldown to SessionStep[]"
    - "generateFreeRideSteps: 10/80/10 split, min 3 min per segment"
    - "Session complete overlay rendered inline when currentIndex >= steps.length"
    - "Auto-advance: useEffect fires goNext() when secondsLeft === 0 and stepDuration > 0"
    - "3-second countdown warning below timer when secondsLeft <= 3 and next step exists"
    - "useSessionTimer mocked in tests to return controlled secondsLeft values"
key_files:
  created:
    - frontend/src/components/session/DurationPickerModal.tsx
    - frontend/src/tests/session.test.tsx
  modified:
    - frontend/src/stores/uiStore.ts
    - frontend/src/screens/DuringSessionScreen.tsx
    - frontend/src/screens/TodayScreen.tsx
decisions:
  - "Mocked useSessionTimer in tests to avoid fake-timer infinite-loop issues with setInterval"
  - "SessionRunner extracted as inner component to own timer state; DuringSessionScreen is a thin data loader"
  - "Auto-advance guard requires stepDuration > 0 to prevent loops when step duration is 0"
  - "Free-ride step split: Warm-up 10%, Free ride 80%, Cool-down 10%, each minimum 3 min"
metrics:
  duration: "4min"
  completed_date: "2026-06-21"
  tasks_completed: 3
  files_changed: 5
---

# Phase 05 Plan 03: DuringSessionScreen Live Stepper Summary

DuringSessionScreen rewritten from Phase 4 static stub into a full live stepper with Date.now() timer, 3-second countdown warning, auto-advance, Skip step, wake lock, Session complete overlay, and free-ride path.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | freeRideDurationMins store slice + DurationPickerModal | 860f2f9 | uiStore.ts, DurationPickerModal.tsx |
| 2 | Rewrite DuringSessionScreen + session tests | 8377054 | DuringSessionScreen.tsx, session.test.tsx |
| 3 | Wire Ride anyway into TodayScreen | 5092aab | TodayScreen.tsx |

## What Was Built

**DuringSessionScreen (rewritten):** Composes useWakeLock (IOS-01) and useSessionTimer. Parses session.structure into 3 SessionStep objects (warmup/main_set/cooldown) via parseSteps, or generates 3 proportional steps via generateFreeRideSteps when freeRideDurationMins is set (D-10/D-11/D-12). Renders SessionStepList with currentIndex, a live MM:SS countdown, a 3-second warning "Starting [next] in N..." (D-01), a Skip step button (D-02), and a full-screen Session complete overlay on completion (D-03). Resets freeRideDurationMins to null on unmount to prevent T-05-09 leakage.

**DurationPickerModal:** AlertDialog with 30/45/60 min preset buttons (mutually exclusive selection) and a custom input validated 10-180 inclusive. "Start session" is disabled until a valid choice is made. On confirm: writes chosen duration to Zustand and navigates to /session. Input out of range shows "Enter a time between 10 and 180 minutes". Mitigates T-05-08.

**uiStore.ts:** Added ephemeral freeRideDurationMins (number | null) slice with setter. Not persisted to localStorage.

**TodayScreen.tsx:** "Ride anyway" secondary button added to the !session rest-day empty state. Opens DurationPickerModal via pickerOpen state.

**session.test.tsx:** 4 Vitest tests using mocked useSessionTimer, useWakeLock, and free-ride path to avoid query and timer complexity. Covers: first step render, auto-advance, Session complete overlay, Skip step.

## Verification

- `npx vitest run src/tests/session.test.tsx src/tests/today.test.tsx`: 14 tests passed (4 new + 10 existing)
- `npx tsc --noEmit`: clean
- No em dashes in any modified file

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] SessionRunner extracted as inner component**
- **Found during:** Task 2
- **Issue:** useSessionTimer must be called with the current step duration, but step-advancing state lives in the same component. Extracting SessionRunner as an inner component that receives already-computed steps clarifies the state ownership and avoids prop-drilling timer resets.
- **Fix:** DuringSessionScreen is a thin data-loader; SessionRunner owns currentIndex, timer, and overlay state.
- **Files modified:** DuringSessionScreen.tsx

**2. [Rule 1 - Bug] Test approach: mock useSessionTimer instead of fake timers**
- **Found during:** Task 2 test iteration
- **Issue:** vi.runAllTimersAsync() caused "infinite loop after 10000 timers" because setInterval(tick, 250) fires endlessly. waitFor() deadlocked with fake timers active.
- **Fix:** vi.mock('@/hooks/useSessionTimer') returns controlled secondsLeft values per test; free-ride path bypasses useQuery for deterministic step data. Tests are deterministic and fast.
- **Files modified:** session.test.tsx

## Threat Surface Scan

No new network endpoints or trust boundaries introduced. T-05-08 (custom input validation) mitigated in DurationPickerModal. T-05-09 (stale freeRideDurationMins) mitigated via useEffect cleanup on DuringSessionScreen unmount.

## Self-Check: PASSED

- [x] frontend/src/screens/DuringSessionScreen.tsx exists and contains useSessionTimer, useWakeLock, Skip step, Session complete, Back to today, Starting
- [x] frontend/src/components/session/DurationPickerModal.tsx exists with preset labels and validation copy
- [x] frontend/src/stores/uiStore.ts contains freeRideDurationMins
- [x] frontend/src/tests/session.test.tsx: 4 tests pass
- [x] frontend/src/screens/TodayScreen.tsx contains Ride anyway and DurationPickerModal
- [x] Commits 860f2f9, 8377054, 5092aab exist
