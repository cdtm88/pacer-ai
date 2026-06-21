---
status: resolved
trigger: "magic link still not working, redirecting to login page"
created: 2026-06-21T00:00:00Z
updated: 2026-06-21T00:00:00Z
---

## Symptoms

- expected: clicking magic link → lands on navigation shell at /
- actual: browser shows /auth/callback briefly, then redirects to /login
- errors: no console errors visible
- environment: Brave on macOS, localhost dev server
- timeline: never fully worked

## Current Focus

hypothesis: "exchangeCodeForSession() fires SIGNED_IN via setTimeout(0) — deferred after .then() runs and navigate('/') triggers AuthGate render with session=null"
next_action: "fix applied"

## Evidence

- timestamp: 2026-06-21T00:00:00Z
  observation: "Callback URL appears then /login — confirms /auth/callback route loads and code is present"
- timestamp: 2026-06-21T00:00:00Z
  observation: "No console errors — exchange succeeds (no error branch hit)"
- timestamp: 2026-06-21T00:00:00Z
  observation: "GoTrue-JS v2 _notifyAllSubscribers uses setTimeout(0) per source — SIGNED_IN event deferred after .then() resolves"
- timestamp: 2026-06-21T00:00:00Z
  observation: "exchangeCodeForSession() returns { data: { session, user }, error } — session available synchronously in response"

## Eliminated

- hypothesis: "AuthGate redirects before /auth/callback route mounts"
  reason: "Callback URL visible in browser — route mounts correctly"
- hypothesis: "PKCE exchange fails with an error"
  reason: "No console error, no error branch in AuthCallbackScreen logs"
- hypothesis: "useAuth INITIAL_SESSION racing with exchange"
  reason: "Partially true but secondary — main issue is setTimeout(0) deferral of SIGNED_IN after navigate()"

## Resolution

root_cause: "GoTrue-JS v2 _notifyAllSubscribers defers SIGNED_IN via setTimeout(0). The .then() callback runs first, calling navigate('/'), which causes AuthGate to render with session=null (store not yet updated). The redirect to /login fires before the auth state change propagates."
fix: "In AuthCallbackScreen, destructure data from exchangeCodeForSession response and call useAuthStore.getState().setAuth() directly with data.session before calling navigate('/'). This bypasses the setTimeout(0) deferral."
files_changed:
  - frontend/src/screens/AuthCallbackScreen.tsx
