---
phase: 04-ui-and-calendar
plan: "04"
subsystem: frontend-auth
tags: [auth, supabase, magic-link, routing, zustand, react-query, vitest]
dependency_graph:
  requires: ["04-01", "04-02", "04-03"]
  provides: ["auth-shell", "api-client", "auth-store", "login-screen", "router-gates"]
  affects: ["all subsequent frontend plans that read authenticated data"]
tech_stack:
  added:
    - "@supabase/supabase-js (auth session management)"
    - "Zustand 5.x (authStore + uiStore)"
    - "TanStack Query (FirstRunGate profile check)"
    - "sonner (toast on send failure)"
    - "Vitest + jsdom + @testing-library/react (gate tests)"
  patterns:
    - "apiFetch injects Authorization Bearer from supabase.auth.getSession()"
    - "sseUrl appends ?token= for EventSource (cannot send headers)"
    - "uploadRide omits Content-Type so browser sets multipart boundary"
    - "RootProvider at router root activates useAuth() listener globally"
    - "AuthGate reads Zustand store (sync); FirstRunGate uses TanStack Query (async)"
key_files:
  created:
    - frontend/src/lib/supabase.ts
    - frontend/src/lib/api.ts
    - frontend/src/stores/authStore.ts
    - frontend/src/stores/uiStore.ts
    - frontend/src/hooks/useAuth.ts
    - frontend/src/screens/LoginScreen.tsx
    - frontend/src/tests/auth.test.tsx
    - frontend/src/tests/setup.ts
    - frontend/vitest.config.ts
  modified:
    - frontend/src/router.tsx
decisions:
  - "RootProvider wrapper in router (not main.tsx) activates useAuth at the root so all route renders have live auth state without prop-drilling"
  - "AuthGate is sync (Zustand store read); FirstRunGate is async (TanStack Query); this avoids double-loading spinners for the common case where auth state is already settled"
  - "/onboarding placed under AuthGate but outside FirstRunGate so an authenticated user with no profile can reach it without infinite redirect"
  - "uiStore seeds iOSBannerDismissed from localStorage on module init (no effect hook needed)"
metrics:
  duration: "4m 42s"
  completed: "2026-06-20T12:14:55Z"
  tasks_completed: 3
  tasks_total: 3
  files_created: 9
  files_modified: 1
status: complete
---

# Phase 04 Plan 04: Auth Shell Summary

Supabase magic-link auth with JWT-injecting API client, Zustand stores, real AuthGate + FirstRunGate routing, and passing Vitest gate tests.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Supabase client, API fetch wrapper, Zustand stores | 12c16cb | lib/supabase.ts, lib/api.ts, stores/authStore.ts, stores/uiStore.ts |
| 2 | useAuth hook and LoginScreen (magic link) | 98b2397 | hooks/useAuth.ts, screens/LoginScreen.tsx |
| 3 | Real AuthGate + FirstRunGate in router + tests | f39fd14 | router.tsx, tests/auth.test.tsx, tests/setup.ts, vitest.config.ts |

## What Was Built

**lib/supabase.ts:** Singleton `createClient` using `VITE_SUPABASE_URL` + `VITE_SUPABASE_ANON_KEY`. Auth session management only; no data queries go through it.

**lib/api.ts:** `apiFetch` reads `supabase.auth.getSession()` on every call and injects `Authorization: Bearer <access_token>`. `sseUrl` appends `?token=` for EventSource compatibility. `uploadRide` builds FormData with `file` only and omits Content-Type. All 12 typed endpoint helpers exported: `getProfileMe`, `getSessionToday`, `getUpcomingSessions`, `getRides`, `getLatestPmc`, `getAdaptations`, `createConversation`, `markSessionMissed`, `markSessionDone`, `uploadRide`, `getCalendarSettings`, `disconnectCalendar`.

**stores/authStore.ts:** Zustand store `{ session, user, isLoading }` with `setAuth` action. Seeds `isLoading: true` so AuthGate shows a spinner until the first `getSession` resolves.

**stores/uiStore.ts:** Zustand store `{ activeTab, iOSBannerDismissed }` with setters. `iOSBannerDismissed` persists to `localStorage` under key `ios-banner-dismissed` and is seeded on init.

**hooks/useAuth.ts:** `onAuthStateChange` subscription + initial `getSession` call on mount. Sets `isLoading: false` once settled. Unsubscribes on cleanup.

**screens/LoginScreen.tsx:** Centered card (max-w 400px desktop, full-width mobile) on `--color-bg`. Logotype "PacerAI" (heading weight, `--color-ink`), descriptor "Your adaptive cycling coach." (`--color-ink-2`), email input with inline validation ("Enter your email address" / "Enter a valid email address"), primary Button "Send magic link" (`--color-blue-6`). Post-submit state shows "Check your email" heading and "We sent a link to {email}. Click it to sign in." body. Sonner toast on error. No em dashes.

**router.tsx:** `RootProvider` wraps all routes and calls `useAuth()`. `AuthGate` reads `useAuthStore` synchronously (Zustand); shows spinner while `isLoading`, redirects `/login` when no session. `FirstRunGate` uses `useQuery({ queryKey: ['profile'], queryFn: getProfileMe })`; redirects `/onboarding` when result is null (D-02). `/onboarding` is under `AuthGate` but outside `FirstRunGate`.

**tests/auth.test.tsx:** 4 passing Vitest tests covering: (1) AuthGate redirects /login when no session, (2) AuthGate renders Outlet when session exists, (3) FirstRunGate redirects /onboarding when getProfileMe returns null, (4) FirstRunGate renders Outlet when profile exists. All Supabase and API calls mocked.

## Verification Results

- `npx tsc --noEmit`: no errors
- `npm test -- --run`: 4/4 tests passed
- LoginScreen: no em dashes; renders exact copy "Send magic link", "Check your email", "Your adaptive cycling coach."
- router.tsx gates use `useAuthStore` and `getProfileMe` as required

## Decisions Made

1. **RootProvider in router, not main.tsx:** Keeps auth listener co-located with the route tree. All nested routes render with live auth state without importing useAuth in every screen.

2. **AuthGate sync / FirstRunGate async split:** AuthGate reads Zustand directly (zero async overhead for the common authenticated case). FirstRunGate uses TanStack Query so the profile check is cached and not re-fetched on every navigation.

3. **/onboarding gate placement:** `AuthGate -> /onboarding` (no `FirstRunGate`) prevents an infinite redirect loop where: no profile -> /onboarding -> FirstRunGate -> no profile -> /onboarding...

4. **uiStore localStorage init:** Reading localStorage at module initialization time (before any React render) avoids a flash of the default value on first paint.

## Deviations from Plan

None. Plan executed exactly as written.

## Threat Surface

No new security surface beyond what the plan's threat model documents. T-04-10 (magic link), T-04-11 (access_token in memory), T-04-12 (AuthGate bypass), and T-04-13 (?token= in SSE URL) are all addressed as specified.

## Self-Check: PASSED

Created files verified:
- frontend/src/lib/supabase.ts: exists
- frontend/src/lib/api.ts: exists
- frontend/src/stores/authStore.ts: exists
- frontend/src/stores/uiStore.ts: exists
- frontend/src/hooks/useAuth.ts: exists
- frontend/src/screens/LoginScreen.tsx: exists
- frontend/src/tests/auth.test.tsx: exists
- frontend/vitest.config.ts: exists
- frontend/src/router.tsx: modified

Commits verified:
- 12c16cb: feat(04-04): add Supabase client, JWT API wrapper, and Zustand stores
- 98b2397: feat(04-04): add useAuth hook and LoginScreen magic-link UI
- f39fd14: feat(04-04): wire real AuthGate + FirstRunGate into router with gate tests
