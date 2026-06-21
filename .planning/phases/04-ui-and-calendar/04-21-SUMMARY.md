---
phase: 04-ui-and-calendar
plan: 21
subsystem: e2e-test-harness
tags: [gap-closure, playwright, route-ordering, history, fit-upload]
dependency_graph:
  requires: [04-16]
  provides: [rides-upload-mock-correct-lifo-ordering]
  affects: [frontend/tests/e2e/full-uat.spec.ts]
tech_stack:
  added: []
  patterns: [playwright-lifo-route-registration]
key_files:
  created: []
  modified:
    - frontend/tests/e2e/full-uat.spec.ts
decisions:
  - "Route handlers reordered in mockBackendApis: /rides/ registered first, /rides/upload registered last, matching established LIFO convention from STATE.md"
metrics:
  duration: ~5m
  completed: 2026-06-21
status: complete
---

# Phase 04 Plan 21: Rides Route Handler LIFO Ordering Summary

Corrected the Playwright route registration order in `mockBackendApis` so that `/rides/upload` POST requests are intercepted by the specific upload handler rather than the general list handler.

## What Was Done

Swapped lines 231-232 in `frontend/tests/e2e/full-uat.spec.ts` inside `mockBackendApis`:

Before (broken):
```
page.route(/\/rides\/upload/, ...)  // registered first — LIFO loser
page.route(/\/rides\//, ...)        // registered last — LIFO winner (wrong!)
```

After (fixed):
```
page.route(/\/rides\//, ...)        // registered first — LIFO loser for upload POSTs
page.route(/\/rides\/upload/, ...)  // registered last — LIFO winner (correct)
```

This matches the project convention recorded in STATE.md: "Playwright LIFO: specific route handlers registered after general ones to win the match."

## Tasks

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Reorder rides route handlers so /rides/upload wins LIFO | 38039f1 | frontend/tests/e2e/full-uat.spec.ts |

## Deviations from Plan

None. The plan executed exactly as written. The file was untracked in the main repo (not yet committed) and was copied into the worktree before applying the two-line swap.

## Observations

The History e2e tests that render ride list text ("95% on target") were already failing before this change — those failures are unrelated UI rendering issues outside this plan's scope. The upload-zone visibility test ("FIT upload zone is present") passes. The route ordering fix closes the test-harness half of UAT GAP 4.

**Real-device 422 note:** The runtime 422 that appears when a user uploads a FIT file happens because files shorter than the minimum duration are rejected. `test-ride.fit` in the repo root is a 66-byte stub and is NOT a valid 10+ minute ride. To test the real upload flow manually, use a valid FIT file with 10+ minutes of actual data.

## Self-Check

- [x] `frontend/tests/e2e/full-uat.spec.ts` exists in worktree at commit 38039f1
- [x] `/rides/` is registered before `/rides/upload` in mockBackendApis (lines 231-232)
- [x] No other route registrations or fixtures were changed

## Self-Check: PASSED
