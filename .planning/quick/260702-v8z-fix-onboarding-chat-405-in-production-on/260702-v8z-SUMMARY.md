---
phase: quick-260702-v8z
plan: 01
subsystem: frontend
tags: [react, vite, sse, fetch, vercel, onboarding]

requires: []
provides:
  - Working onboarding SSE POST URL in production (same-origin /api/onboarding/start)
affects: [onboarding, production-deploy]

tech-stack:
  added: []
  patterns:
    - "Frontend fetch/SSE calls use same-origin literal /api/* paths, never import.meta.env.VITE_API_URL (unset in Vercel)"

key-files:
  created: []
  modified:
    - frontend/src/screens/OnboardingScreen.tsx

key-decisions:
  - "Changed both onboarding fetch URLs to the literal string '/api/onboarding/start', matching the existing frontend/src/lib/api.ts BASE='' same-origin convention, rather than configuring VITE_API_URL in Vercel"

patterns-established: []

requirements-completed: [QUICK-260702-v8z]

coverage:
  - id: D1
    description: "Both onboarding SSE POST fetch calls target same-origin /api/onboarding/start instead of the undefined VITE_API_URL env var"
    requirement: "QUICK-260702-v8z"
    verification:
      - kind: other
        ref: "grep -c VITE_API_URL src/screens/OnboardingScreen.tsx == 0; grep -c '/api/onboarding/start' src/screens/OnboardingScreen.tsx == 2; npx tsc --noEmit -p tsconfig.app.json exit 0"
        status: pass
    human_judgment: false
  - id: D2
    description: "Fix committed and pushed to origin/main"
    requirement: "QUICK-260702-v8z"
    verification:
      - kind: other
        ref: "git log --oneline -1 --name-only (2a7b196 touches OnboardingScreen.tsx); git ls-remote origin main == 2a7b196a24e8d2d173f7226e9a2ad37b296b017d"
        status: pass
    human_judgment: false
  - id: D3
    description: "Live production route no longer 405s and the deployed bundle serves the corrected URL"
    requirement: "QUICK-260702-v8z"
    verification:
      - kind: other
        ref: "curl POST https://www.pacer.moorelabs.uk/api/onboarding/start (unauthenticated) -> 401; curl https://www.pacer.moorelabs.uk/assets/index-DcSdROXT.js contains '/api/onboarding/start', not 'undefined/onboarding/start'"
        status: pass
    human_judgment: true
    rationale: "Live-site curl checks confirm routing and bundle content, but full authenticated SSE stream behavior (actual chat turn) was explicitly out of scope for this quick task per the plan and needs a real browser/auth session to confirm end-to-end."

duration: 12min
completed: 2026-07-02
status: complete
---

# Quick Task 260702-v8z: Fix Onboarding Chat 405 in Production Summary

**Fixed onboarding SSE POST URLs to use same-origin `/api/onboarding/start` instead of the unset `VITE_API_URL` env var, restoring the interview flow in production.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-02T21:22:00Z
- **Completed:** 2026-07-02T21:34:34Z
- **Tasks:** 3
- **Files modified:** 1

## Accomplishments
- Both `OnboardingScreen.tsx` fetch call sites (initial/subsequent interview turns and the post-confirmation save/plan turn) now POST to the literal same-origin path `/api/onboarding/start`, matching the `/api/*` convention already used by `frontend/src/lib/api.ts` (`BASE = ''`)
- Fix committed and pushed directly to `origin/main` (pre-approved for this quick task)
- Confirmed live: unauthenticated `POST /api/onboarding/start` now returns `401` (auth rejection, routing works) instead of `404`/`405`
- Confirmed the new Vercel deploy served bundle `assets/index-DcSdROXT.js` contains `/api/onboarding/start` and does not contain the broken `undefined/onboarding/start` string

## Task Commits

1. **Task 1: Point both onboarding SSE POSTs at /api/onboarding/start** - folded into the Task 2 commit below (code-only change, verified via grep + `tsc --noEmit` before committing)
2. **Task 2: Commit the fix and push to main, then wait for deploy** - `2a7b196` (fix)
3. **Task 3: Verify the live deployment serves the fix** - no commit (verification-only task); confirmed via curl against production

## Files Created/Modified
- `frontend/src/screens/OnboardingScreen.tsx` - Both `fetch(...)` calls (in `runStream` and `handleConfirm`) changed from `` `${import.meta.env.VITE_API_URL}/onboarding/start` `` to the literal `'/api/onboarding/start'`; no other logic touched

## Decisions Made
- Kept the fix as a same-origin literal URL string rather than configuring `VITE_API_URL` in Vercel, consistent with the existing `api.ts` convention (`BASE = ''`) and avoiding a new env-var dependency
- Did not refactor the two call sites to use the `apiFetch()` helper — that helper doesn't support the raw `ReadableStream` SSE reader pattern these sites rely on (POST-based SSE, since `EventSource` cannot POST)

## Deviations from Plan

None - plan executed exactly as written. One incidental setup step was required: `frontend/node_modules` did not exist in this worktree, so `npm ci` was run (installing from the existing `package-lock.json`, no new packages added) to make `tsc` available for the Task 1 verification command. This is standard dependency restoration, not a deviation from the plan's intent.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Onboarding chat routing is confirmed fixed in production at the HTTP/bundle level (curl-verified: route returns 401 not 404/405, bundle contains the corrected URL)
- Full authenticated end-to-end SSE stream verification (an actual logged-in user completing an onboarding turn in a real browser) was explicitly out of scope for this quick task and is deferred to a separate browser-automation confirmation pass, per the plan's own instruction

---
*Phase: quick-260702-v8z*
*Completed: 2026-07-02*

## Self-Check: PASSED
- FOUND: frontend/src/screens/OnboardingScreen.tsx
- FOUND: 2a7b196 (fix commit, in git log --all)
- FOUND: .planning/quick/260702-v8z-fix-onboarding-chat-405-in-production-on/260702-v8z-SUMMARY.md
