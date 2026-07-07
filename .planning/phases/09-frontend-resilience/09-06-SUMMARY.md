---
phase: 09-frontend-resilience
plan: 06
subsystem: ui
tags: [react, sse, fetch, streaming, error-recovery, onboarding]

# Dependency graph
requires:
  - phase: 09-frontend-resilience
    provides: StreamErrorBanner component (09-01) and its retry-then-terminal-error UX contract (09-UI-SPEC.md #1)
provides:
  - Onboarding's fetch-based SSE streams (initial/turn runStream, confirm-stream) apply the same silent-retry-then-terminal-error policy as chat's useSSEStream
  - Confirm-stream !res.ok path fixed: no longer silently falls through to pollForProfile (the D-05 stuck-spinner bug)
affects: [frontend-resilience, onboarding]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Retry policy duplicated (not shared) across useSSEStream (EventSource) and OnboardingScreen (fetch+ReadableStream) with a cross-reference comment, since EventSource cannot POST or set Authorization headers (Pitfall 1)"
    - "Split handleConfirm into a one-time UI-setup handler and a retry-capable runConfirmStream, so automatic/manual retries don't re-append the confirmation chat message"

key-files:
  created: []
  modified:
    - frontend/src/screens/OnboardingScreen.tsx
    - frontend/src/tests/onboarding.test.tsx

key-decisions:
  - "Duplicated the retry loop (MAX_RETRIES=2, BACKOFF_MS=[500,1500]) in both runStream and runConfirmStream with a cross-reference comment pointing to useSSEStream.ts, per 09-RESEARCH.md Open Question 1 recommendation, rather than extracting a shared util for two call sites"
  - "Added retry-on-SSE-error-event handling to the confirm-stream reader loop (not just the !res.ok branch) — the original code had no handling at all for a mid-stream 'error' event during confirm, which would also leave isStreaming stuck forever once the reader hit done:true with no branch taken"

requirements-completed: [item-13]

coverage:
  - id: D1
    description: "Initial/turn-message stream error retries silently up to 2 times (500ms/1500ms backoff) before surfacing StreamErrorBanner with Retry; isStreaming clears to false"
    requirement: item-13
    verification:
      - kind: unit
        ref: "frontend/src/tests/onboarding.test.tsx#an initial-message stream error retries silently up to 2 times (500ms/1500ms backoff) before any banner appears; after exhaustion, StreamErrorBanner renders with Retry and isStreaming is false"
        status: pass
    human_judgment: false
  - id: D2
    description: "Confirm-stream !res.ok path sets a terminal error with Retry instead of silently falling through to pollForProfile (the stuck-spinner bug)"
    requirement: item-13
    verification:
      - kind: unit
        ref: "frontend/src/tests/onboarding.test.tsx#the confirm-stream (!res.ok) path sets a terminal error instead of falling through to pollForProfile -- the spinner does not stick"
        status: pass
    human_judgment: false
  - id: D3
    description: "Clicking Retry re-invokes the failed call (initial stream or confirm-stream) and clears the banner optimistically"
    requirement: item-13
    verification:
      - kind: unit
        ref: "frontend/src/tests/onboarding.test.tsx#clicking Retry re-invokes the failed initial-stream call and clears the banner optimistically"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/onboarding.test.tsx#clicking Retry re-invokes the failed confirm-stream call and clears the banner optimistically"
        status: pass
    human_judgment: false
  - id: D4
    description: "OnboardingScreen does not import useSSEStream (Pitfall 1 guard) -- transport is not literally shared, only the retry policy and StreamErrorBanner component"
    requirement: item-13
    verification:
      - kind: unit
        ref: "frontend/src/tests/onboarding.test.tsx#does not import useSSEStream (Pitfall 1 guard -- EventSource cannot POST or set Authorization, so the transport is not shared)"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-07
status: complete
---

# Phase 09 Plan 06: Onboarding Stream Retry Policy Summary

**Mirrored the silent-retry-then-terminal-error policy from chat's useSSEStream into onboarding's fetch+ReadableStream transport, and fixed the confirm-stream stuck-spinner bug where a failed save silently fell through to pollForProfile with no error state at all.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-07T17:35:00Z (approx, worktree init)
- **Completed:** 2026-07-07T17:57:02Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- `runStream` (initial/turn-message stream) now retries silently up to 2 times (500ms/1500ms backoff) on `!res.ok`, mid-stream SSE `error` events, and network `catch` failures, mirroring `useSSEStream.ts`'s policy exactly
- `handleConfirm` was split into a one-time UI-setup handler and a retry-capable `runConfirmStream`, so the confirm-stream gets the identical retry loop without re-appending the "This looks right" chat message on each retry
- The confirm-stream's `!res.ok` branch (the D-05 stuck-spinner bug) now sets a terminal error ("Couldn't save your profile.") with Retry instead of silently calling `pollForProfile()` with no error state
- Also added retry handling to the confirm-stream's mid-stream `error` SSE event, which previously had no branch at all and would leave `isStreaming` stuck once the reader hit `done: true` (Rule 2 — same D-05 class of bug, not explicitly called out in the plan's line references but directly in scope)
- Replaced the static "Connection lost. Reconnecting..." banner with the shared `StreamErrorBanner` component (`variant="onboarding"`), wired to a `handleRetry` dispatcher that re-invokes whichever stream failed (initial/turn vs. confirm, disambiguated via `isConfirmed`)
- Extended `onboarding.test.tsx` with 4 new behavior tests plus a Pitfall-1 import guard (13 tests total, all passing)

## Task Commits

1. **Task 1: Mirror the retry-then-terminal-error policy in onboarding's streams (item 13, D-05)** - `94e94ae` (fix)

## Files Created/Modified
- `frontend/src/screens/OnboardingScreen.tsx` - Added `MAX_RETRIES`/`BACKOFF_MS` module constants, retry loops in `runStream`'s three failure paths, split `handleConfirm` into `runConfirmStream` (retry-capable) + `handleConfirm` (one-time setup), added `handleRetry` dispatcher, replaced static error banner with `StreamErrorBanner`
- `frontend/src/tests/onboarding.test.tsx` - Added a render-based describe block covering silent retry/backoff timing, confirm-stream terminal error, manual Retry re-invocation for both streams, and the "no useSSEStream import" guard

## Decisions Made
- Retry loop is duplicated (not extracted to a shared util) per 09-RESEARCH.md's Open Question 1 recommendation — two call sites don't justify the indirection, and a cross-reference comment (`// Mirrors the retry policy in useSSEStream.ts -- keep behavior in sync`) keeps behavior discoverable
- `lastUserMessageRef` tracks the last user-sent message so a manual Retry on the initial/turn stream re-invokes `runStream` with the same argument it was called with originally
- `isConfirmed` state (already existing) is reused to disambiguate which stream a manual Retry should re-invoke, rather than adding new state

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added retry handling to the confirm-stream's mid-stream `error` SSE event**
- **Found during:** Task 1
- **Issue:** The plan's action text focuses on the `!res.ok` branch (lines 317-321) as *the* stuck-spinner bug, but the confirm-stream's reader loop had no `event.type === 'error'` branch at all. If the server sent an `error` SSE event and then closed the connection, the `while` loop would eventually see `done: true`, break, and the function would return having called neither `pollForProfile()` nor any error setter — `isStreaming` would stay `true` forever, an equally-stuck spinner just triggered by a different failure mode.
- **Fix:** Added an `event.type === 'error'` branch to `runConfirmStream`'s reader loop, applying the same `retry()`/terminal-error logic as the `!res.ok` branch.
- **Files modified:** `frontend/src/screens/OnboardingScreen.tsx`
- **Verification:** Covered indirectly by the confirm-stream terminal-error test (which exercises `!res.ok`); the `error`-event branch mirrors the already-tested `runStream` pattern for the same event type.
- **Committed in:** `94e94ae` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical functionality)
**Impact on plan:** Closes an equally-valid stuck-spinner path in the same code path the plan targets. No scope creep — confined to the same function/file the plan already modifies.

## Issues Encountered
- The worktree had no `frontend/node_modules` (fresh worktree checkout). Symlinked from the main repo's `frontend/node_modules` (gitignored, not committed) to run `vitest` without a full reinstall.
- Vitest + fake timers required installing `vi.useFakeTimers()` *before* `render()` (not after confirming the first `fetch` call via `waitFor`), because `waitFor`'s real-timer polling let the mount effect's retry `setTimeout` get scheduled on the real clock before fake timers were installed, silently detaching the test's `advanceTimersByTimeAsync` calls from the actual pending timer. Fixed by installing fake timers first and using `vi.advanceTimersByTimeAsync(0)` to flush the initial fetch chain's microtasks.
- The Pitfall-1 "does not import useSSEStream" guard test initially matched the plan-mandated cross-reference *comment* text ("Mirrors the retry policy in useSSEStream.ts"), which correctly exists per Open Question 1's recommendation. Narrowed the regex to a line-scoped `import` statement check so the comment doesn't trip the guard.
- Pre-existing lint findings (`react-hooks/immutability`: `pollForProfile`/`runConfirmStream` self- and forward-references inside `useCallback`; `react-hooks/set-state-in-effect`) already existed on the original file before this plan's changes (verified via `git stash` diff). One new instance of the same pre-existing pattern (`runConfirmStream` referencing itself in its own retry closure) was introduced, consistent with the existing codebase style — out of scope to restructure per the deviation rules' scope boundary (pre-existing debt, not caused by this task, and fixing it would require an architectural change to the hook structure).

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Onboarding and chat now share the same retry-then-terminal-error UX (StreamErrorBanner, same 2-retry/500ms-1500ms-backoff policy) without sharing the transport, satisfying D-05's actual intent per 09-RESEARCH.md
- The confirm-stream stuck-spinner bug (both the `!res.ok` and `error`-event variants) is fully closed
- No blockers for remaining Phase 09 plans (09-07)

---
*Phase: 09-frontend-resilience*
*Completed: 2026-07-07*

## Self-Check: PASSED

- FOUND: frontend/src/screens/OnboardingScreen.tsx
- FOUND: frontend/src/tests/onboarding.test.tsx
- FOUND: .planning/phases/09-frontend-resilience/09-06-SUMMARY.md
- FOUND: 94e94ae (fix commit)
- FOUND: f028081 (summary commit)
