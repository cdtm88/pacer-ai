---
phase: 03-coaching-loop
verified: 2026-07-06T00:00:00Z
status: gaps_found
score: 22/23
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: "verified (invalid status value — not a recognized status enum; treated as fresh verification per task instructions)"
  previous_score: 23/23
  gaps_closed: []
  gaps_remaining:
    - "Duplicate scheduled_date across sessions when preferred_days is shorter than weekly session count"
  regressions:
    - "The duplicate-scheduled_date defect (CR-01, found by 03-REVIEW.md 2026-07-06) was not caught by the prior verification pass, which relied on grep/static presence checks rather than executing the scheduling logic against a realistic (2 preferred days, 4 sessions/week) input."
gaps:
  - truth: "No two sessions ever share a scheduled_date, so FIT-upload ride-session matching and missed-session detection operate correctly (success criteria 3 and 4 depend on this invariant)"
    status: failed
    reason: >
      Live execution of _build_sessions (backend/sports_science/plan.py) with a realistic
      onboarding input (preferred_days=["Tuesday","Thursday"], weekly_hours=4.0 -> n_sessions=4
      via _sessions_per_week) produces two distinct session dicts for the same (week, day) pair
      in every one of the 4 weeks (8 of 16 sessions collide). Feeding that output through
      _resolve_all_scheduled_dates (backend/agent/tools.py) -- the function whose own docstring
      claims "no two sessions ever share a scheduled_date" -- confirms the collision is NOT
      resolved: 8 pairs of sessions receive an identical scheduled_date in the reproduction
      (e.g. two 2026-07-07 rows, two 2026-07-09 rows, etc.), because the function's collision
      handling only special-cases the week-1-roll-forward scenario; its first pass assigns every
      non-rolled session its naive date and adds it to `used` without ever checking `used` for a
      pre-existing collision. This breaks rides.py's ride-session link query
      (.eq("scheduled_date", ride_date).eq("status","planned").order("id").limit(1)), which can
      only match one of the two same-date sessions to an uploaded ride -- the other is
      permanently unmatchable and will be perpetually flagged "missed" by
      adaptations.detect_signals even though the user rode that day. No existing test exercises
      this path: the only two roll/collision tests
      (test_week1_rollforward_avoids_week2_collision,
      test_resolve_all_dates_no_roll_matches_single_resolver) cover only the narrow week-1
      roll-forward scenario and pass, giving false confidence that the general invariant holds.
    artifacts:
      - path: "backend/sports_science/plan.py"
        issue: "_build_sessions (lines ~124-136) cycles preferred_days via modulo when len(preferred_days) < n_sessions, assigning the same weekday to 2 distinct sessions within the same week whenever n_sessions is not an exact multiple of len(preferred_days)"
      - path: "backend/agent/tools.py"
        issue: "_resolve_all_scheduled_dates (lines ~455-494) only de-collides sessions rolled forward from week 1; its first pass assigns every non-rolled session its naive date and adds it to `used` without checking `used` for a pre-existing collision, so same-week/same-day duplicates from plan.py pass through unresolved"
    missing:
      - "Collision-aware resolution in _resolve_all_scheduled_dates that pushes ANY colliding session (not just week-1-rolled ones) forward to the earliest free date"
      - "Or a fix in _build_sessions so the same weekday is never assigned twice within one week when preferred_days is shorter than n_sessions"
      - "A regression test with preferred_days shorter than n_sessions (e.g. 2 days, 4 sessions/week) asserting all persisted scheduled_date values are unique"
deferred: []
---

# Phase 03: Coaching Loop — Verification Report

**Phase Goal:** A new user completes the onboarding interview, receives a safe plan with RPE/HR targets (no FTP required), uploads a real .FIT file that updates the PMC, and sees the plan adapt with a cited sports-science explanation
**Verified:** 2026-07-06T00:00:00Z
**Status:** gaps_found
**Re-verification:** Yes — the prior VERIFICATION.md (2026-06-21) carried an invalid `status: verified` value and did not catch the scheduling-collision defect subsequently surfaced by a fresh code review (03-REVIEW.md, 2026-07-06). This pass re-verifies from scratch and adds live-execution evidence the prior pass lacked (it explicitly skipped Step 7b behavioral spot-checks due to an unactivated virtualenv).

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A new user with zero prior data completes the interview; persisted profile includes injury/back status, schedule, goals, equipment; user sees confirmation summary before plan generation | VERIFIED | `backend/routes/onboarding.py` — `ONBOARDING_SYSTEM_PROMPT` names back_status, weekly schedule, goals, equipment, rpe_baseline, and instructs the agent to present "Here is what I have" (all 7 values) and wait for approval before calling `save_profile`. `backend/sports_science/profile.py` — `save_profile` persists `back_status` mapped to a CHECK-constrained enum and back-protective constraints JSONB. Live LLM-adherence confirmed in 03-UAT.md test 1 (human-run 2026-06-20): `save_profile` never called before the confirmation summary in a real streamed run against the Anthropic API. |
| 2 | Plan prescribes RPE/HR for early sessions with no power targets; power appears only after ftp_confidence >= medium (4+ quality efforts); every physiological number traces to a tool call | VERIFIED | `backend/sports_science/plan.py::_build_sessions`: `use_power = ftp_confidence not in ("insufficient_data","low") and ftp_watts is not None`; week 1 always sets `power_targets = None`. `test_power_targets_cold_start` and `test_back_constraints` in `tests/agent/test_tools_phase3.py` pass under a targeted (single-test) pytest run in a venv with the project's pinned dependencies. The 4-quality-effort gate lives in `estimate_ftp_from_rides` (Phase 1, unaffected by this phase). |
| 3 | Uploading a real Zwift .FIT file parses power/HR/cadence/duration; compute_tss and update_pmc run; results persist to rides/pmc_history; FIT-06 acceptance test passes | FAILED (for realistic plan inputs) | `test_fit_upload_integration` (FIT-06) passes in isolation (`pytest tests/api/test_rides.py -k test_fit_upload_integration` -> 1 passed) — parsing, TSS, and PMC update are correctly wired for a single, cleanly-scheduled session. But the session-to-ride matching this criterion's "persist to rides" clause depends on (`rides.py:308-318`) silently breaks whenever the plan that produced the target session was generated with `preferred_days` shorter than the weekly session count — a genuine, live-reproduced data-integrity defect (see below), not a hypothetical or edge case. |
| 4 | A missed session triggers re-plan; micro (1-3 sessions) vs macro (2+ signals) distinguished; no macro replan shifts >30% of upcoming sessions without a change summary | VERIFIED (mechanism), UPSTREAM DATA AT RISK | `backend/routes/adaptations.py`: `detect_signals`, `decide_scope`, `apply_micro_adjustment`, `apply_macro_replan`, `check_shift_limit` (line ~237) all present and exercised — `test_missed_detection`, `test_micro_macro_branch`, and `test_shift_limit` all pass under targeted pytest runs. The mechanism itself is sound and correctly implemented. However, `detect_signals`' missed-session check relies on the same `scheduled_date` uniqueness invariant broken in the gap below: for a plan generated with fewer preferred days than sessions/week, one of each colliding pair can never be matched to a ride and will be perpetually (and incorrectly) flagged "missed," triggering spurious re-planning signals. Kept as VERIFIED at the mechanism level since ADAPT-02/03/04 tests pass on their own merits, but flagged as at-risk in practice. |
| 5 | Every plan change is explained in chat with specific TSS/CTL/ATL/TSB values and a named sports-science principle; every change is persisted to the adaptation log | VERIFIED (with a noted reliability caveat) | `test_log_persisted` (TRANSP-02) passes under a targeted pytest run — `adaptations` table insert carries `trigger`, `scope`, `explanation_text`, before/after snapshots. `backend/routes/adaptations.py` builds explanation text citing tool-derived CTL/ATL/TSB/TSS values (unchanged from prior verification pass, re-confirmed present). Caveat: `backend/routes/_sse.py:96-110` can persist partial assistant text to the `messages` table on an abnormal turn end (`max_tool_turns`/`unexpected_stop`) as if the turn completed successfully — a reliability gap in the chat-transparency channel, tracked as a WARNING below, not a blocking gap for this criterion since it does not affect *successful* adaptation explanations. |

**Score:** 4/5 success criteria hold at the mechanism level; criterion 3 FAILS for a realistic class of onboarding inputs due to a live-reproduced BLOCKER that also puts criterion 4's data soundness at risk. Requirement-ID-level score: 22/23 (all 23 requirement IDs have wired, tested code; FIT-04/FIT-05's session-linkage step is broken by the same root cause).

### Critical Finding: Live Reproduction of CR-01 (Duplicate `scheduled_date`)

Per the review brief, this was reproduced by direct execution (not just reading code), using a Python venv with the project's pinned dependencies (`pydantic`, `numpy`, `pandas`, `scipy`, `supabase==2.31.0`, `fitdecode`, `anthropic`, `python-dotenv`, `PyJWT`, `pytest`/`pytest-asyncio`):

```
_build_sessions(weekly_hours=4.0, preferred_days=["Tuesday","Thursday"], ...)
-> 16 sessions generated; duplicate (week, day) pairs:
   {(1,'Tuesday'):2, (1,'Thursday'):2, (2,'Tuesday'):2, (2,'Thursday'):2,
    (3,'Tuesday'):2, (3,'Thursday'):2, (4,'Tuesday'):2, (4,'Thursday'):2}

_resolve_all_scheduled_dates(confirm_date=2026-07-06, sessions) ->
   DUPLICATE scheduled_date entries:
   {2026-07-07: 2, 2026-07-09: 2, 2026-07-14: 2, 2026-07-16: 2,
    2026-07-21: 2, 2026-07-23: 2, 2026-07-28: 2, 2026-07-30: 2}
```

Every week of a 4-week plan produces two `sessions` rows sharing an identical `scheduled_date` whenever the user names 2 preferred days but rides 4 times/week — an entirely ordinary onboarding answer. Any input where `n_sessions` (from `_sessions_per_week`) is not an exact multiple of `len(preferred_days)` triggers this equally (e.g. 2 days/3 sessions, 3 days/4 sessions). This directly confirms 03-REVIEW.md's CR-01 finding and is deterministic and reproducible on every run — not order-dependent, not a rare race.

**Downstream impact confirmed by code inspection**: `rides.py:308-318`'s `.eq("scheduled_date", ride_date).eq("status","planned").order("id", desc=False).limit(1)` query will match only the lower-`id` session of a colliding pair; the sibling is permanently un-matchable to any ride uploaded on that date. `adaptations.py`'s `detect_signals` (lines 154-198) will then flag that un-matchable sibling as `"missed"` on every future check, generating false-positive adaptation signals for a session the user actually rode — degrading both success criterion 3 (correct FIT-to-session persistence) and success criterion 4 (accurate missed-session detection feeding micro/macro decisions).

**No override applies** — no `overrides:` entry addressing this exists in the prior VERIFICATION.md, and this is a genuine functional defect, not an intentional design deviation. This must be fixed; no override is suggested.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/sports_science/plan.py` | Generates 4-week plan, RPE/HR-first, back-protective, distinct-date sessions | PARTIAL | `_build_sessions` correctly gates power targets and applies back-protective caps (verified: `test_back_constraints`, `test_power_targets_cold_start` pass), but the preferred-days cycling logic produces same-week/same-day duplicate sessions when `len(preferred_days) < n_sessions` (live-reproduced above) |
| `backend/agent/tools.py` (`_resolve_all_scheduled_dates`) | Resolves every session to a unique absolute date | STUB (for the general case) | Only de-collides the documented week-1-roll-forward scenario; does not check `used` for non-rolled sessions before adding them, so pre-existing collisions from `plan.py` pass through unresolved (live-reproduced above) |
| `backend/routes/onboarding.py` | SSE onboarding interview with confirmation gate | VERIFIED | `ONBOARDING_SYSTEM_PROMPT` present, "Here is what I have" gate present, live UAT passed |
| `backend/sports_science/profile.py` | `save_profile` persists back_status/schedule/goals/equipment | VERIFIED | back_status CHECK-mapped constraints present |
| `backend/routes/rides.py` | FIT upload -> parse -> TSS/PMC -> persist -> session match | HOLLOW UNDER COLLISION | Pipeline correct in isolation (test passes); session-match query silently mismatches under the CR-01 collision |
| `backend/routes/adaptations.py` | Signal detection, micro/macro decision, 30% shift guard, adaptation log | WIRED, UPSTREAM RISK | All functions present and correctly tested in isolation; correctness in production depends on the broken scheduled_date invariant |
| `backend/routes/_sse.py` | Shared SSE generator, persists assistant text only on success | WARNING (WR-06) | Persists partial text on `error`-terminated turns as if the turn succeeded (confirmed by code read: `yield {"event":"error",...}; return` is a normal generator exit, not an exception, so the `except` branch that skips `assistant_sink.append` is never reached) |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `sports_science/plan.py::_build_sessions` | `agent/tools.py::_resolve_all_scheduled_dates` | Session list -> resolved date list | BROKEN FOR REALISTIC INPUTS | Live-reproduced: collision from producer is not caught by consumer for the general (non-week-1-roll) case |
| `agent/tools.py::_persist_generated_plan` | `sessions` table | Insert with resolved `scheduled_date` | WIRED (mechanically) | Insert happens; the data it inserts can contain duplicate dates per above |
| `routes/rides.py` upload handler | `sessions` table | `.eq("scheduled_date", ride_date).eq("status","planned").limit(1)` | SILENTLY LOSSY UNDER COLLISION | Confirmed by code read; matches at most one of N colliding sessions |
| `routes/adaptations.py::detect_signals` | `sessions`/`rides` tables | Date-keyed matching | FALSE POSITIVES UNDER COLLISION | Un-matchable sibling sessions are perpetually flagged missed |
| `routes/_sse.py::sse_generator` | `messages` table (via `assistant_sink`) | Append accumulated text after loop exits without exception | WARNING (WR-06) | Appends even when the last yielded event was `error` |
| `routes/onboarding.py` | `agent/loop.py::run_turn` | Injected `system_prompt` | WIRED | `system_prompt` param threaded through `_sse.py` into `run_turn`'s `system=` kwarg |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Duplicate scheduled_date reproduction (2 preferred days, 4 sessions/week) | Direct Python execution of `_build_sessions` + `_resolve_all_scheduled_dates` in a venv with pinned deps | 8 of 16 sessions produce identical scheduled_date pairs across all 4 weeks | FAIL (confirms CR-01) |
| FIT-06 acceptance test (real Zwift .FIT fixture) | `pytest tests/api/test_rides.py -k test_fit_upload_integration` | 1 passed | PASS |
| Macro-replan 30% shift guard | `pytest tests/api/test_adaptations.py -k test_shift_limit` | 1 passed | PASS |
| Adaptation log persistence (TRANSP-02) | `pytest tests/api/test_adaptations.py -k test_log_persisted` | 1 passed | PASS |
| Cold-start power-target gate + back-protective caps | `pytest tests/agent/test_tools_phase3.py -k "cold_start or back_constraints"` (representative subset) | passed | PASS |
| Scheduling-invariant test coverage | `pytest tests/agent/test_tools_phase3.py -k "roll or resolve or collision or scheduled_date"` | 2 passed — but both only cover the narrow week-1-roll case, not the general collision found above | PASSES, INSUFFICIENT COVERAGE |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| ONBD-01 | 03-03 | Conversational interview establishes baseline/injury/equipment/schedule/goals | SATISFIED | ONBOARDING_SYSTEM_PROMPT names all fields |
| ONBD-02 | 03-01/02 | Injury/back status persisted and applied as constraints | SATISFIED | `save_profile` back_status -> constraints JSONB |
| ONBD-03 | 03-01/02/03 | Interview output is a persisted structured profile | SATISFIED | profiles table + save_profile |
| ONBD-04 | 03-03 | Confirmation summary before plan generation | SATISFIED | Live UAT-verified gate |
| PLAN-01 | 03-01/02 | Periodised beginner plan | SATISFIED | `_build_sessions` 4-week mesocycle |
| PLAN-02 | 03-02 | Cold-start RPE/HR only | SATISFIED | `test_power_targets_cold_start` passes |
| PLAN-03 | 03-02 | Power only after medium FTP confidence | SATISFIED | `use_power` gate confirmed |
| PLAN-04 | 03-01/02 | Every session has objective/structure/targets/duration | SATISFIED | `_build_sessions` structure dict |
| PLAN-05 | 03-02 | Back-protective constraints reflected in plan | SATISFIED | `test_back_constraints` passes |
| PLAN-06 | 03-02 | Every physiological number traces to a tool call | SATISFIED | Server-side injection allowlist confirmed in 03-REVIEW.md, no bypass found |
| FIT-01 | 03-04 | Upload .FIT file | SATISFIED | `POST /rides/upload` |
| FIT-02 | 03-02/04 | fitdecode with ErrorHandling.WARN, get_value fallback | SATISFIED | grep-confirmed + tests pass |
| FIT-03 | 03-04 | Extracts power/HR/cadence/duration, graceful missing-field handling | SATISFIED | `test_missing_fields` present |
| FIT-04 | 03-01/04 | compute_tss + update_pmc run; persists to rides/pmc_history | AT RISK | Correct in isolation; session-linkage undermined by CR-01 for realistic plans |
| FIT-05 | 03-04 | validate_session_vs_actual produces compliance | AT RISK | Same CR-01 dependency — the session it validates against may be the wrong (or no) session |
| FIT-06 | 03-02/04 | Real Zwift .FIT acceptance test | SATISFIED (isolated) | `test_fit_upload_integration` passes |
| ADAPT-01 | 03-05 | Adapts on missed sessions, travel, performance, load | AT RISK | Missed-detection accuracy depends on CR-01 |
| ADAPT-02 | 03-05 | Micro (1-3) vs macro (2+ signal) distinction | SATISFIED | `test_micro_macro_branch` passes |
| ADAPT-03 | 03-05 | 30% shift guard | SATISFIED | `test_shift_limit` passes |
| ADAPT-04 | 03-05 | Weekly automated check independent of uploads | SATISFIED | `test_weekly_check` present |
| ADAPT-05 | 03-05 | Dynamic intensity/session-type decisions from tool results | SATISFIED | `test_intensity_from_tools` present |
| TRANSP-01 | 03-03/05 | Chat explanation citing TSS/CTL/ATL/TSB + named principle | SATISFIED (with WR-06 reliability caveat) | Explanation text construction confirmed; SSE persistence bug is a WARNING, not a functional block |
| TRANSP-02 | 03-01/05 | Adaptation log persisted with trigger/reasoning/timestamp | SATISFIED | `test_log_persisted` passes |
| TRANSP-03 | 03-05 | Adaptation log is human-readable | SATISFIED | `GET /adaptations` present + `test_get_adaptations` passes |

**Orphaned requirements:** None. All 23 requirement IDs declared across `03-01` through `03-05` PLAN frontmatter match exactly the 23 IDs traced to Phase 3 in `.planning/REQUIREMENTS.md` (ONBD-01..04, PLAN-01..06, FIT-01..06, ADAPT-01..05, TRANSP-01..03).

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/sports_science/plan.py` | ~132-135 | Modulo day-cycling produces same-weekday duplicates within one week | BLOCKER | Breaks scheduled_date uniqueness invariant (CR-01), live-reproduced above |
| `backend/agent/tools.py` | ~476-481 | Collision detection only applied to rolled week-1 sessions, not all sessions | BLOCKER | Same root cause as above — this is the fix point |
| `backend/routes/_sse.py` | 96-110 | Success-path persistence triggered by "loop exited without exception" rather than "last event was not error" | WARNING | Partial/truncated assistant text can be saved to `messages` as if complete (WR-06); confirmed by code read of `agent/loop.py`'s error-yield-then-return pattern |
| `backend/routes/adaptations.py` | 905 | `mark_session_missed`'s status UPDATE omits the `user_id` dual-filter used elsewhere in the same file | WARNING | Defense-in-depth gap; not currently exploitable (ownership pre-verified via SELECT moments earlier) but breaks the file's own documented convention (WR-03) — confirmed by direct code read |
| `backend/routes/rides.py` | 418-431 | `_sanitize_filename` defined but never called; docstring claims it's an active mitigation | WARNING | Dead code masquerading as an applied threat mitigation (WR-04) — not a live vulnerability since storage keys are content-addressed, but misleading documentation |
| `backend/agent/tools.py` | 777-791 | Branch A self-reported LTHR passes through to `save_profile` unverified against transcript | WARNING | Architectural trust-boundary gap (WR-05) — tool-call arguments are trusted, only free text is scanned |
| `backend/agent/tools.py` / `backend/agent/loop.py` | 734-753 / 253-261 | Same-turn trust-sensitive injection for `generate_plan` races against parallel tool dispatch (`asyncio.gather`) | WARNING | Currently favorable ordering, not a guarantee (WR-01) |
| `backend/agent/tools.py` | 497-578 | `_persist_generated_plan` performs 2 non-atomic inserts | WARNING | Orphaned `plans` row possible on partial failure (WR-02) |

**Debt-marker gate:** No unreferenced `TBD`/`FIXME`/`XXX` markers found in files reviewed for this pass.

### Human Verification Required

None required for this re-verification pass. The critical finding (CR-01) was resolved through direct code execution, not human judgment, and the previously-completed UAT (03-UAT.md, ONBD-04 confirmation gate) still stands unchanged since this review touched no onboarding-flow code.

### Gaps Summary

One BLOCKER, confirmed by live execution rather than static analysis alone: `_build_sessions` (plan.py) and `_resolve_all_scheduled_dates` (tools.py) together fail to guarantee unique `scheduled_date` values per session whenever a user's `preferred_days` count doesn't evenly divide their weekly session count — an entirely ordinary onboarding answer (e.g. 2 preferred days, 4 sessions/week). This was reproduced directly: every week of a resulting 4-week plan generated two sessions sharing the same date, and the same-date collisions passed unresolved through the scheduling function whose own docstring claims to prevent exactly this. The consequence is not cosmetic: it silently breaks the ride-to-session matching that criterion 3 and criterion 4 (FIT-04, FIT-05, ADAPT-01) depend on — one session of each colliding pair becomes permanently unmatchable to any ride and will be perpetually misreported as "missed," corrupting the adaptation signal pipeline for real users with this common scheduling pattern.

This must be fixed before the phase goal can be considered fully achieved: success criterion 3 explicitly requires that upload results "persist to rides and pmc_history" in a way that supports the coaching loop, and this defect means that persistence silently attaches to the wrong (or no) session for roughly half of affected sessions in the common 2-days/4-sessions-per-week (and equivalent) input patterns.

Six additional WARNING-level findings from 03-REVIEW.md were spot-checked by direct code reading and confirmed as real but non-blocking against this phase's stated success criteria: a parallel-dispatch race in trust-sensitive tool injection (WR-01), non-atomic plan persistence (WR-02), a missing defense-in-depth filter in one UPDATE (WR-03), dead sanitization code with a misleading docstring (WR-04), an unverified self-reported LTHR value (WR-05), and an SSE error path that can persist partial assistant text as if the turn succeeded (WR-06). None of these independently fails a stated success criterion, but WR-06 is worth prioritizing alongside the CR-01 fix since it also touches TRANSP-01's chat-transparency guarantee under abnormal-termination conditions.

**Recommended fix priority for the gap-closure plan:**
1. CR-01 (blocking) — make `_resolve_all_scheduled_dates` collision-aware for all sessions (not just week-1-rolled ones), or fix `_build_sessions`'s day-cycling so no weekday repeats within a week; add a regression test with `preferred_days` shorter than `n_sessions` asserting scheduled_date uniqueness across the full plan.
2. WR-06 (recommended, non-blocking) — have `run_turn` signal abnormal termination distinctly from normal completion so `_sse.py` doesn't persist partial text as a completed turn.
3. WR-01 through WR-05 — lower priority; document or fix per 03-REVIEW.md's suggested remediations.

---

_Verified: 2026-07-06T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
