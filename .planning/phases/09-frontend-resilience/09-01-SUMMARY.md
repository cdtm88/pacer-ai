---
phase: 09-frontend-resilience
plan: 01
subsystem: ui
tags: [react, sse, eventsource, chat, resilience, vitest]

requires: []
provides:
  - "StreamErrorBanner shared component (chat + onboarding, reused by 09-06)"
  - "useSSEStream silent retry-with-backoff (500ms/1500ms, MAX_RETRIES=2)"
  - "ChatScreen terminal-error banner + manual Retry"
  - "ChatScreen empty-done-swallow fix (D-03 unbrick)"
affects: [09-06-onboarding-resilience]

tech-stack:
  added: []
  patterns:
    - "Retry-with-backoff loop declared inside the useEffect closure (openStream() function, retryCount/MAX_RETRIES/BACKOFF_MS as closure vars) so state resets naturally per new url"
    - "Terminal stream error clears activeStreamUrl via a dedicated useEffect keyed on [error], separate from the isDone effect -- keeps the isStreaming derivation formula unchanged while making it resolve correctly"
    - "Shared StreamErrorBanner component with a variant prop (chat: borderTop / onboarding: full border+borderRadius) instead of two separate banner components"

key-files:
  created:
    - frontend/src/components/chat/StreamErrorBanner.tsx
    - frontend/src/tests/StreamErrorBanner.test.tsx
  modified:
    - frontend/src/hooks/useSSEStream.ts
    - frontend/src/tests/useSSEStream.test.ts
    - frontend/src/screens/ChatScreen.tsx
    - frontend/src/tests/chat.test.tsx

key-decisions:
  - "Test file path correction: plan frontmatter/task <files> listed frontend/src/hooks/useSSEStream.test.ts, but the actual (pre-existing) test file lives at frontend/src/tests/useSSEStream.test.ts (matching the plan's own <verify> commands and the project's established test-directory convention). Modified the real file, not a new one."
  - "ChatScreen's terminal-error banner shows the fixed copy 'Connection failed.' (per UI-SPEC Copywriting Contract) rather than the raw hook error message, closing threat T-09-01-02 (no backend exception text surfaced to the user)"
  - "activeStreamUrl is cleared on terminal error via a new effect keyed on [error], not by changing the isStreaming formula itself -- per the plan's explicit instruction to keep 'isStreaming = activeStreamUrl !== null && !isDone' unchanged"
  - "pendingUserMessage is deliberately NOT cleared when a terminal error occurs (only on isDone) so Retry can re-derive the exact same request"

patterns-established:
  - "Shared error-banner component pattern (StreamErrorBanner) for both SSE consumers in this codebase, established for 09-06 to reuse verbatim"

requirements-completed: [item-02, item-03]

coverage:
  - id: D1
    description: "useSSEStream retries silently up to 2x (500ms/1500ms backoff) before surfacing any error"
    requirement: item-02
    verification:
      - kind: unit
        ref: "frontend/src/tests/useSSEStream.test.ts#a single error event does NOT call setError immediately -- it retries after backoff"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/useSSEStream.test.ts#after MAX_RETRIES (2) consecutive error events, setError fires with the terminal message and isThinking is false"
        status: pass
    human_judgment: false
  - id: D2
    description: "Terminal chat stream error renders StreamErrorBanner with manual Retry and re-enables input; stale permanent Reconnecting banner removed"
    requirement: item-02
    verification:
      - kind: unit
        ref: "frontend/src/tests/chat.test.tsx#terminal stream error (after retries exhaust) renders StreamErrorBanner with Retry, and the input re-enables"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/chat.test.tsx#clicking Retry re-derives the stream URL from the last sent message and re-enters streaming, clearing the banner"
        status: pass
    human_judgment: false
  - id: D3
    description: "Tool-only turn (done with empty content) clears activeStreamUrl silently and unbricks a subsequent send"
    requirement: item-03
    verification:
      - kind: unit
        ref: "frontend/src/tests/chat.test.tsx#a done event with empty content (tool-only turn) clears activeStreamUrl silently and unbricks a subsequent send"
        status: pass
    human_judgment: false
  - id: D4
    description: "StreamErrorBanner shared component renders message + Retry button, styled per 09-UI-SPEC.md, reusable by onboarding (09-06)"
    verification:
      - kind: unit
        ref: "frontend/src/tests/StreamErrorBanner.test.tsx"
        status: pass
    human_judgment: false

duration: 18min
completed: 2026-07-07
status: complete
---

# Phase 09 Plan 01: Chat SSE Resilience Summary

**Silent retry-with-backoff inside useSSEStream (2x, 500ms/1500ms), a shared StreamErrorBanner component, and a split isDone effect that always clears activeStreamUrl -- fixing both the permanent-brick chat error banner and the tool-only-turn input lockup.**

## Performance

- **Duration:** 18 min
- **Completed:** 2026-07-07T17:27:40Z
- **Tasks:** 3
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments
- `useSSEStream` now retries silently up to 2 times (500ms then 1500ms backoff) on a transient `error` event before ever calling `setError`; the `streamCompleted` guard and `done` handler are unchanged.
- New shared `StreamErrorBanner` component (`chat` and `onboarding` variants) renders per 09-UI-SPEC.md exactly -- lucide `AlertCircle`/`RotateCw`, inline `--color-*` styling, no shadcn `Button` variant dependency.
- `ChatScreen`'s isDone effect is split: it ALWAYS clears `activeStreamUrl`/`pendingUserMessage` on `isDone`, and only pushes a coach message when `content` is non-empty -- closing the D-03 silent-brick bug where a tool-only turn left `handleSend`'s guard permanently blocking future sends.
- A new effect clears `activeStreamUrl` when the hook surfaces a terminal `error`, so `isStreaming` correctly resolves to `false` and the input re-enables; `StreamErrorBanner`'s Retry re-derives the SSE URL from `pendingUserMessage` (preserved across the error, only cleared on `isDone`).
- The stale `chat.test.tsx` test asserting the old permanent "Connection lost. Reconnecting..." banner (Pitfall 3) was rewritten; no test in the suite now asserts that string as expected behavior.

## Task Commits

Each task was committed atomically (TDD RED -> GREEN per task):

1. **Task 1: Build the shared StreamErrorBanner component**
   - `a9164a0` test(09-01): add failing test for StreamErrorBanner component
   - `02e4481` feat(09-01): implement shared StreamErrorBanner component
2. **Task 2: Add silent retry-with-backoff inside useSSEStream (item 2, D-02)**
   - `a12e984` test(09-01): add failing tests for useSSEStream retry-with-backoff
   - `468378d` feat(09-01): add silent retry-with-backoff to useSSEStream (D-02)
3. **Task 3: Wire ChatScreen terminal error + Retry, and fix empty-done swallow (items 2 and 3)**
   - `5e1f0ac` test(09-01): rewrite stale reconnecting test, add empty/non-empty-done and terminal-error tests
   - `f63007c` feat(09-01): wire ChatScreen terminal error banner + Retry, fix empty-done swallow (D-02, D-03)

**Plan metadata:** committed alongside this SUMMARY (see final commit list in completion message).

## Files Created/Modified
- `frontend/src/components/chat/StreamErrorBanner.tsx` - NEW shared terminal-error banner (message + Retry button), `variant` prop for chat/onboarding border treatment
- `frontend/src/tests/StreamErrorBanner.test.tsx` - NEW unit tests for the banner component
- `frontend/src/hooks/useSSEStream.ts` - added `openStream()`/`retryCount`/`MAX_RETRIES`/`BACKOFF_MS` retry loop inside the effect closure
- `frontend/src/tests/useSSEStream.test.ts` - replaced immediate-setError tests with retry/backoff/terminal-error/retryCount-reset tests
- `frontend/src/screens/ChatScreen.tsx` - split isDone effect, new error-clears-activeStreamUrl effect, `handleRetry`, `StreamErrorBanner` wired in place of the static banner
- `frontend/src/tests/chat.test.tsx` - rewrote the stale "Reconnecting..." test; added empty-done, non-empty-done, terminal-error, and Retry-click tests

## Decisions Made
- Used the actual pre-existing test file path (`frontend/src/tests/useSSEStream.test.ts`) rather than the plan frontmatter's stated `frontend/src/hooks/useSSEStream.test.ts`, since that path does not exist in this codebase and the plan's own `<verify>` commands already point at `src/tests/`.
- ChatScreen's error banner always shows the fixed copy "Connection failed." (per UI-SPEC), not the raw backend message text, closing the informational-disclosure threat noted in the plan's threat model (T-09-01-02).
- Kept `isStreaming = activeStreamUrl !== null && !isDone` as a literal, unmodified formula (per plan instruction) and instead added a dedicated `useEffect(() => { if (error) setActiveStreamUrl(null) }, [error])` so the formula resolves correctly once retries are exhausted.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed frontend npm dependencies**
- **Found during:** Task 1 (running the first test)
- **Issue:** `frontend/node_modules` did not exist in this worktree; `npx vitest` failed with `ERR_MODULE_NOT_FOUND` for `vitest`/`@vitejs/plugin-react`.
- **Fix:** Ran `npm install` in `frontend/` (project's already-declared `package.json`/`package-lock.json`, no new packages added or versions changed).
- **Files modified:** None tracked (`frontend/node_modules` is gitignored).
- **Verification:** `npx vitest run` subsequently executed successfully.
- **Committed in:** N/A (gitignored, nothing to commit)

**2. [Rule 1 - Bug] Corrected the plan's stated useSSEStream test file path**
- **Found during:** Task 2 (locating the test file named in the plan)
- **Issue:** Plan frontmatter/task `<files>` listed `frontend/src/hooks/useSSEStream.test.ts`, which does not exist; the real, git-tracked file is `frontend/src/tests/useSSEStream.test.ts` (matching the plan's own `<verify>` shell commands).
- **Fix:** Edited the real file at `frontend/src/tests/useSSEStream.test.ts`.
- **Files modified:** `frontend/src/tests/useSSEStream.test.ts`
- **Verification:** `npx vitest run src/tests/useSSEStream.test.ts` green (15/15).
- **Committed in:** `a12e984`, `468378d`

---

**Total deviations:** 2 auto-fixed (1 blocking dependency install, 1 path correction)
**Impact on plan:** Both were necessary to execute the plan at all; no scope creep, no behavior beyond what the plan specified.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- `StreamErrorBanner` is ready for plan 09-06 (onboarding) to import and reuse via its `variant="onboarding"` prop, per D-05's UX-consistency intent.
- The retry-with-backoff *policy* (not the `EventSource` transport) established here (`retryCount`/`MAX_RETRIES=2`/`BACKOFF_MS=[500,1500]`) is the pattern 09-06 should mirror inside `OnboardingScreen.tsx`'s fetch-based `runStream`/`handleConfirm` catch branches, per RESEARCH.md Pitfall 1 / Open Question 1.
- Full frontend suite (`npx vitest run`) green: 90/90 tests, 12 files, confirmed after this plan's changes.

---
*Phase: 09-frontend-resilience*
*Completed: 2026-07-07*
