---
phase: 09-frontend-resilience
plan: 02
subsystem: ui
tags: [react, localStorage, react-query, session-timer, resilience]

requires:
  - phase: 09-frontend-resilience
    provides: 09-RESEARCH.md / 09-PATTERNS.md exact-line verification of sessionPersistence.ts, TodayScreen.tsx, DuringSessionScreen.tsx
provides:
  - PersistedSession identity (sessionId + date) so a stale/mismatched localStorage record can be detected
  - loadMatchingSession() — silent stale-session discard used by TodayScreen and DuringSessionScreen
  - fastForwardSteps() — shared multi-step epoch fast-forward used by both the reload path (computeRestoredState) and the live-resume path
affects: [09-frontend-resilience (other plans touching TodayScreen/DuringSessionScreen), any future phase touching session persistence]

tech-stack:
  added: []
  patterns:
    - "Identity fields (sessionId + date) on a localStorage-persisted record, validated against live server state before trust — silent discard on mismatch, no UI"
    - "Extract-and-share pure state-transition function (fastForwardSteps) so two call sites (mount restore, live resume) can never drift into inconsistent behavior"

key-files:
  created: []
  modified:
    - frontend/src/lib/sessionPersistence.ts
    - frontend/src/screens/TodayScreen.tsx
    - frontend/src/screens/DuringSessionScreen.tsx
    - frontend/src/tests/session.test.tsx

key-decisions:
  - "PersistedSession.sessionId typed string | null (not string) — a free ride with no scheduled session legitimately has no linked session id; forcing non-null would require a lossy sentinel value"
  - "Added loadMatchingSession() as a new pure helper in sessionPersistence.ts rather than inlining the id/date comparison three times (TodayScreen once, DuringSessionScreen twice) — keeps the four original wrappers (loadSession/saveSession/clearSession/hasActiveSession) untouched per PATTERNS.md while avoiding triplicated, drift-prone comparison logic"
  - "DuringSessionScreen's outer freeRideDurationMins fallback now waits for the session query to resolve before trusting a persisted record (sessionLoading-gated), so a stale record read during that same reload can never leak a wrong-session freeRideDurationMins even when computeRestoredState correctly discards it"

requirements-completed: [item-01, item-08]

coverage:
  - id: D1
    description: "PersistedSession gains sessionId + date; every saveSession call site (goNext, buildPayload) writes them"
    requirement: item-01
    verification:
      - kind: unit
        ref: "frontend/src/tests/session.test.tsx#persists sessionId and date alongside step state (item 1, D-06 foundation)"
        status: pass
    human_judgment: false
  - id: D2
    description: "TodayScreen and DuringSessionScreen silently discard a persisted session whose sessionId or date does not match today's real session — no dialog, no toast, no wrong redirect"
    requirement: item-01
    verification:
      - kind: unit
        ref: "frontend/src/tests/session.test.tsx#TodayScreen stale-session mismatch guard (item 1, D-06) — 3 tests (sessionId mismatch, date mismatch, matching resumes)"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/session.test.tsx#DuringSessionScreen stale-session mismatch guard (item 1, D-06) — mismatched persisted session is discarded"
        status: pass
    human_judgment: false
  - id: D3
    description: "Live resume (tab backgrounded through 2+ completed steps) fast-forwards to the correct step and remaining time via a shared fastForwardSteps helper, matching the already-correct reload path"
    requirement: item-08
    verification:
      - kind: unit
        ref: "frontend/src/tests/session.test.tsx#fastForwardSteps + computeRestoredState (item 8) — 4 tests (single-step, multi-step, clamp-at-end, reload-path delegation)"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/session.test.tsx#DuringSessionScreen — auto-advances exactly one step... / fast-forwards through multiple elapsed steps on live resume (item 8)"
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-07
status: complete
---

# Phase 9 Plan 2: Stale-Session Hijack + Live-Resume Overshoot Fix Summary

**PersistedSession gains sessionId/date identity validated via a new loadMatchingSession() helper (silent discard, no UI per D-06), and a shared fastForwardSteps() helper makes live tab-resume fast-forward through multiple elapsed steps exactly like the already-correct reload path.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-07-07T17:31:00Z
- **Completed:** 2026-07-07T17:40:00Z
- **Tasks:** 3
- **Files modified:** 4 (3 source + 1 test file)

## Accomplishments
- `PersistedSession` now carries `sessionId: string | null` and `date: string` (YYYY-MM-DD); both `saveSession` call sites in `DuringSessionScreen.tsx` (`buildPayload`, `goNext`) write them
- `loadMatchingSession(currentSessionId)` silently discards (clearSession, no dialog/toast) any persisted record whose id or date doesn't match today's real session — wired into `TodayScreen`'s redirect guard and both `DuringSessionScreen` consumer sites (outer freeRideDurationMins fallback, `computeRestoredState`'s mount restore)
- `fastForwardSteps()` extracted from `computeRestoredState`'s while-loop and exported; the live-resume `secondsLeft===0` effect now calls it directly (instead of a bare `goNext()`), so backgrounding through 2+ steps lands on the correct step with the correct remaining time instead of silently absorbing the overshoot

## Task Commits

Each task was committed atomically (TDD RED → GREEN per task):

1. **Task 1: Add sessionId + date to PersistedSession and update all save sites**
   - `8982d19` test(09-02): add failing test for sessionId/date persistence
   - `7a51c4d` feat(09-02): add sessionId/date identity to PersistedSession
2. **Task 2: Stale-session mismatch guard in TodayScreen and DuringSessionScreen (item 1, D-06)**
   - `aac1dba` test(09-02): add failing tests for stale-session mismatch guard
   - `97118bd` feat(09-02): silently discard stale/mismatched persisted sessions
3. **Task 3: Live-resume fast-forward via shared helper (item 8)**
   - `1b7e655` test(09-02): add failing tests for live-resume multi-step fast-forward
   - `aad1aad` feat(09-02): route live-resume through shared multi-step fast-forward

_All three tasks followed the RED → GREEN cycle: a failing test was committed first, then the implementation that makes it pass._

## Files Created/Modified
- `frontend/src/lib/sessionPersistence.ts` — `PersistedSession` gains `sessionId`/`date`; adds `todayDateString()` and `loadMatchingSession()` (new pure helpers; the four original wrappers are unchanged)
- `frontend/src/screens/TodayScreen.tsx` — redirect guard now validates `loadMatchingSession(session?.id ?? null)` after the `['session','today']` query resolves, instead of unconditionally redirecting on any persisted entry
- `frontend/src/screens/DuringSessionScreen.tsx` — `fastForwardSteps()` extracted/exported and shared by `computeRestoredState` (reload path, unchanged output) and the live-resume effect (new); both `loadSession()` consumer sites now go through `loadMatchingSession()`
- `frontend/src/tests/session.test.tsx` — 9 new tests (persistence foundation, stale-session guard x4, live-resume x2, fastForwardSteps/computeRestoredState unit tests x4); also fixes a pre-existing environment gap (Node's built-in `localStorage` lacks `.clear()` under this jsdom setup) using the same in-memory mock pattern already established in `pwa.test.tsx`

## Decisions Made
- `PersistedSession.sessionId` is `string | null`, not `string` as the plan's literal wording suggested — a free ride started without a scheduled session genuinely has no linked session id, and forcing a non-null sentinel would be a lossy/hacky representation. Comparisons treat `null === null` as a match (a free ride resumes correctly when both the persisted and current session are absent).
- Added `loadMatchingSession()` as a new exported function in `sessionPersistence.ts` (not baked into the four original wrappers, and not inlined three separate times across consumers). PATTERNS.md's guidance was "the mismatch-check belongs in the consumer" — read as "don't make the raw read/write wrappers stateful/context-aware," which this satisfies, while avoiding triplicated comparison logic that could silently drift out of sync between `TodayScreen` and the two `DuringSessionScreen` call sites.
- `DuringSessionScreen`'s outer `persistedSession` (used only for the `freeRideDurationMins` iOS-relaunch fallback) now waits for `sessionLoading` to resolve before calling `loadMatchingSession`. This is a small, deliberate behavior change: on a genuinely-free-ride relaunch, the free-ride steps now appear once the (usually near-instant, often cache-hit) session query resolves rather than instantly from a synchronous `loadSession()` call — necessary so a stale/mismatched record can never leak a wrong-session `freeRideDurationMins` before validation is possible.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed jsdom `localStorage.clear` missing in this environment**
- **Found during:** Task 1 (writing the first localStorage-inspecting test)
- **Issue:** Node 25's built-in global `localStorage` (not jsdom's) was active in the test environment and lacks `.clear()`, throwing `TypeError: localStorage.clear is not a function` on the very first `localStorage.clear()` call in `beforeEach`
- **Fix:** Adopted the existing in-memory `localStorage` mock pattern already used by `pwa.test.tsx` (`vi.stubGlobal('localStorage', makeLocalStorageMock())` in `beforeEach`, `vi.unstubAllGlobals()` in `afterEach`) rather than inventing a new approach
- **Files modified:** `frontend/src/tests/session.test.tsx`
- **Verification:** All localStorage-touching tests pass; full suite green
- **Committed in:** `8982d19` (Task 1 RED commit)

**2. [Rule 1 - Bug] Stabilized the test `Wrapper`'s QueryClient across `rerender()`**
- **Found during:** Task 3 (writing the live-resume `rerender()`-based tests)
- **Issue:** The original `Wrapper` test helper called `makeQueryClient()` fresh inside its render body; calling RTL's `rerender()` on the same root (needed to force the mocked `useSessionTimer` hook to re-evaluate after advancing fake system time) would have created a new `QueryClient` each time, wiping the React Query cache mid-test
- **Fix:** `Wrapper` now lazy-initializes the client via `useState(() => makeQueryClient())` so the same client instance persists across `rerender()` calls
- **Files modified:** `frontend/src/tests/session.test.tsx`
- **Verification:** Live-resume tests pass reliably (also re-ran the full `session.test.tsx` file 3x to check for flakiness — 14/14 stable each run)
- **Committed in:** `1b7e655` (Task 3 RED commit)

**3. [Rule 3 - Blocking] `frontend/node_modules` was missing in this worktree**
- **Found during:** Task 1 (first `npx vitest run` attempt)
- **Issue:** This git worktree had no `node_modules` installed, so `vitest` couldn't resolve `vitest/config`/`@vitejs/plugin-react`
- **Fix:** Symlinked `frontend/node_modules` to the main checkout's already-installed `frontend/node_modules` (same machine, same versions per `package.json`) rather than running a fresh `npm install`. `node_modules` is gitignored, so this symlink is not part of any commit.
- **Files modified:** none (environment-only, gitignored)
- **Verification:** `npx vitest run` and `npx tsc --noEmit` both work from this worktree
- **Committed in:** n/a (not a tracked change)

---

**Total deviations:** 3 auto-fixed (1 blocking test-environment gap, 1 bug in new test infra, 1 blocking dev-environment gap). No scope creep — all three were necessary to make the plan's own verification commands runnable and its tests correct.

## Issues Encountered
- The original "auto-advances when the timer hits 0" test forced `secondsLeft` to `0` via the mock independent of real elapsed wall-clock time. Once the live-resume effect derives its action from actual `Date.now() - stepStartEpoch` math (this plan's whole point), that test's precondition became invalid — a `secondsLeft===0` signal with zero real elapsed time no longer triggers any advance. Replaced it with fake-timer scenarios where the mocked `useSessionTimer` mirrors the real hook's epoch computation, so `secondsLeft===0` is only ever asserted when it would genuinely occur. This matches RESEARCH.md's Pitfall 3 guidance (existing tests can encode buggy behavior as "expected").
- `vi.clearAllMocks()` does not reset a mock's `mockImplementation`/`mockReturnValue` (only clears call/result history) — an early attempt to manually call `mockReset()` mid-test caused a cross-test crash (`useSessionTimer()` returning `undefined` during a later unmount). Removed the manual reset; each test now sets its own explicit `mockReturnValue`/`mockImplementation`, which fully overrides prior state, so no manual reset is needed between tests.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Item 1 (D-06, stale-session hijack) and item 8 (live-resume overshoot) are both fully closed for `sessionPersistence.ts` / `TodayScreen.tsx` / `DuringSessionScreen.tsx`.
- No new UI was introduced for the discard path (verified via diff grep for `sonner`/`toast`/`AlertDialog`/`dialog` across both modified screens — none found outside a code comment).
- Full frontend suite (`npx vitest run`) is green: 89/89 tests across 11 files. `npx tsc --noEmit` is clean.
- Other Phase 9 plans (items 2-7, 9-14) touch different files (`useSSEStream.ts`, `ChatScreen.tsx`, `OnboardingScreen.tsx`, `router.tsx`, `AppLayout.tsx`, `api.ts`, `AuthCallbackScreen.tsx`, `FitUploadZone.tsx`) and are unaffected by this plan's changes.

---
*Phase: 09-frontend-resilience*
*Completed: 2026-07-07*
