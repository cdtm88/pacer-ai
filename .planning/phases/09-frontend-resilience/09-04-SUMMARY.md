---
phase: 09-frontend-resilience
plan: 04
subsystem: auth
tags: [react-router, supabase, pkce, react-query, error-boundary, asvs]

# Dependency graph
requires:
  - phase: 04-ui-and-calendar
    provides: router.tsx route tree, AppLayout nav shell, useAuth/authStore auth plumbing
provides:
  - Per-route error boundary (RouteErrorFallback) wired onto all 5 AppLayout leaf routes
  - queryClient.clear() on SIGNED_IN (cross-account cache-bleed fix)
  - Single-consumption AuthCallbackScreen (store-watch + timeout, no manual exchangeCodeForSession)
affects: [09-05, 09-06, 09-07, 10-hygiene-and-safety-nets]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "React Router ErrorBoundary route-config property (not errorElement) for per-route crash isolation"
    - "onAuthStateChange event-taxonomy discipline: extend OR-chains by exact event name, never TOKEN_REFRESHED/INITIAL_SESSION"
    - "Auth callback screens watch the auth store instead of performing their own token/code exchange"

key-files:
  created:
    - frontend/src/components/ErrorBoundaryFallback.tsx
    - frontend/src/tests/routerErrorBoundary.test.tsx
  modified:
    - frontend/src/router.tsx
    - frontend/src/screens/AuthCallbackScreen.tsx
    - frontend/src/tests/auth.test.tsx

key-decisions:
  - "ErrorBoundary attached individually to each of the 5 AppLayout leaf routes (not once on AppLayout itself) per RESEARCH.md Pattern 3, sharing one RouteErrorFallback component"
  - "SIGNED_IN added to the existing SIGNED_OUT/USER_UPDATED OR-chain; TOKEN_REFRESHED and INITIAL_SESSION explicitly excluded (Pitfall 5) to avoid wiping the cache on silent token refresh"
  - "AuthCallbackScreen's PKCE branch rewritten to watch authStore (subscribe + immediate check) with a 6s timeout fallback to /login; implicit-flow (hash token) branch left untouched per RESEARCH.md guidance since getSession() there is idempotent"

patterns-established:
  - "Distinguish two onAuthStateChange listener registrations in tests by callback arity (RootProvider's single-arg vs useAuth's two-arg) rather than call order"

requirements-completed: [item-10, item-11, item-12]

coverage:
  - id: D1
    description: "Router error boundary: a leaf-route render crash shows a minimal 'Something went wrong' + Reload fallback with no error detail, while the AppLayout nav shell stays mounted"
    requirement: "item-12"
    verification:
      - kind: unit
        ref: "frontend/src/tests/routerErrorBoundary.test.tsx#renders the minimal fallback instead of white-screening when a leaf route throws"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/routerErrorBoundary.test.tsx#keeps the AppLayout nav shell mounted when a child route crashes (D-10)"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/routerErrorBoundary.test.tsx#renders no error message/stack detail (D-09)"
        status: pass
    human_judgment: false
  - id: D2
    description: "queryClient.clear() fires on SIGNED_IN (and still on SIGNED_OUT/USER_UPDATED) but not on TOKEN_REFRESHED, preventing cross-account cached data from rendering after a new sign-in"
    requirement: "item-10"
    verification:
      - kind: unit
        ref: "frontend/src/tests/auth.test.tsx#RootProvider query cache clear on auth transitions (item 10, ASVS V3) > clears the query cache on SIGNED_IN"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/auth.test.tsx#RootProvider query cache clear on auth transitions (item 10, ASVS V3) > does NOT clear the query cache on TOKEN_REFRESHED (Pitfall 5)"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/auth.test.tsx#RootProvider query cache clear on auth transitions (item 10, ASVS V3) > still clears the query cache on SIGNED_OUT and USER_UPDATED"
        status: pass
    human_judgment: false
  - id: D3
    description: "AuthCallbackScreen consumes the PKCE code exactly once (no manual exchangeCodeForSession); a resolved session navigates home, an unresolved one times out to /login"
    requirement: "item-11"
    verification:
      - kind: unit
        ref: "frontend/src/tests/auth.test.tsx#AuthCallbackScreen single code-consumption (item 11, ASVS V2) > navigates to / (replace) once a session appears in the store, without calling exchangeCodeForSession"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/auth.test.tsx#AuthCallbackScreen single code-consumption (item 11, ASVS V2) > navigates to /login when no session resolves within the timeout"
        status: pass
      - kind: unit
        ref: "frontend/src/tests/auth.test.tsx#AuthCallbackScreen single code-consumption (item 11, ASVS V2) > never calls exchangeCodeForSession, even immediately on mount"
        status: pass
    human_judgment: false

# Metrics
duration: 4min
completed: 2026-07-07
status: complete
---

# Phase 09 Plan 04: Auth/Router Hardening Summary

**Cross-account query-cache bleed closed (SIGNED_IN cache clear), PKCE double-exchange login-bounce eliminated, and per-route error boundaries added to all 5 AppLayout leaf routes with a shared minimal fallback.**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-07-07T21:22:00Z (approx, first RED test run)
- **Completed:** 2026-07-07T21:26:54Z
- **Tasks:** 3
- **Files modified:** 5 (2 new, 3 modified)

## Accomplishments
- Added `RouteErrorFallback` component and wired `ErrorBoundary` onto all 5 `AppLayout` leaf routes (index/agenda/history/chat/settings) — a screen crash now shows a minimal contained fallback instead of white-screening the whole app, and the nav shell (bottom tab bar / desktop sidebar / header) stays mounted and navigable.
- Extended `RootProvider`'s `onAuthStateChange` OR-chain with `'SIGNED_IN'` so `queryClient.clear()` fires on sign-in, sign-out, and user-update, closing the cross-account cache-bleed hole (a previous account's cached data could otherwise render after a new sign-in). `TOKEN_REFRESHED`/`INITIAL_SESSION` are explicitly excluded so silent token refresh doesn't wipe the cache.
- Deleted `AuthCallbackScreen`'s manual `exchangeCodeForSession(code)` call, which was racing `supabase.ts`'s `detectSessionInUrl: true` background exchange and could bounce a user with a genuinely valid session to `/login`. Replaced it with a store-watch (subscribe + immediate check) that reacts once `useAuth.ts`'s existing global `onAuthStateChange` populates the session, plus a 6-second timeout fallback to `/login` for a truly invalid/expired code.

## Task Commits

Each task was committed atomically:

1. **Task 1: Router error boundary — fallback component + per-route wiring (item 12, D-09/D-10)** - `5ab8e33` (feat)
2. **Task 2: Clear query cache on SIGNED_IN (item 10, ASVS V3)** - `d0031d1` (fix)
3. **Task 3: Single code-consumption in AuthCallbackScreen (item 11, ASVS V2)** - `3437760` (fix)

_No separate RED/GREEN/REFACTOR commits — tests and implementation were verified locally per task (RED confirmed before each fix) but committed together per task per this plan's `tdd="true"` task-level convention, matching the codebase's existing single-commit-per-task pattern._

## Files Created/Modified
- `frontend/src/components/ErrorBoundaryFallback.tsx` - New `RouteErrorFallback` component; reads `useRouteError()` but renders no error detail (D-09)
- `frontend/src/router.tsx` - `ErrorBoundary: RouteErrorFallback` added to all 5 AppLayout leaf routes; `'SIGNED_IN'` added to the cache-clear OR-chain
- `frontend/src/screens/AuthCallbackScreen.tsx` - Manual `exchangeCodeForSession` branch deleted; replaced with authStore watch + 6s timeout fallback to `/login`; implicit-flow branch untouched
- `frontend/src/tests/routerErrorBoundary.test.tsx` - New: renders a throwing leaf route inside a real `AppLayout` + data router, asserts fallback content, nav-shell survival, and no error-detail leak
- `frontend/src/tests/auth.test.tsx` - Extended: `RootProvider` cache-clear coverage (SIGNED_IN/SIGNED_OUT/USER_UPDATED/TOKEN_REFRESHED) and `AuthCallbackScreen` single-consumption coverage (store-watch navigation, timeout fallback, exchangeCodeForSession never called)

## Decisions Made
- Attached `ErrorBoundary` to each of the 5 leaf route objects individually rather than once on the `AppLayout` route entry, matching RESEARCH.md Pattern 3's reasoning: per-leaf attachment gives a clearer mental model matching D-10's "crash on one screen" phrasing and avoids the fallback also swallowing an `AppLayout`-level render error.
- In `RootProvider`'s cache-clear tests, distinguished the two `onAuthStateChange` mock registrations (RootProvider's own single-arg listener vs. `useAuth`'s two-arg listener) by function arity rather than call order, so the test doesn't depend on hook-registration sequencing.
- Kept the `AuthCallbackScreen` implicit-flow (`hasImplicitTokens`) branch exactly as-is per RESEARCH.md guidance — `getSession()` there is idempotent and not part of the double-exchange bug, so touching it would be unnecessary scope.
- Used a 6-second timeout for the PKCE store-watch fallback, within RESEARCH.md Open Question 3's recommended 5-8s range (Claude's Discretion, no explicit UX decision needed).

## Deviations from Plan

None — plan executed exactly as written. All three tasks matched their `<action>`/`<behavior>` specs; no additional bugs, missing validation, or blocking issues were discovered during implementation.

One environment note (not a plan deviation): the worktree had no `frontend/node_modules` (git worktrees don't share node_modules with the main checkout). Symlinked `frontend/node_modules` to the main repo's identical `package.json`-matched install to run `vitest`/`tsc` — no `package.json`/`package-lock.json` changes, so this is not tracked as a deviation to the plan's file list.

## Issues Encountered
None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three security-relevant items (10, 11, 12) from the phase's Security Domain (ASVS V2/V3) are closed and verified.
- Full frontend test suite green (88/88 tests, 12 files) after this plan's changes — no regressions in sibling test files (`session.test.tsx`, `today.test.tsx`, `chat.test.tsx`, etc.).
- `npx tsc --noEmit` clean.
- No blockers for the remaining Phase 9 plans (09-01 through 09-03, 09-05 through 09-07), which touch disjoint files per the phase's file-overlap wave sequencing.

---
*Phase: 09-frontend-resilience*
*Completed: 2026-07-07*
