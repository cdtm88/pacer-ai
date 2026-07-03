---
status: complete
phase: 06-core-loop-persistence
source: [06-VERIFICATION.md]
started: 2026-07-03T16:41:02Z
updated: 2026-07-03T18:07:03Z
---

## Current Test

number: —
name: All tests complete
expected: —
awaiting: nothing; UAT passed 2/2

## Tests

### 1. Live Supabase end-to-end ride upload smoke test
expected: First upload processes inline and links to the session; byte-identical re-upload dedups via the live UNIQUE constraint; pmc_history shows a contiguous day series with rest-day decay.
result: pass (after live fixes; see Gaps)
notes: |
  Upload chain verified in production (2026-07-03): FIT parsed, ride booked to
  ride date (not upload date), content_hash written, session 5766f37d flipped
  planned -> completed with rides.session_id linked, compliance_pct computed
  (426% vs 21.5 TSS target). Two infra gaps surfaced by Vercel runtime logs and
  fixed via migration 0006 (pushed live): missing UNIQUE(user_id,date) on
  pmc_history (upsert failed 42P10, series empty) and missing `fits` storage
  bucket (raw_fit_path NULL). PMC series backfilled with production-parity math:
  731 rows, gap decay verified (CTL 2.16 -> 0.21 over idle years -> 2.36 today).
  Dedup confirmed: byte-identical re-upload short-circuited server-side (still
  2 ride rows). Frontend showed generic success toast because it ignored the
  duplicate flag; fixed in f2488d0 (duplicate-aware toast).

### 2. Physiological sanity check of _estimate_session_tss
expected: The new pure tool-library function (backend/sports_science/plan.py) estimates planned-session TSS with Coggan steady-state formula using IF midpoints 0.655 (zone 2) and 0.50 (recovery). Confirm these targets are sane for a deconditioned returning beginner (they drive underperformance detection thresholds, not prescriptions).
result: pass
notes: Constants match published references (Z2 IF band 0.56-0.75 midpoint = 0.655 -> ~43 TSS/hr; recovery 0.50 -> 25 TSS/hr, both in TrainingPeaks ranges). Errs safe for detection: false underperformance flag requires riding below IF 0.55 all session. User confirmed pass 2026-07-03.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

- [fixed 2026-07-03] pmc_history missing UNIQUE(user_id, date) -> bulk upsert rejected with 42P10, PMC series never written. Fixed in migration 0006 (constraint added, no duplicate rows existed), pushed live, series backfilled.
- [fixed 2026-07-03] `fits` storage bucket never provisioned -> Storage upload 404 "Bucket not found", raw_fit_path NULL. Fixed in migration 0006 (private bucket created as code). Note: raw_fit_path for the two existing rides remains NULL; future uploads will store.
- [enhancement -> backlog] Ride row in History could show richer detail: power/HR graphs, ride breakdown (user request during UAT). Candidate for Phase 9 or later.
