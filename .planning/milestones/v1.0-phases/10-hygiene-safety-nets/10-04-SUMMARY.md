---
phase: 10-hygiene-safety-nets
plan: 04
subsystem: api
tags: [rate-limiting, fastapi, sse, dependency-injection, chat, onboarding]

# Dependency graph
requires:
  - phase: 10-hygiene-safety-nets (plan 03)
    provides: get_current_user's SSE ephemeral-token verify path, POST /chat/token, chat.py/onboarding.py current shape (this plan's Wave 2 wiring builds on top of it without conflict)
provides:
  - backend/rate_limit.py -- in-process sliding-window token bucket keyed by user_id (10 req/60s), with a non-raising is_rate_limited() for streaming endpoints and a raising rate_limited_user() FastAPI dependency for JSON endpoints
  - chat_stream (GET /chat/stream) rate-limit branch returning a single SSE error frame (code: rate_limited), never a mid-stream HTTPException
  - onboarding_start (POST /onboarding/start) now depends on rate_limited_user, returning a real HTTP 429 with a structured {"error": "rate_limited", "detail": "..."} body once over limit
  - Frontend: useSSEStream.ts and OnboardingScreen.tsx (both fetch call sites) skip the silent auto-retry and show the exact rate-limit copy when the backend signals a rate limit
affects: [phase-11-google-calendar-verification (unrelated), any future phase touching chat.py/onboarding.py/useSSEStream.ts/OnboardingScreen.tsx]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Hand-rolled in-process rate limiter (no new dependency) -- rejected slowapi per RESEARCH's package-legitimacy gate ([SUS] verdict) and its Request-only key_func design mismatch with this app's Depends(get_current_user) pattern"
    - "Streaming-safe rate-limit signaling: chat_stream returns a StreamingResponse yielding one error frame instead of raising HTTPException(429) once the 200/text-event-stream headers are already committed -- mirrors the existing _invalid_conversation_stream pattern"
    - "Frontend rate-limit short-circuit: both useSSEStream.ts's error listener and OnboardingScreen.tsx's two !res.ok branches check for the rate-limit signal BEFORE the existing silent retry-with-backoff block, so a rate limit never compounds itself via auto-retry"

key-files:
  created:
    - backend/rate_limit.py
    - tests/api/test_rate_limit.py
  modified:
    - backend/routes/chat.py
    - backend/routes/onboarding.py
    - tests/api/test_chat.py
    - tests/api/test_onboarding.py
    - frontend/src/hooks/useSSEStream.ts
    - frontend/src/screens/OnboardingScreen.tsx
    - frontend/src/tests/useSSEStream.test.ts

key-decisions:
  - "10 requests / 60 seconds per user_id (Claude's discretion per D-03) -- generous enough for normal chat/onboarding use, tight enough to stop a runaway retry loop"
  - "Keyed exclusively by post-auth user_id, never by Request/IP -- verified via grep (no get_remote_address/request.client/.host usage)"
  - "chat_stream's rate-limit branch returns a StreamingResponse with one error frame rather than raising HTTPException(429), since a 429 cannot be delivered once SSE streaming headers are committed"
  - "onboarding_start's dependency is swapped wholesale from get_current_user to rate_limited_user (rather than an additional inline check) since the endpoint returns a normal JSON/streaming response before any StreamingResponse construction, making a real HTTP 429 safe"
  - "Removed the literal string 'slowapi' from rate_limit.py's docstring after the acceptance-criteria grep gate flagged it -- context/rationale is preserved via a reference to 10-RESEARCH.md instead of naming the package inline"

requirements-completed: [ITEM-06]

coverage:
  - id: D1
    description: "backend/rate_limit.py: sliding-window token bucket keyed by user_id, non-raising is_rate_limited() and raising rate_limited_user() dependency"
    requirement: "ITEM-06"
    verification:
      - kind: unit
        ref: "tests/api/test_rate_limit.py#test_nth_plus_one_call_is_limited"
        status: pass
      - kind: unit
        ref: "tests/api/test_rate_limit.py#test_two_user_ids_have_independent_budgets"
        status: pass
      - kind: unit
        ref: "tests/api/test_rate_limit.py#test_is_rate_limited_flips_true_only_after_budget_spent"
        status: pass
      - kind: unit
        ref: "tests/api/test_rate_limit.py#test_rate_limited_user_raises_429_once_over_limit"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET /chat/stream returns a single SSE error frame (code: rate_limited) on the (N+1)th request within the window, never a mid-stream 429"
    requirement: "ITEM-06"
    verification:
      - kind: integration
        ref: "tests/api/test_chat.py#test_chat_stream_over_limit_returns_sse_rate_limited_frame"
        status: pass
    human_judgment: false
  - id: D3
    description: "POST /onboarding/start returns HTTP 429 with {\"detail\": {\"error\": \"rate_limited\", ...}} on the (N+1)th request within the window"
    requirement: "ITEM-06"
    verification:
      - kind: integration
        ref: "tests/api/test_onboarding.py#test_onboarding_start_over_limit_returns_429"
        status: pass
    human_judgment: false
  - id: D4
    description: "useSSEStream.ts's error listener skips the silent retry and surfaces the rate-limit copy immediately when code === rate_limited"
    requirement: "ITEM-06"
    verification:
      - kind: unit
        ref: "frontend/src/tests/useSSEStream.test.ts#a rate_limited error event sets the terminal error immediately and does NOT schedule a retry"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/useSSEStream.test.ts#falls back to the default rate-limit copy when the rate_limited event has no message"
        status: pass
      - kind: other
        ref: "cd frontend && npx tsc -b --noEmit"
        status: pass
    human_judgment: false
  - id: D5
    description: "OnboardingScreen.tsx's two !res.ok call sites (initial/turn stream, confirm stream) skip retry() on HTTP 429 and read the FastAPI detail body for the rate-limit message"
    requirement: "ITEM-06"
    verification:
      - kind: other
        ref: "grep -c \"429\" frontend/src/screens/OnboardingScreen.tsx (returns 4, both call sites)"
        status: pass
      - kind: other
        ref: "cd frontend && npx tsc -b --noEmit"
        status: pass
    human_judgment: true
    rationale: "No vitest harness exists for OnboardingScreen.tsx's fetch-based SSE reader (unlike useSSEStream.ts, which has a MockEventSource test harness) -- per the plan's own acceptance criteria this is covered by typecheck + source-assertion greps, not a runtime unit test. Live behavior (does the 429 banner actually render and not retry in the browser) is unverified by automation and should be spot-checked in UAT."

# Metrics
duration: 22min
completed: 2026-07-08
status: complete
---

# Phase 10 Plan 04: Rate Limiting Safety Net Summary

**Hand-rolled sliding-window token bucket (10 req/60s, keyed by user_id) protecting chat/stream and onboarding/start from runaway-retry Anthropic spend, with matching frontend skip-retry-on-rate-limit behavior.**

## Performance

- **Duration:** 22 min
- **Started:** 2026-07-08T14:50:00Z
- **Completed:** 2026-07-08T15:12:05Z
- **Tasks:** 3
- **Files modified:** 8 (2 created, 6 modified)

## Accomplishments
- `backend/rate_limit.py`: a ~65-line, dependency-free (no slowapi) in-process rate limiter -- `_check_and_record`, `is_rate_limited` (non-raising), `rate_limited_user` (raising FastAPI dependency), keyed exclusively by `user_id`
- `GET /chat/stream` now checks the limit synchronously before any streaming begins; over-limit requests receive HTTP 200 with a single SSE `error` frame (`code: rate_limited`) -- never a mid-stream 429, which would be undeliverable once streaming headers are committed
- `POST /onboarding/start` swapped its `get_current_user` dependency for `rate_limited_user`, so an over-limit request gets a real HTTP 429 with a structured, frontend-readable body
- `useSSEStream.ts` and both `OnboardingScreen.tsx` fetch call sites now special-case the rate-limit signal (SSE `code: rate_limited` / HTTP 429) to skip the existing silent auto-retry-with-backoff and go straight to the terminal `StreamErrorBanner` with the exact UI-SPEC copy

## Task Commits

Each task was committed atomically:

1. **Task 1: backend/rate_limit.py module + tests** - `c7db50b` (feat, TDD)
2. **Task 2: Wire rate limiting into chat_stream and onboarding/start** - `d09acc3` (feat)
3. **Task 3: Frontend skip-retry + rate-limit copy** - `4797beb` (feat)

**Plan metadata:** (this commit, docs)

## Files Created/Modified
- `backend/rate_limit.py` - sliding-window token bucket (`WINDOW_SECS=60`, `MAX_REQUESTS_PER_WINDOW=10`), `_check_and_record`, `is_rate_limited`, `rate_limited_user`
- `tests/api/test_rate_limit.py` - unit tests: Nth+1 rejection, independent per-user budgets, `is_rate_limited` flip, 429 detail shape
- `backend/routes/chat.py` - `chat_stream` gains a rate-limit branch (SSE error frame) before conversation_id resolution
- `backend/routes/onboarding.py` - `/start` dependency swapped from `get_current_user` to `rate_limited_user`
- `tests/api/test_chat.py` - integration test proving the (N+1)th `/chat/stream` request returns an SSE `rate_limited` error frame, plus a reset fixture
- `tests/api/test_onboarding.py` - integration test proving the (N+1)th `/onboarding/start` request returns HTTP 429, plus a reset fixture
- `frontend/src/hooks/useSSEStream.ts` - `error` listener checks `code === 'rate_limited'` before the retry-count block
- `frontend/src/screens/OnboardingScreen.tsx` - both `!res.ok` branches check `res.status === 429` before `retry()`, reading the FastAPI detail body
- `frontend/src/tests/useSSEStream.test.ts` - vitest coverage for the rate-limit skip-retry behavior and its default-copy fallback

## Decisions Made
- 10 req/60s per `user_id` as the starting threshold (Claude's discretion per D-03) -- single constant, trivially tunable later
- Rate-limit key is exclusively `user_id`, never `Request`/IP (verified via grep against `get_remote_address`/`request.client`/`.host`)
- `chat_stream`'s over-limit path returns a `StreamingResponse` (one `error` frame), never raises `HTTPException(429)`, since the 200/`text/event-stream` headers are already committed by the time an exception could fire mid-stream
- `onboarding_start`'s dependency is swapped wholesale to `rate_limited_user` rather than adding an inline check, since this endpoint's response is constructed after the dependency resolves (a real 429 is safe here, unlike `chat_stream`)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Removed the literal string "slowapi" from rate_limit.py's docstring**
- **Found during:** Task 1 (acceptance-criteria verification loop)
- **Issue:** The plan's own acceptance criterion (`grep -c "slowapi" backend/rate_limit.py requirements.txt` must return 0) failed because the module docstring explained the rejection of slowapi by name, per the RESEARCH doc's framing -- a reasonable design rationale that nonetheless tripped the literal source-assertion gate.
- **Fix:** Reworded the docstring to explain the same rationale (a rejected third-party rate-limiting library flagged by the package-legitimacy gate, and its `Request`-only `key_func` mismatch) without naming the package, pointing readers to `10-RESEARCH.md` for the specific candidate and citation.
- **Files modified:** `backend/rate_limit.py`
- **Verification:** `grep -c "slowapi" backend/rate_limit.py requirements.txt` now returns 0 for both files; `.venv/bin/pytest tests/api/test_rate_limit.py -q` still passes.
- **Committed in:** `c7db50b` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Cosmetic-only fix to satisfy a literal acceptance-criteria grep; no behavior change. No scope creep.

## Issues Encountered
- The frontend `npm run test -- --run` full suite has one pre-existing, unrelated failing test: `src/tests/session.test.tsx > DuringSessionScreen > persists sessionId and date alongside step state`. Verified this is a pre-existing test-isolation flake (passes in isolation via `npx vitest run src/tests/session.test.tsx`; fails identically even with the new `useSSEStream.test.ts` additions excluded from the run via `--exclude`). Not touched by this plan's files (`DuringSessionScreen`/session persistence is unrelated to chat/onboarding/rate-limiting); per the scope boundary this is logged, not fixed, and does not block this plan's acceptance criteria (which target `useSSEStream.test.ts` behavior specifically, which passes both in isolation and in the full run).
- Both `backend/` (`.venv`) and `frontend/` (`node_modules`) toolchains are absent from this git worktree by design (gitignored, not checked out per-worktree). Ran backend tests via the main repo's `.venv/bin/pytest` absolute path, and symlinked `frontend/node_modules` to the main repo's install to run `tsc`/`vitest` -- the symlink is itself gitignored and was not committed.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Item 6 (rate limiting) of Phase 10's 8-item scope is complete: `backend/rate_limit.py`, both endpoints wired, both frontend error paths special-cased.
- No blockers for the remaining Phase 10 plans/items.
- Flag for future UAT: the pre-existing `session.test.tsx` flake (unrelated to this plan) should be investigated separately -- likely a shared-localStorage race across parallel vitest workers, not a functional regression.

## Self-Check: PASSED

- All key-files (created + modified) verified present on disk via `[ -f ]`.
- All 4 task/summary commits (`c7db50b`, `d09acc3`, `4797beb`, `3a2f767`) verified present via `git log --oneline --all`.
- Backend: `.venv/bin/pytest tests/api/test_rate_limit.py tests/api/test_chat.py tests/api/test_onboarding.py -q` -> 23 passed. `.venv/bin/pytest tests/ -q` -> 343 passed, no regressions.
- Frontend: `cd frontend && npx tsc -b --noEmit` -> clean. `npm run test -- --run` -> 133/134 passed; the 1 failure (`session.test.tsx`) is a verified pre-existing, unrelated flake (see Issues Encountered).
- All plan acceptance-criteria greps re-verified passing (slowapi=0, user_id keying, no IP keying, `rate_limited_user`/`is_rate_limited` wiring, no mid-stream 429, frontend copy/429 greps).

---
*Phase: 10-hygiene-safety-nets*
*Completed: 2026-07-08*
