---
phase: 06-core-loop-persistence
verified: 2026-07-03T17:40:00Z
status: passed
score: 16/16 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Run a real ride upload against the live Supabase project (linked project, migration 0005 already applied) for a user with an active plan: confirm a plan via generate_plan, then POST /rides/upload twice with the same .fit file."
    expected: "First upload returns status='processed', creates one rides row with content_hash set, flips the ride-date-matching session to 'completed' with rides.session_id set, and writes a full pmc_history day-series (gap days included) via one bulk upsert. The second (byte-identical) upload returns status='duplicate', duplicate=true, and creates no second rides row (proves the live UNIQUE(user_id, content_hash) constraint path, not just the mocked pre-check)."
    why_human: "Every test asserting this behavior (test_session_link_flips_planned_session_to_completed, test_dedup_precheck_short_circuits, test_dedup_unique_violation_returns_duplicate, tests/test_pmc_recompute.py) mocks the Supabase client. The 06-05-SUMMARY explicitly defers live-DB correctness (real UNIQUE constraint race, real RLS, real pmc_history writes) to this verification step. No automated check in this repo exercises the actual linked database beyond schema introspection (already confirmed: migration 0005 applied and idempotent)."
  - test: "Have a cycling coach or domain-knowledgeable reviewer sanity-check backend/sports_science/plan.py::_estimate_session_tss (Coggan TSS = duration_hours * IF^2 * 100, IF=0.655 for endurance/strength zone-2 sessions, IF=0.50 for recovery) against real-world TSS-per-hour expectations for a beginner returning to fitness."
    expected: "The estimated TSS-per-hour values (roughly 43 TSS/hr at IF 0.655, 25 TSS/hr at IF 0.50) are plausible planned-session targets, not wildly over/under actual TSS a beginner would produce riding at those zones, since this value now drives real downstream behavior (underperformance detection thresholds, micro/macro TSS scaling)."
    why_human: "This function was added after the code review (commit 63d856e) specifically to unblock CR-01 (sessions.tss_target was never populated). It is architecturally correct (pure function, inside the tool library, no DB access, formula is the standard Coggan definition) but its accuracy is a physiological/product judgment call outside what code review or tests can certify."
---

# Phase 6: Core Loop Persistence Verification Report

**Phase Goal:** A generated plan becomes real database state and ride data flows through it correctly: plan confirmation writes `plans` and `sessions` rows; Today/Agenda/ZWO/calendar read real sessions; estimated FTP is actually used (fix `ftp_watts` vs `ftp` key mismatch, add missing `profiles.ftp`/`lthr` columns); PMC uses ride date not upload date, decays through zero-TSS gap days, sums same-day rides, and dedups re-uploaded FIT files; rides link to sessions and mark them completed; adaptation checks are idempotent (signals consumed once, `/missed` endpoint works, macro-replan confirm endpoint exists).

**Verified:** 2026-07-03T17:40:00Z
**Status:** passed (human verification completed 2026-07-03: both items passed via live UAT, see 06-UAT.md)
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Migration 0005 applied to the linked Supabase project (idempotent) | VERIFIED | `supabase migration list --linked` shows 0005 on both Local and Remote; `supabase/migrations/0005_phase6_persistence.sql` contains all six schema changes (pmc_history.tss/days_of_data, sessions 'missed' CHECK, profiles.ftp/lthr, rides.content_hash+UNIQUE(user_id,content_hash), adaptations.trigger_session_ids/status) |
| 2 | A confirmed plan writes one `plans` row and per-session `sessions` rows with a real `plan_id`, never an LLM-supplied `user_id` | VERIFIED | `backend/agent/tools.py::_persist_generated_plan` (inserts plans + sessions, rewrites `plan_id`/session ids), `dispatch_tool` generate_plan branch at line 626-627; WR-01 fix strips any LLM-supplied `user_id` unconditionally (lines 577-597); tests in `tests/agent/test_tools_phase3.py` pass |
| 3 | Week-1 sessions never land before the confirmation date; no scheduled_date collisions | VERIFIED | `_resolve_scheduled_date` + `_resolve_all_scheduled_dates` (WR-02 fix, collision handling) at tools.py:415-477 |
| 4 | save_profile writes `profiles.lthr` from `lthr_estimate` | VERIFIED | `backend/sports_science/profile.py` upsert dict (per 06-02-SUMMARY, confirmed present) |
| 5 | Estimated FTP is read from the correct `"ftp"` key (not `"ftp_watts"`) and written back to `profiles.ftp` | VERIFIED | `backend/routes/rides.py:237` reads `ftp_value.get("ftp", ...)`; lines 238-246 write back to `profiles.ftp`, user-scoped |
| 6 | PMC recompute uses ride date, decays through zero-TSS gap days, sums same-day rides, and `days_of_data` counts calendar days | VERIFIED | `backend/pmc_recompute.py::recompute_pmc_for_user` groups by `ride_date`, walks every calendar day filling gaps with 0.0, increments `days_of_data` per day not per ride; single `.upsert(rows, on_conflict="user_id,date")` call; `tests/test_pmc_recompute.py` (`gap_days`, `same_day_sum`, `days_of_data_calendar`) all pass |
| 7 | Re-uploaded (byte-identical) FIT files are deduped | VERIFIED | `upload_fit` computes `sha256(file_bytes)`, pre-check SELECT short-circuits, unique-violation fallback at insert time (`_is_unique_violation`); DB-level `UNIQUE(user_id, content_hash)` constraint from migration 0005 is the authoritative guard; `test_dedup_precheck_short_circuits`, `test_dedup_unique_violation_returns_duplicate` pass |
| 8 | A ride links to the session scheduled on its own `ride_date` (status='planned'), flips it to 'completed', and sets `rides.session_id` | VERIFIED | `process_ride_background` step 2 (rides.py:302-333) matches on `ride_date` + `status='planned'`, deterministic tiebreak (`.order("id")`), updates session status and `rides.session_id`; `test_session_link_flips_planned_session_to_completed` passes |
| 9 | The ride pipeline is inline-awaited (no BackgroundTasks — Vercel serverless constraint); upload returns `status='processed'` | VERIFIED | `upload_fit` inline-awaits `process_ride_background`-equivalent steps before returning; response `{"ride_id":..., "status":"processed"}` at rides.py:625 |
| 10 | `sessions.tss_target` is actually populated by `generate_plan` (CR-01) | VERIFIED | `_estimate_session_tss` in `backend/sports_science/plan.py` (pure Coggan TSS formula, no DB access); `_persist_generated_plan` writes it (tools.py:536); `apply_micro_adjustment`/`apply_macro_replan` skip scaling when NULL instead of writing 0.0 |
| 11 | `detect_signals` never re-emits a signal for a session already consumed, and superseded/rejected proposals release their sessions (CR-04) | VERIFIED | `_get_consumed_session_ids` filters `.in_("status", ["applied","proposed"])` (excludes superseded); `test_detect_signals_idempotent` passes |
| 12 | A consumed 'missed' signal flips the triggering session's status to 'missed' | VERIFIED | `apply_micro_adjustment` (adaptations.py:462-468) and `apply_macro_replan` (adaptations.py:653-661) both flip status, dual-filtered by id+user_id; `test_apply_micro_adjustment_missed_status_value` passes |
| 13 | `POST /adaptations/sessions/{id}/missed` actually triggers an adaptation for the session it marks (CR-02) | VERIFIED | `mark_session_missed` synthesizes `{"type":"missed","session_id":...}` when detect_signals output omits it and the session isn't already consumed (adaptations.py:884-892) |
| 14 | The 30% shift guard actually fires on real macro shifts, not unconditionally (CR-03) | VERIFIED | `after_sessions` generator now shifts by `i // 2` days (adaptations.py:574-591) instead of a uniform `i+2`; `test_apply_macro_replan_shift_limit_fires`/`test_shift_limit` pass |
| 15 | A new macro proposal supersedes prior `status='proposed'` rows for the same user | VERIFIED | adaptations.py:615-621 updates prior proposed rows to 'superseded' before inserting the new proposal |
| 16 | `POST /adaptations/{id}/confirm` applies exactly the stored proposed snapshot, dual/triple-filtered by id+user_id+status='proposed' | VERIFIED | `confirm_macro_replan` (adaptations.py:775-837): select filters `id`,`user_id`,`status='proposed'`, 404 `proposal_not_found` when absent, applies `after_snapshot["sessions"]` verbatim, flips status to 'applied'; `test_confirm_macro_applies_stored_snapshot`/`test_confirm_macro_idor_returns_404` pass |
| 17 | `validate_session_vs_actual` does not raise when actual/planned tss is None | VERIFIED | `backend/sports_science/compliance.py:13-14` coerces `.get("tss") or 0` for both planned and actual |

**Score:** 16/16 truths verified (17 listed above; truths 2-3 map to a single plan-persistence must-have in the plan frontmatter, hence the 16/16 headline score against the merged plan must_haves list)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/0005_phase6_persistence.sql` | Six idempotent schema changes | VERIFIED | Present, applied live, idempotent (confirmed via `supabase migration list --linked`) |
| `backend/agent/tools.py::_persist_generated_plan` | Persists plans+sessions | VERIFIED | Present, wired into `dispatch_tool`, tested |
| `backend/agent/tools.py::_resolve_scheduled_date` | Past-safe date resolution | VERIFIED | Present, plus `_resolve_all_scheduled_dates` collision handling (WR-02) |
| `backend/pmc_recompute.py` | Day-series PMC recompute | VERIFIED | Present, imports pure `update_pmc`, single bulk upsert, tested |
| `backend/routes/adaptations.py::confirm_macro_replan` | Confirm endpoint | VERIFIED | Present at `POST /{adaptation_id}/confirm`, IDOR-safe, tested |
| `backend/routes/rides.py` (get_user_ftp, upload_fit, process_ride_background) | FTP fix, dedup, link, inline-await | VERIFIED | All present and correct per code read |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `dispatch_tool` | `_persist_generated_plan` | `generate_plan` branch, awaited before tool_result returns | WIRED | tools.py:626-627 |
| `run_turn`/`_sse.py` | `dispatch_tool` | `user_id=user_id` forwarded from JWT (`current_user["user_id"]`) through chat.py/onboarding.py -> `_sse.py` -> `loop.run_turn` -> `dispatch_tool` | WIRED | Traced end-to-end; no path where `user_id=None` for an authenticated request |
| `upload_fit` | `recompute_pmc_for_user` | inline-awaited in `process_ride_background` step 4 | WIRED | rides.py:366 |
| `sessions.py` (Today/Agenda/ZWO) | real `sessions`/`profiles` table | `.select(...)` queries scoped by user_id | WIRED | `_SESSION_COLUMNS` includes `tss_target`; `/zwo` selects `profiles.ftp` (now populated); these endpoints predate Phase 6 but were reading an empty table — now populated by `_persist_generated_plan` |
| `detect_signals` | `_get_consumed_session_ids` | pre-query before candidate scan | WIRED | adaptations.py:99-117, 155 |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `sessions.py::today_session`/`upcoming_sessions` | `sessions` table rows | `_persist_generated_plan` insert (was previously always empty — grep-verified zero inserts pre-phase) | Yes, once a plan is confirmed | FLOWING |
| `pmc_history` rows | `recompute_pmc_for_user` bulk upsert | grouped/summed real `rides.tss` | Yes | FLOWING |
| `profiles.ftp` | `get_user_ftp` write-back | `estimate_ftp_from_rides` CP model output | Yes (medium/high confidence only) | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Backend full suite | `.venv/bin/pytest tests/ -q` | 242 passed, 9 failed (all 9 pre-existing/documented: 8x `tests/agent/test_sse.py` stale-auth + 1x order-dependent `test_capability_gap`) | PASS (matches accepted baseline exactly) |
| Frontend full suite | `npx vitest run` (from `frontend/`) | 79 passed, 11 files | PASS |
| Named regression tests for each critical/warning fix | `pytest -k "idempotent or missed_status_value or shift_limit or confirm_macro"` | 6 passed | PASS |
| PMC recompute behavioral tests | `pytest tests/test_pmc_recompute.py -v` | 3 passed (gap_days, same_day_sum, days_of_data_calendar) | PASS |
| Ride-session link behavioral test | `pytest tests/api/test_rides.py -k session_link_flips -v` | 1 passed | PASS |
| Migration applied live | `supabase migration list --linked` | 0005 present on Local and Remote | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| FIT-04 | 06-01, 06-03, 06-05 | FIT upload -> TSS/PMC pipeline correctness | SATISFIED | Dedup, inline-await, PMC recompute all verified |
| FIT-05 | 06-05 | Ride-session compliance link | SATISFIED | Session link + compliance verified, WR-12 test fix confirmed |
| TOOL-03 | 06-05 | FTP estimation surfaced to the app | SATISFIED | Key fix + write-back verified |
| TOOL-05 | 06-03 | PMC correctness (Banister EWMA) | SATISFIED | Gap-day decay, same-day sum, calendar days_of_data verified; pure `update_pmc` untouched |
| PLAN-01 | 06-02 | Confirmed plan becomes real state | SATISFIED | `_persist_generated_plan` verified |
| PLAN-04 | 06-01, 06-02 | Plan schema/persistence | SATISFIED | Migration + persistence verified |
| ONBD-04 | 06-02 | Onboarding writes lthr | SATISFIED | `save_profile` lthr write-back verified |
| ADAPT-01 | 06-01, 06-04 | Adaptation detection | SATISFIED | Idempotent detect_signals verified |
| ADAPT-02 | 06-04 | Micro adjustment | SATISFIED | Verified, CR-01 NULL-guard applied |
| ADAPT-03 | 06-04 | 30% shift guard | SATISFIED | CR-03 fix verified, guard fires |
| ADAPT-04 | 06-01, 06-04 | Manual/periodic check idempotency | SATISFIED | Verified |
| TRANSP-02 | 06-04 | Adaptation log completeness (trigger_session_ids/status) | SATISFIED | `log_adaptation` writes both fields on every path |

No orphaned requirements — all 12 target IDs are covered by at least one plan's `requirements:` frontmatter, and each has passing test evidence.

### Anti-Patterns Found

No `TBD`/`FIXME`/`XXX` unresolved debt markers found in phase-modified files. `TODO`/`HACK`/`PLACEHOLDER` scan clean. No stub returns (`return null`, empty dict/array with no data path) found in the reviewed files — all persistence paths trace to real DB writes.

Known, explicitly-deferred residual issues (not blockers for this phase's stated goal, confirmed present in code and consistent with the executor's deferred-items.md and the phase note that WR-03/WR-06/WR-08..11 and IN-* were deferred to Phases 7-9):

| File | Issue | Severity | Status |
|------|-------|----------|--------|
| `backend/agent/tools.py` (`_persist_generated_plan`) | WR-03: no supersede of prior active plan — re-confirming a plan stacks multiple active plans/stale sessions | Warning | Deferred (not fixed in post-review commits; confirmed absent by grep) |
| `backend/routes/adaptations.py:219` | WR-06: `found_ride.get("tss") or 0` still false-fires underperformance at 0% when a ride's TSS is NULL | Warning | Deferred |
| `backend/routes/adaptations.py` (calendar sync selects) | WR-08: session SELECTs still omit `calendar_event_id`; calendar sync after adaptation remains dead code | Warning | Deferred (Phase 7 scope: BackgroundTasks->inline-await work) |
| `backend/pmc_recompute.py:81` | WR-09: `date.fromisoformat` sits outside the try block, contract technically violated (masked today by the outer caller's catch) | Warning | Deferred |
| `backend/agent/tools.py` (`_persist_generated_plan`) | WR-10: non-atomic plans/sessions insert — a sessions-insert failure orphans an active plans row | Warning | Deferred |
| `backend/routes/adaptations.py` (several session UPDATEs) | WR-11: some session UPDATEs still filter by id alone, not dual-filtered by id+user_id | Warning | Deferred |

### Human Verification Required

1. **Live Supabase end-to-end smoke test** — upload a real .fit file twice against the linked project for a confirmed plan.
   Expected: first upload creates a linked, completed session and a full pmc_history series; second (duplicate) upload short-circuits via the live UNIQUE constraint.
   Why human: every automated test in this phase mocks the Supabase client; the SUMMARY documents explicitly deferred live-DB verification.

2. **Physiological sanity check of `_estimate_session_tss`** (new Coggan TSS estimate added post-review to close CR-01).
   Expected: IF midpoints (0.655 zone2/strength, 0.50 recovery) produce plausible planned-session TSS for a beginner.
   Why human: architecturally sound and correctly scoped inside the tool library (pure, no DB, standard formula), but real-world calibration is a domain judgment call, not a code-correctness question.

### Gaps Summary

No gaps found. All 4 REVIEW.md criticals (CR-01..CR-04) and 6 of 12 warnings (WR-01, WR-02, WR-04, WR-05, WR-07, WR-12) have code fixes with passing regression tests, confirmed by direct code reading (not SUMMARY claims). The remaining warnings (WR-03, WR-06, WR-08, WR-09, WR-10, WR-11) and all info-level items are real but were explicitly out of scope for this phase's stated goal and are deferred to Phases 7-9 per the phase's own tracking; none of them block the phase-6 goal statement's specific claims (plan persistence, FTP fix, PMC correctness, ride-session linking, adaptation idempotency, confirm endpoint). Migration 0005 is confirmed live on the linked Supabase project. Backend (242/251, 9 pre-existing accepted failures) and frontend (79/79) test suites match the documented baseline exactly. Two items require human verification (live-DB smoke test, physiological sanity check of a newly added tool-library computation) — this is why overall status is `human_needed` rather than `passed`.

---

_Verified: 2026-07-03T17:40:00Z_
_Verifier: Claude (gsd-verifier)_
