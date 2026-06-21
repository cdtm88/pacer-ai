---
phase: 05-during-session-and-zwo-export
plan: "02"
subsystem: frontend-hooks
tags: [ios, wake-lock, timer, hooks, tdd]
dependency_graph:
  requires: []
  provides: [useSessionTimer, useWakeLock, nosleep.js]
  affects: [frontend/src/screens/DuringSessionScreen.tsx]
tech_stack:
  added: [nosleep.js@0.12.0]
  patterns: [Date.now() delta timer, Wake Lock API with fallback, visibilitychange resync]
key_files:
  created:
    - frontend/src/hooks/useSessionTimer.ts
    - frontend/src/hooks/useWakeLock.ts
    - frontend/src/types/nosleep.d.ts
    - frontend/src/tests/useSessionTimer.test.ts
    - frontend/src/tests/useWakeLock.test.ts
  modified:
    - frontend/package.json
    - frontend/package-lock.json
decisions:
  - "visibilitychange handler snapshots elapsed into pausedElapsedRef AND resets startRef on both hidden and visible transitions to prevent double-counting ticks while hidden"
  - "useWakeLock always runs NoSleep.js fallback when sentinel is null after try/catch, covering iOS < 18.4 PWA silent-fail"
metrics:
  duration: "8min"
  completed: "2026-06-21"
  tasks_completed: 2
  files_created: 5
  files_modified: 2
status: complete
---

# Phase 05 Plan 02: Session Timer and Wake Lock Hooks Summary

Date.now() delta countdown timer and Wake Lock hook with NoSleep.js fallback, both unit-tested against IOS-01 and IOS-02 requirements.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Install nosleep.js + type declaration + useSessionTimer hook (IOS-02) | 8548c10 | package.json, nosleep.d.ts, useSessionTimer.ts, useSessionTimer.test.ts |
| 2 | useWakeLock hook with NoSleep.js fallback (IOS-01) | a0bfc28 | useWakeLock.ts, useWakeLock.test.ts |

## What Was Built

- **nosleep.js@0.12.0** installed as a dependency with a hand-written ambient module declaration (`nosleep.d.ts`) since no `@types/nosleep.js` package exists.
- **useSessionTimer(totalSeconds)** counts down using `Date.now()` deltas (never tick counts). On `visibilitychange`, snapshots elapsed into `pausedElapsedRef` and resets `startRef` on both hidden and visible transitions, so background time is correctly accumulated. The hook clamps at 0 and resets fully on `advance()`.
- **useWakeLock()** feature-detects `'wakeLock' in navigator` before calling `request('screen')`. If the sentinel is null after the try/catch (API absent or denied, including iOS < 18.4 PWA silent-fail), it dynamically imports NoSleep.js and calls `enable()`. Re-acquires on `visibilitychange` to visible. Cleanup releases sentinel and disables NoSleep.

## Verification

- 5/5 useSessionTimer tests pass (countdown, visibilitychange resync, clamp at 0, advance reset)
- 4/4 useWakeLock tests pass (native acquire, NoSleep fallback absent/rejected, cleanup on unmount)
- `tsc --noEmit` clean
- `grep nosleep.js frontend/package.json` returns match

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] visibilitychange resync double-counting**
- **Found during:** Task 1 TDD GREEN phase
- **Issue:** PATTERNS.md target code only reset `startRef` on visible transition, not on hidden. During the hidden period, ticks continued computing `pausedElapsedRef + (now - original_startRef)` -- which double-counted the pre-hide elapsed once the tab became visible again (startRef reset to now, losing the background time).
- **Fix:** On both hidden and visible transitions, snapshot elapsed into `pausedElapsedRef` and reset `startRef = Date.now()`. This ensures ticks always compute a short delta from the most recent transition, and `pausedElapsedRef` accumulates the full historical elapsed.
- **Files modified:** `frontend/src/hooks/useSessionTimer.ts`
- **Commit:** 8548c10

## Known Stubs

None.

## Threat Flags

None. Both hooks are pure browser DOM/client state with no network calls, no PII, no secrets. T-05-06 (wake lock DoS) is mitigated by the feature-detect guard and NoSleep fallback.

## TDD Gate Compliance

- RED gate: import error confirmed (no tests ran) before hook files existed.
- GREEN gate: all tests passed after implementation.
- REFACTOR: not required (code is clean as written).

## Self-Check: PASSED

- frontend/src/hooks/useSessionTimer.ts: FOUND
- frontend/src/hooks/useWakeLock.ts: FOUND
- frontend/src/types/nosleep.d.ts: FOUND
- frontend/src/tests/useSessionTimer.test.ts: FOUND
- frontend/src/tests/useWakeLock.test.ts: FOUND
- Commit 8548c10: FOUND
- Commit a0bfc28: FOUND
