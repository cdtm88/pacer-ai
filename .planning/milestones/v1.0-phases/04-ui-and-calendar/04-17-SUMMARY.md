---
phase: 04-ui-and-calendar
plan: 17
subsystem: auth
tags: [auth, pkce, magic-link, uat-gap-1]
status: complete

dependency_graph:
  requires: [04-14]
  provides: [gap-closure/uat-gap-1]
  affects: [frontend/src/hooks/useAuth.ts]

tech_stack:
  added: []
  patterns: [auth-callback-guard, window-location-pathname]

key_files:
  modified:
    - frontend/src/hooks/useAuth.ts

decisions:
  - "Read window.location.pathname directly (not useLocation) because useAuth may mount above the Router"
  - "Guard is computed once at effect start (const onAuthCallback) so the check is stable across async callbacks"
  - "Non-null sessions on /auth/callback are always written — real sessions are never withheld"

metrics:
  duration: 8m
  completed: 2026-06-21
  tasks_completed: 1
  files_changed: 1
---

# Phase 04 Plan 17: Skip null getSession seed on /auth/callback (UAT GAP 1) Summary

Single guard added to useAuth.ts: when the current path includes /auth/callback and getSession() resolves null, the initial setAuth seed is skipped, letting AuthCallbackScreen own session population via the PKCE exchange.

## Tasks

| # | Name | Commit | Files |
|---|------|--------|-------|
| 1 | Skip null getSession seed on /auth/callback | 67b460c | frontend/src/hooks/useAuth.ts |

## What Was Built

The race condition in the magic-link flow was: `useAuth`'s `getSession()` resolved null (PKCE exchange not yet done) and wrote `{session: null, isLoading: false}` into the auth store. AuthGate saw a non-loading null session and immediately redirected to `/login`, aborting the callback.

Fix: compute `const onAuthCallback = window.location.pathname.includes('/auth/callback')` once at effect mount. In the `getSession().then()` callback, if `onAuthCallback && initialSession === null`, return early without calling `setAuth`. This leaves the auth store in its initial `isLoading: true` state, so AuthGate stays suspended while AuthCallbackScreen completes the PKCE exchange and calls `setAuth` with the real session.

Edge cases preserved:
- Non-null session on /auth/callback (detectSessionInUrl resolved early): `setAuth` called normally
- All other routes: `setAuth` always called including with null, so unauthenticated users still redirect to /login
- `onAuthStateChange` handler unchanged (SIGNED_OUT-only clearing guard stays)

## Deviations from Plan

None. Plan executed exactly as written.

## Verification

- grep confirms "auth/callback" present in useAuth.ts (3 occurrences)
- `tsc --noEmit` passes (no output)
- Build passes in main repo (used to confirm no type regressions)
- Manual smoke required: request magic link, click it, confirm app lands at / without flashing /login (UAT GAP 1)

## Self-Check: PASSED

- frontend/src/hooks/useAuth.ts: modified with guard
- Commit 67b460c: confirmed in git log
- No unexpected file deletions
