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
result: partial pass; 2 infra gaps found and fixed live (see Gaps); duplicate re-upload sub-check still pending
notes: |
  Upload chain verified in production (2026-07-03): FIT parsed, ride booked to
  ride date (not upload date), content_hash written, session 5766f37d flipped
  planned -> completed with rides.session_id linked, compliance_pct computed
  (426% vs 21.5 TSS target). Two infra gaps surfaced by Vercel runtime logs and
  fixed via migration 0006 (pushed live): missing UNIQUE(user_id,date) on
  pmc_history (upsert failed 42P10, series empty) and missing `fits` storage
  bucket (raw_fit_path NULL). PMC series backfilled with production-parity math:
  731 rows, gap decay verified (CTL 2.16 -> 0.21 over idle years -> 2.36 today).
  Remaining: byte-identical re-upload of hilly_ride_30min_today.fit must
  short-circuit via dedup.

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

- [fixed 2026-07-03] pmc_history missing UNIQUE(user_id, date) -> bulk upsert rejected with 42P10, PMC series never written. Fixed in migration 0006 (constraint added, no duplicate rows existed), pushed live, series backfilled.
- [fixed 2026-07-03] `fits` storage bucket never provisioned -> Storage upload 404 "Bucket not found", raw_fit_path NULL. Fixed in migration 0006 (private bucket created as code). Note: raw_fit_path for the two existing rides remains NULL; future uploads will store.
- [enhancement -> backlog] Ride row in History could show richer detail: power/HR graphs, ride breakdown (user request during UAT). Candidate for Phase 9 or later.
