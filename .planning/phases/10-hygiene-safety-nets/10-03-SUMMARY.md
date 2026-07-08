---
phase: 10-hygiene-safety-nets
plan: 03
subsystem: auth
tags: [jwt, sse, pyjwt, fastapi, eventsource, security]

# Dependency graph
requires:
  - phase: 04
    provides: get_current_user JWT dependency and the SSE chat/stream endpoint this plan extends
provides:
  - "POST /chat/token ephemeral SSE token exchange endpoint"
  - "get_current_user query-param branch that verifies namespaced sse_token before Supabase paths"
  - "sseUrl() frontend helper that carries only an ephemeral token in the SSE URL"
affects: [chat, sse, auth, security-hardening]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Ephemeral, stateless, namespaced token exchange for EventSource auth (typ claim guard, dedicated secret, exp-only enforcement, no durable state)"

key-files:
  created:
    - tests/api/test_chat_token.py
  modified:
    - backend/routes/chat.py
    - backend/auth.py
    - frontend/src/lib/api.ts
    - .env.example

key-decisions:
  - "Used a NEW dedicated SSE_TOKEN_SECRET (never SUPABASE_JWT_SECRET) so the ephemeral-token path works regardless of whether the deployment uses ES256/JWKS or legacy HS256 Supabase verification"
  - "Namespaced the ephemeral token with typ: sse_token as a claim-level guard so it can never cross-validate with a real Supabase JWT"
  - "Stateless design per D-04: exp (~60s) is the sole enforcement mechanism, no DB/cache row for revocation or single-use tracking"

patterns-established:
  - "Query-param-only auth branch inserted before existing verification chain in get_current_user, falling through unchanged on any failure -- backward compatible extension pattern for FastAPI Depends() chains"

requirements-completed: [ITEM-05]

coverage:
  - id: D1
    description: "POST /chat/token mints a short-lived (~60s) namespaced token for an authenticated caller and rejects unauthenticated requests"
    requirement: "ITEM-05"
    verification:
      - kind: unit
        ref: "tests/api/test_chat_token.py#test_issue_sse_token_returns_short_lived_token"
        status: pass
      - kind: unit
        ref: "tests/api/test_chat_token.py#test_issue_sse_token_requires_auth"
        status: pass
    human_judgment: false
  - id: D2
    description: "GET /chat/stream authenticates via the ephemeral sse_token on ?token=, and a real Supabase JWT never validates as an sse_token (namespace guard)"
    requirement: "ITEM-05"
    verification:
      - kind: unit
        ref: "tests/api/test_chat_token.py#test_stream_accepts_ephemeral_sse_token"
        status: pass
      - kind: unit
        ref: "tests/api/test_chat_token.py#test_real_supabase_jwt_is_not_an_sse_token"
        status: pass
    human_judgment: false
  - id: D3
    description: "Existing Bearer-header and Supabase HS256/ES256 auth paths are unregressed by the new branch"
    requirement: "ITEM-05"
    verification:
      - kind: unit
        ref: "tests/api/test_chat.py (13 tests)"
        status: pass
      - kind: unit
        ref: "tests/api/test_auth.py (all tests)"
        status: pass
    human_judgment: false
  - id: D4
    description: "sseUrl() exchanges the Supabase JWT for an ephemeral token before opening EventSource; frontend typechecks cleanly"
    requirement: "ITEM-05"
    verification:
      - kind: integration
        ref: "cd frontend && npx tsc -b --noEmit"
        status: pass
    human_judgment: false

# Metrics
duration: 35min
completed: 2026-07-08
status: complete
---

# Phase 10 Plan 03: SSE Ephemeral Token Exchange Summary

**Short-lived, namespaced `sse_token` exchange (`POST /chat/token`) replaces the full Supabase JWT in `GET /chat/stream?token=`, closing the T-10-03-01 access-log leak.**

## Performance

- **Duration:** 35 min
- **Started:** 2026-07-08T00:00:00Z (approx, see commit timestamps)
- **Completed:** 2026-07-08
- **Tasks:** 3 completed (RED test task, TDD implementation task, frontend integration task)
- **Files modified:** 5 (1 created, 4 modified)

## Accomplishments
- `tests/api/test_chat_token.py` specifies the full token-exchange contract: mint shape, auth requirement, ephemeral-token acceptance on `/stream`, and the sse_token <-> Supabase-JWT namespace guard (RED before implementation, GREEN after)
- `POST /chat/token` (backend/routes/chat.py) mints a ~60s HS256 token signed with a new dedicated `SSE_TOKEN_SECRET`, namespaced with `typ: "sse_token"`; missing secret returns HTTP 500 rather than an unsigned token
- `get_current_user` (backend/auth.py) tries the sse_token verify path first on the query-param branch only, falling through unchanged to the existing ES256/HS256 Supabase paths on any failure -- the Bearer-header path is untouched
- `sseUrl()` (frontend/src/lib/api.ts) now exchanges the real Supabase JWT for the ephemeral token via `POST /api/chat/token` and carries only that token in the SSE URL; the raw `supabase.auth.getSession()` read was removed from `sseUrl`
- `.env.example` documents the new `SSE_TOKEN_SECRET` var with a generation comment

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 — failing tests for POST /chat/token and the SSE-token verify path** - `377615d` (test)
2. **Task 2: Implement POST /chat/token and extend get_current_user's query-param branch** - `74452c1` (feat, TDD GREEN)
3. **Task 3: Update sseUrl() to exchange for an ephemeral token before opening EventSource** - `d2e0492` (feat)

_Note: Task 2 is a `tdd="true"` task; RED was established in Task 1's commit (`377615d`), GREEN lands in `74452c1`. No separate refactor commit was needed._

## Files Created/Modified
- `tests/api/test_chat_token.py` - New test file specifying the token-exchange contract (4 tests)
- `backend/routes/chat.py` - New `POST /token` handler (`issue_sse_token`), mounts as `POST /chat/token`
- `backend/auth.py` - New query-param-only sse_token verify branch in `get_current_user`
- `frontend/src/lib/api.ts` - `sseUrl()` rewritten to perform the token exchange
- `.env.example` - New `SSE_TOKEN_SECRET=` placeholder with generation comment

## Decisions Made
- Dedicated `SSE_TOKEN_SECRET` (not a reuse of `SUPABASE_JWT_SECRET`) to remain independent of whether a given deployment relies on ES256/JWKS or legacy HS256 Supabase verification (per 10-RESEARCH.md Pattern 3 rationale)
- `typ: "sse_token"` claim namespace guard rather than a separate verification function, to keep the extension minimal and localized to the existing `get_current_user` fallback chain
- No durable state (DB/cache row) for the ephemeral token per D-04 -- the `exp` claim (~60s) is the sole enforcement; replay within that window is an accepted risk (T-10-03-04, medium severity, single-user app)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created a local `.venv` symlink and `frontend/node_modules` symlink in the worktree**
- **Found during:** Task 1 (running `.venv/bin/pytest` for the first time)
- **Issue:** This plan runs inside a git worktree, which does not carry the gitignored `.venv/` (Python) or `frontend/node_modules/` directories from the main repo checkout. Neither existed in the worktree, blocking all `<verify>` commands.
- **Fix:** Symlinked both from the main repo checkout (`ln -s /Users/christianmoore/ai/pacer-ai/.venv .venv` and the equivalent for `frontend/node_modules`) so the plan's exact verification commands (`.venv/bin/pytest ...`, `npx tsc -b --noEmit`) could run unmodified. Both symlinks were removed after verification completed, before writing this SUMMARY, to leave a clean working tree (`frontend/node_modules` is gitignored regardless; `.venv` as a symlink is not matched by the `.venv/`-only gitignore pattern, so it was explicitly deleted rather than left untracked).
- **Files modified:** None (symlinks only, never staged or committed)
- **Verification:** `git status --short` shows a clean tree after cleanup; all task commits contain only the intended source/test files.
- **Commit:** N/A (not committed; removed before final SUMMARY commit)

---

**Total deviations:** 1 auto-fixed (1 blocking, environment-only)
**Impact on plan:** No impact on shipped code. Purely a local test-environment workaround required by worktree isolation; no production files were affected.

## Issues Encountered
- `tests/agent/test_sse.py` has 8 pre-existing failures (`TestSSEEventSequence` class) unrelated to this plan's files -- these are explicitly called out in `10-PATTERNS.md` as a separate fix item ("fix 8 stale tests") for a different plan in this phase. Verified via `git diff` that none of this plan's commits touch `tests/agent/test_sse.py`; left untouched per the scope-boundary rule.

## User Setup Required

**External services require manual configuration.**
- **New env var:** `SSE_TOKEN_SECRET` must be generated (`openssl rand -hex 32`) and added to:
  - Local `.env` (placeholder already added to `.env.example`)
  - Vercel Project Settings -> Environment Variables (Production + Preview), for the backend Function
- Production cannot mint SSE ephemeral tokens (`POST /chat/token` will return HTTP 500) until this variable is set in the Vercel environment.

## Next Phase Readiness
- The SSE token-exchange path is fully implemented and tested; `GET /chat/stream` no longer requires the full Supabase JWT in its query string once `sseUrl()` is used by the frontend (already wired, no `ChatScreen.tsx` changes needed).
- Blocker for production: `SSE_TOKEN_SECRET` must be set in Vercel before this deploys (see User Setup Required above) -- otherwise `POST /chat/token` returns 500 and SSE chat will fail end-to-end in production.
- No blockers for continuing with other phase 10 plans; this plan's files (`backend/auth.py`, `backend/routes/chat.py`, `frontend/src/lib/api.ts`) do not overlap with the rate-limiting or stale-test-fix work described elsewhere in `10-PATTERNS.md`.

---
*Phase: 10-hygiene-safety-nets*
*Completed: 2026-07-08*
