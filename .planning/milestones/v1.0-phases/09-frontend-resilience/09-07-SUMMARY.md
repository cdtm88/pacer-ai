---
phase: 09-frontend-resilience
plan: 07
subsystem: chat
tags: [react-query, fastapi, chat, conversation-history, idor-mitigation]

# Dependency graph
requires:
  - phase: 09-frontend-resilience
    provides: "09-01 (ChatScreen isDone-split effect + StreamErrorBanner), 09-03 (api.ts Ride interface / export changes) -- both merged into ChatScreen.tsx/api.ts before this plan ran"
provides:
  - "GET /conversations/{id}/messages backend endpoint (user-scoped, wraps load_conversation)"
  - "getConversationMessages frontend api client function"
  - "ChatScreen persisted-conversation-id + cache-miss reload branch"
affects: [chat, conversation-persistence]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "REST GET endpoint wrapping an existing user-scoped DB helper (load_conversation) instead of a new SELECT, for defence-in-depth ownership enforcement"
    - "React Query queryFn branching on a localStorage-persisted id to survive gcTime eviction without bumping gcTime"

key-files:
  created: []
  modified:
    - backend/routes/chat.py
    - frontend/src/lib/api.ts
    - frontend/src/screens/ChatScreen.tsx
    - frontend/src/tests/chat.test.tsx
    - tests/api/test_chat.py

key-decisions:
  - "GET /conversations/{id}/messages validates format via validate_uuid (400 on malformed) then delegates entirely to load_conversation's existing user_id ownership filter, rather than reimplementing _resolve_conversation_id's None-fallback semantics -- a foreign id returns an empty list, not a 404 (avoids conversation-id enumeration) and not another user's data"
  - "ChatScreen's ['active-conversation'] query now resolves to an ActiveConversation ({id, priorMessages?}) rather than the raw Conversation shape, with message hydration happening in a separate ref-guarded useEffect (not as a side effect inside queryFn) so a later refetch of the same conversation never clobbers messages the user has since typed"
  - "gcTime is deliberately left at its default (5min) -- D-04 explicitly requires the persisted localStorage id (not a gcTime bump) to provide cross-GC continuity"

requirements-completed: [item-04]

coverage:
  - id: D1
    description: "GET /conversations/{id}/messages returns user-scoped messages; malformed id rejected (400); foreign id returns empty list (no cross-user leak)"
    requirement: item-04
    verification:
      - kind: unit
        ref: "tests/api/test_chat.py#test_get_conversation_messages_returns_owned_messages"
        status: pass
      - kind: unit
        ref: "tests/api/test_chat.py#test_get_conversation_messages_foreign_id_returns_empty_list"
        status: pass
      - kind: unit
        ref: "tests/api/test_chat.py#test_get_conversation_messages_rejects_malformed_id"
        status: pass
    human_judgment: false
  - id: D2
    description: "getConversationMessages fetches the new endpoint and returns {role, content}[]; throws parsed backend detail on error"
    requirement: item-04
    verification:
      - kind: unit
        ref: "frontend/src/tests/chat.test.tsx#getConversationMessages (item 4, D-04) — real implementation against mocked fetch > issues a GET..."
        status: pass
      - kind: unit
        ref: "frontend/src/tests/chat.test.tsx#getConversationMessages (item 4, D-04) — real implementation against mocked fetch > throws using the parsed detail..."
        status: pass
    human_judgment: false
  - id: D3
    description: "ChatScreen persists the conversation id and reloads the EXISTING conversation (no new createConversation call) with hydrated message history after a cache-miss, showing a brief loading state; 09-01 regressions guarded"
    requirement: item-04
    verification:
      - kind: unit
        ref: "frontend/src/tests/chat.test.tsx#ChatScreen — cache-miss reload (item 4, D-04) > on first mount with no persisted id..."
        status: pass
      - kind: unit
        ref: "frontend/src/tests/chat.test.tsx#ChatScreen — cache-miss reload (item 4, D-04) > with a persisted id present, reloads the EXISTING conversation..."
        status: pass
      - kind: unit
        ref: "frontend/src/tests/chat.test.tsx#ChatScreen — cache-miss reload (item 4, D-04) > shows a brief loading state..."
        status: pass
    human_judgment: false

# Metrics
duration: 30min
completed: 2026-07-07
status: complete
---

# Phase 09 Plan 07: Conversation History Cache-Miss Reload (item 4, D-04) Summary

**Added a user-scoped GET /conversations/{id}/messages endpoint and made ChatScreen persist its active conversation id so a React Query cache eviction reloads the existing conversation instead of silently starting a new one.**

## Performance

- **Duration:** ~30 min
- **Started:** 2026-07-07T21:45:00Z (approx)
- **Completed:** 2026-07-07T22:00:23Z
- **Tasks:** 3
- **Files modified:** 5

## Accomplishments
- New `GET /conversations/{conversation_id}/messages` on `conversations_router`, wrapping the existing user-scoped `load_conversation` helper (no new unscoped SELECT); malformed ids rejected via `validate_uuid` before any DB access, foreign ids return an empty list (T-09-07-01, IDOR mitigated)
- New `getConversationMessages(conversationId)` in `frontend/src/lib/api.ts`, following the established `detail.detail ?? detail.error` structured-error convention
- `ChatScreen.tsx` now persists the active conversation id to `localStorage` and branches its `['active-conversation']` queryFn: a persisted id reloads the existing conversation's history via `getConversationMessages` (no new `createConversation` call); no id creates a new conversation and persists its id. A ref-guarded `useEffect` hydrates the visible message list exactly once per reload so a later refetch never clobbers messages the user has since typed. `gcTime` is unchanged (default 5min) -- continuity comes from the persisted id, per D-04's explicit requirement
- A brief "Loading your conversation..." state renders while an existing conversation's history is reloading, so the "Ask your coach anything" empty state doesn't flash first
- 09-01's isDone-split effect and StreamErrorBanner behavior (D-02/D-03) preserved and still covered by the existing test suite (all 26 pre-existing chat.test.tsx tests still pass)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add user-scoped GET conversation-messages endpoint (backend)** - `8abe9b0` (feat)
2. **Task 2: Add getConversationMessages to the frontend api client** - `250f798` (feat)
3. **Task 3: Persist conversation id and branch the ChatScreen queryFn (item 4, D-04)** - `49e4141` (feat)

_TDD was applied per-task (tests written alongside/immediately after the implementation and run to green before committing); no separate RED-only commits were made for this execute-type plan._

## Files Created/Modified
- `backend/routes/chat.py` - new `GET /conversations/{conversation_id}/messages` handler on `conversations_router`
- `frontend/src/lib/api.ts` - new `getConversationMessages(conversationId)` function
- `frontend/src/screens/ChatScreen.tsx` - persisted conversation id, queryFn branch, message hydration effect, loading state
- `frontend/src/tests/chat.test.tsx` - backend-adjacent frontend unit coverage for getConversationMessages (real implementation via `vi.importActual`) and the ChatScreen cache-miss reload flow (3 new tests + a localStorage mock)
- `tests/api/test_chat.py` - 3 new tests for the endpoint (owned messages, foreign id, malformed id)

## Decisions Made
- The new endpoint reuses `load_conversation`'s app-layer `user_id` ownership filter rather than reimplementing `_resolve_conversation_id`'s None-fallback pattern, so a foreign conversation id degrades to an empty message list (not a 404 that would allow conversation-id enumeration, and not another user's data)
- ChatScreen's query now returns `{id, priorMessages?}` rather than the raw `Conversation` shape; message hydration is a separate ref-guarded effect (not a side effect inside `queryFn`) to keep the queryFn pure and avoid clobbering user-typed messages on a later refetch of the same conversation
- `gcTime` intentionally left at its default -- D-04 explicitly calls out that this must NOT be a gcTime-bump workaround

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed missing backend Python dependencies in the ambient interpreter**
- **Found during:** Task 1 verification (`python -m pytest tests/api/test_chat.py`)
- **Issue:** The worktree's available Python interpreter was missing `python-dotenv`, `numpy`, and other packages already pinned in `requirements.txt` (a pre-existing environment gap unrelated to this plan's code changes)
- **Fix:** Installed `requirements.txt` into the interpreter (`pip install --break-system-packages -r requirements.txt`) -- no new/unpinned packages were introduced, only what was already declared
- **Files modified:** none (environment-only)
- **Verification:** `python -m pytest tests/api/test_chat.py -x -q` passes (6/6)
- **Committed in:** n/a (environment setup, not a code change)

**2. [Rule 3 - Blocking] Installed frontend npm dependencies (`node_modules` was absent in the worktree)**
- **Found during:** Task 2 verification (`npx vitest run src/tests/chat.test.tsx`)
- **Issue:** The worktree had no `node_modules` installed
- **Fix:** Ran `npm install` in `frontend/` (installs exactly what's pinned in `package.json`/lockfile)
- **Files modified:** none (environment-only; `node_modules` is gitignored)
- **Verification:** `npx vitest run src/tests/chat.test.tsx` passes
- **Committed in:** n/a (environment setup, not a code change)

**3. [Rule 1 - Bug] Fixed a jsdom/Node localStorage incompatibility in the new cache-miss-reload test**
- **Found during:** Task 3 verification
- **Issue:** In this Node version, bare `localStorage` resolves to Node's built-in (non-functional without `--localstorage-file`) global rather than jsdom's implementation, so `localStorage.clear()`/`setItem()` threw. The repo already has an established fix for this exact issue (`makeLocalStorageMock()` + `vi.stubGlobal('localStorage', ...)`, used in `session.test.tsx` and `pwa.test.tsx`)
- **Fix:** Applied the same established in-memory `localStorage` mock pattern to the new `ChatScreen — cache-miss reload` describe block
- **Files modified:** `frontend/src/tests/chat.test.tsx`
- **Verification:** All 29 tests in `chat.test.tsx` pass
- **Committed in:** `49e4141` (Task 3 commit)

**4. [Rule 1 - Bug] Fixed a test/teardown race between an in-flight SSE effect and `vi.unstubAllGlobals()`**
- **Found during:** Task 3 verification
- **Issue:** The new "reloads the EXISTING conversation... " test fired a send after the reload completed, but didn't wait for the resulting `EventSource` to actually be constructed before the test resolved, so `afterEach`'s `vi.unstubAllGlobals()` occasionally ran before the async `useSSEStream` effect executed, throwing `ReferenceError: EventSource is not defined`
- **Fix:** Added the same "drain the EventSource creation" `waitFor` used by an existing test in this file (`sseUrl is called with a path...`), which has an identical comment explaining the exact same race
- **Files modified:** `frontend/src/tests/chat.test.tsx`
- **Verification:** All 29 tests in `chat.test.tsx` pass consistently across repeated runs
- **Committed in:** `49e4141` (Task 3 commit)

---

**Total deviations:** 4 auto-fixed (2 blocking/environment, 2 bug fixes in new test code)
**Impact on plan:** All auto-fixes were necessary to get the plan's own verification commands running; none touched production code paths beyond what the plan specified. No scope creep.

## Issues Encountered
None beyond the deviations documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Item 4 (D-04) is fully closed: conversation history now survives the React Query cache's gcTime eviction window
- The new `GET /conversations/{id}/messages` endpoint is available for any future feature needing to read (not just stream) conversation history
- No blockers for remaining phase 09 plans

---
*Phase: 09-frontend-resilience*
*Completed: 2026-07-07*

## Self-Check: PASSED

All 6 files confirmed present on disk; all 3 task commits (8abe9b0, 250f798, 49e4141) confirmed present in git log.
