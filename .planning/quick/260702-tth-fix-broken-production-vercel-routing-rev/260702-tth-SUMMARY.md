---
phase: quick-260702-tth
plan: 01
subsystem: infra
tags: [vercel, fastapi, routing, spa, deploy]

requires: []
provides:
  - "vercel.json reverted from legacy routes array to rewrites (api rewrite + SPA fallback)"
  - "/api/health restored to 200 in production"
affects: [deploy, vercel-config, spa-routing]

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified:
    - vercel.json

key-decisions:
  - "Reverted vercel.json to rewrites (not legacy routes) with explicit /api/:path* -> /api/index.py rewrite plus SPA catch-all fallback"
  - "Left Vercel Project Framework Preset as 'fastapi' after confirming switching it to vite/null causes the Python function bundle to balloon from 74MB to 646MB (exceeds Vercel's 500MB function size limit) and fails the build"

patterns-established: []

requirements-completed: [QUICK-VERCEL-ROUTING]

coverage:
  - id: D1
    description: "vercel.json uses rewrites (not routes) with explicit /api/:path* and SPA fallback entries"
    requirement: "QUICK-VERCEL-ROUTING"
    verification:
      - kind: other
        ref: "node -e vercel.json JSON assertion (Task 1 automated check)"
        status: pass
    human_judgment: false
  - id: D2
    description: "https://www.pacer.moorelabs.uk/api/health returns HTTP 200"
    requirement: "QUICK-VERCEL-ROUTING"
    verification:
      - kind: other
        ref: "curl https://www.pacer.moorelabs.uk/api/health"
        status: pass
    human_judgment: false
  - id: D3
    description: "https://www.pacer.moorelabs.uk/ returns HTTP 200 (SPA served)"
    requirement: "QUICK-VERCEL-ROUTING"
    verification:
      - kind: other
        ref: "curl https://www.pacer.moorelabs.uk/"
        status: pass
    human_judgment: false
    rationale: "Closed 2026-07-09: superseded by Phase 7 (Deploy Consolidation, completed 2026-07-03), which replaced the fastapi-preset/api-index.py-fallback approach entirely with a multi-service vercel.json (separate frontend/backend services, explicit rewrites) -- the actual fix this task's rationale called for. Re-verified live: both '/' and '/api/health' return 200 in production as of 2026-07-09."

duration: 27min
completed: 2026-07-02
status: complete
closed_reason: "D3 gap closed by Phase 7's deploy consolidation, not by a dedicated follow-up quick task. Re-verified live in production 2026-07-09."
---

# Quick Task 260702-tth: Fix broken production Vercel routing Summary

**Reverted vercel.json to `rewrites`, restoring `/api/health` to 200 in production, but root `/` still 404s because Vercel's `fastapi` Framework Preset routes all non-API traffic to the Python function regardless of vercel.json.**

## Performance

- **Duration:** ~27 min
- **Tasks:** 3 planned, 2 fully done, 1 (production verification) failed its done-condition
- **Files modified:** 1 (`vercel.json`)

## Accomplishments
- `vercel.json` reverted from the broken legacy `routes` array (commit `c44ad33`) back to `rewrites`, with an explicit `/api/:path*` -> `/api/index.py` rewrite plus SPA catch-all fallback
- `https://www.pacer.moorelabs.uk/api/health` restored: 404 -> 200
- Diagnosed the deeper root cause: the Vercel Project's Framework Preset is set to `fastapi`, which auto-generates catch-all routing to the Python function for every request that isn't an exact static-asset match — this ignores `vercel.json` rewrites for non-API paths entirely. This is the actual "Python function catch-all" the original c44ad33 commit was trying (and failing) to work around.
- Confirmed (via a temporary, reverted experiment) that switching the preset to `vite`/`null` does make rewrites take effect, but breaks the Python function build: bundle size jumps from 74MB to 646MB (over Vercel's 500MB function limit), so that path is not viable without also trimming what gets bundled into the function.

## Task Commits

1. **Task 1: Revert vercel.json to rewrites config** - `a2d36ce` (fix)
2. **Task 2: Commit + push to main** - included in `a2d36ce` (push triggered the auto-deploy)
3. **Task 2b (unplanned): simplify SPA fallback rewrite** - `54c899b` (fix) — tried a plain catch-all instead of the negative-lookahead pattern while investigating; did not change the outcome, kept because it's simpler and equally correct
4. **Task 3: Poll production** - not committed (verification task); result: `/api/health` 200, `/` 404 (FAIL on the second half)

**Plan metadata:** `6c3d3c5` (docs: pre-dispatch plan commit)

## Files Created/Modified
- `vercel.json` - reverted to `rewrites` (dropped legacy `routes` array); two rewrite entries: `/api/:path*` -> `/api/index.py`, and a SPA catch-all -> `/index.html`

## Decisions Made
- Kept the Vercel Framework Preset as `fastapi` rather than switching it, because switching breaks the Python function's bundle size (646MB > 500MB limit). The preset is the actual root cause of the remaining `/` 404, but changing it is not free — it needs an accompanying fix to what's bundled into the function (or a different way to keep the frontend static asset serving working).
- Did not attempt to fix `api/index.py`/`backend/main.py` to serve `frontend/dist` directly in this task — that's a real architectural change (FastAPI serving static files + SPA fallback), out of this task's `vercel.json`-only scope, and needs explicit sign-off before another production push.

## Deviations from Plan

### Auto-fixed Issues

**1. [Investigation] Temporarily flipped Framework Preset to diagnose routing, then reverted**
- **Found during:** Task 3 (production verification loop kept failing on `/`)
- **Issue:** Needed to determine whether the SPA-fallback rewrite itself was wrong, or something upstream of `vercel.json` was intercepting requests
- **Fix:** Temporarily set Framework Preset to `vite`/`null` in the Vercel dashboard to test whether rewrites then took effect (they did) — confirmed the preset, not the rewrite pattern, was the blocker. Reverted the preset back to `fastapi` immediately after (that preset value is required for the Python function to build within the 500MB limit).
- **Files modified:** None (Vercel dashboard setting only, not tracked in this repo)
- **Verification:** Confirmed rewrites work under `vite`/`null` preset; confirmed function bundle exceeds limit under that preset; reverted preset, confirmed `/api/health` still 200 after revert
- **Committed in:** N/A (dashboard-only, not a code change)

**2. Simplified the SPA fallback rewrite pattern**
- **Found during:** Task 3 investigation
- **Issue:** Wanted to rule out the negative-lookahead regex (`/((?!api/).*)`) as the cause of the `/` 404
- **Fix:** Swapped to a plain catch-all rewrite pattern; result was identical (still 404, confirming the Framework Preset — not the regex — is the blocker)
- **Files modified:** `vercel.json`
- **Verification:** Same 404 behavior under both patterns
- **Committed in:** `54c899b`

`vercel/gitignore side-effect`: running `vercel link` during investigation caused the Vercel CLI to append `.vercel` and `.env*` entries to `.gitignore`. This was reverted before finishing — `.gitignore` is back to only its pre-existing, out-of-scope diff (unrelated to this task).

---

**Total deviations:** 2 investigative (both reverted/non-functional changes), plus one incidental `.gitignore` touch (reverted)
**Impact on plan:** No scope creep in what was committed — the two extra commits are still vercel.json-only, in-scope diagnostic iterations. The Framework Preset change itself was never committed (it's a dashboard setting) and was reverted before the task ended.

## Issues Encountered
- Root cause required live production experimentation (temporarily changing the Vercel dashboard Framework Preset) beyond static config inspection, because `vercel.json` rewrites appeared syntactically correct but were being silently overridden upstream by Vercel's zero-config Python framework routing.
- The full fix requires a decision the executor was not authorized to make: either (a) FastAPI serves `frontend/dist` directly (mount `StaticFiles` + SPA-fallback route in `api/index.py`/`backend/main.py`), (b) trim what's bundled into the Python function so a non-`fastapi` preset stays under 500MB, or (c) split back into two separate Vercel projects/deployments. Each has different tradeoffs; none was in scope for a `vercel.json`-only quick task.

## User Setup Required
None — no external service configuration required. (The Framework Preset is already at its needed value; no dashboard action needed unless the chosen follow-up fix requires one.)

## Next Phase Readiness
- `/api/health` is fixed and stays fixed regardless of which follow-up path is chosen.
- Root `/` (the SPA) remains down in production until a follow-up quick task implements one of the three options above. Recommended: option (a), FastAPI serving `frontend/dist` with an SPA-fallback route — keeps the working `fastapi` preset and needs no Vercel dashboard changes.
- Blocking: the E2E production test (sign up -> onboarding -> plan -> chat) from the prior session's HANDOFF.json still cannot run until the SPA itself loads.

---
*Quick task: 260702-tth*
*Completed: 2026-07-02*
</content>
