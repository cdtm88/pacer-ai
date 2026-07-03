---
status: testing
phase: 06-core-loop-persistence
source: [06-VERIFICATION.md]
started: 2026-07-03T16:41:02Z
updated: 2026-07-03T16:41:02Z
---

## Current Test

number: 1
name: Live Supabase end-to-end ride upload smoke test
expected: |
  Against the live linked project (all phase tests mock Supabase): upload a real
  .FIT file while a planned session exists for the ride date. The ride row is
  created with content_hash and raw_fit_path, the matching session flips to
  status 'completed' with the ride linked via rides.session_id, and pmc_history
  gains a contiguous daily series (gap days decayed, tss column populated).
  Upload the byte-identical file again: the request short-circuits via the
  UNIQUE(user_id, content_hash) constraint and no second ride row appears.
awaiting: user response

## Tests

### 1. Live Supabase end-to-end ride upload smoke test
expected: First upload processes inline and links to the session; byte-identical re-upload dedups via the live UNIQUE constraint; pmc_history shows a contiguous day series with rest-day decay.
result: [pending]

### 2. Physiological sanity check of _estimate_session_tss
expected: The new pure tool-library function (backend/sports_science/plan.py) estimates planned-session TSS with Coggan steady-state formula using IF midpoints 0.655 (zone 2) and 0.50 (recovery). Confirm these targets are sane for a deconditioned returning beginner (they drive underperformance detection thresholds, not prescriptions).
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
