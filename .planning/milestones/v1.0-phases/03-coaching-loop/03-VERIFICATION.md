---
phase: 03-coaching-loop
verified: 2026-07-07T15:57:29Z
status: passed
score: 23/23
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 22/23
  gaps_closed:
    - "No two persisted sessions ever share a scheduled_date, so FIT-upload ride-session matching and missed-session detection operate correctly (CR-01)"
  gaps_remaining: []
  regressions: []
deferred: []
---

# Phase 03: Coaching Loop — Verification Report (Re-verification)

**Phase Goal:** A new user completes the onboarding interview, receives a safe plan with RPE/HR targets (no FTP required), uploads a real .FIT file that updates the PMC, and sees the plan adapt with a cited sports-science explanation
**Verified:** 2026-07-07T15:57:29Z
**Status:** passed
**Re-verification:** Yes — after gap-closure plan 03-06, which fixed the one BLOCKER (CR-01) and one recommended non-blocking item (WR-06) from the prior 03-VERIFICATION.md (2026-07-06, status: gaps_found, score 22/23).

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | A new user with zero prior data completes the interview; persisted profile includes injury/back status, schedule, goals, equipment; user sees confirmation summary before plan generation | VERIFIED | Unchanged since prior pass (no onboarding-flow code touched by 03-06). `backend/routes/onboarding.py` `ONBOARDING_SYSTEM_PROMPT` names all 7 fields and requires the "Here is what I have" gate before `save_profile`. Live LLM-adherence confirmed in 03-UAT.md test 1. |
| 2 | Plan prescribes RPE/HR for early sessions with no power targets; power appears only after ftp_confidence >= medium; every physiological number traces to a tool call | VERIFIED | Unchanged. `backend/sports_science/plan.py::_build_sessions` gates `use_power`; `test_power_targets_cold_start`, `test_back_constraints` pass (re-ran: 3 passed alongside the CR-01 tests below). |
| 3 | Uploading a real Zwift .FIT file parses power/HR/cadence/duration; compute_tss and update_pmc run; results persist to rides/pmc_history; FIT-06 acceptance test passes | VERIFIED | `pytest tests/api/test_rides.py -k test_fit_upload_integration` -> 1 passed. The scheduled_date-collision defect that previously undermined the "persist to rides" session-matching clause is now fixed and independently re-reproduced (see Gap Closure Verification below) — this criterion no longer fails for realistic plan inputs. |
| 4 | A missed session triggers re-plan; micro (1-3 sessions) vs macro (2+ signals) distinguished; no macro replan shifts >30% of upcoming sessions without a change summary | VERIFIED | `backend/routes/adaptations.py` mechanism unchanged and still correctly tested (`test_missed_detection`, `test_micro_macro_branch`, `test_shift_limit` all pass). The upstream data-integrity risk flagged in the prior pass (duplicate scheduled_date causing perpetual false "missed" flags) is now closed — `detect_signals`' date-keyed matching operates against a guaranteed-unique `scheduled_date` set. |
| 5 | Every plan change is explained in chat with specific TSS/CTL/ATL/TSB values and a named sports-science principle; every change is persisted to the adaptation log | VERIFIED | `test_log_persisted` (TRANSP-02) passes; explanation-text construction in `backend/routes/adaptations.py` unchanged and confirmed present. The WR-06 reliability caveat (SSE persisting partial assistant text on abnormal termination) is now closed: `sse_generator` gates the `assistant_sink` append on `terminal_event == "done"`; independently re-verified below. |

**Score:** 5/5 success criteria hold. Requirement-ID-level score: 23/23 — all 23 requirement IDs have wired, tested code, and the one requirement previously marked AT RISK (FIT-04/FIT-05/ADAPT-01, via the CR-01 root cause) is now fully SATISFIED.

### Gap Closure Verification (independent re-execution, not SUMMARY-trust)

**CR-01 (BLOCKER, previously `status: failed`) — closed, independently reproduced:**

Re-ran the exact reproduction the prior VERIFICATION.md used, directly against current code (not via reading the plan/summary):

```
_build_sessions(4.0, "none", [], "insufficient_data", None, preferred_days=["Tuesday","Thursday"])
-> 16 sessions; duplicate (week, day) pairs confirmed present (all 8 pairs, same as before):
   {(1,'Tuesday'):2, (1,'Thursday'):2, (2,'Tuesday'):2, (2,'Thursday'):2,
    (3,'Tuesday'):2, (3,'Thursday'):2, (4,'Tuesday'):2, (4,'Thursday'):2}

_resolve_all_scheduled_dates(date(2026,7,6), sessions)  # 2026-07-06 is a Monday
-> 16 resolved dates, 16 unique (0 duplicates) -- PREVIOUSLY: 8 duplicate pairs, 8 unique.
```

This confirms `_build_sessions` still (correctly, per the plan's design choice) produces the duplicate `(week, day)` pairs — the fix was deliberately placed in the resolver, not the producer — and that `_resolve_all_scheduled_dates`'s first pass now advances a colliding candidate date forward one day at a time until free, closing the invariant gap. Read `backend/agent/tools.py:455-513` directly to confirm the collision-aware first-pass loop (`while candidate in used: candidate += timedelta(days=1)`) exists exactly as the SUMMARY claims — this is not a stub or partial fix; the loop runs unconditionally for every non-rolled session.

Named-test verification (single targeted run, not the full suite): `pytest tests/agent/test_tools_phase3.py -k "week1_rollforward or resolve_all_dates_no_roll or unique_when_preferred_days_shorter" -q` -> `3 passed`. The two pre-existing week-1-roll tests still pass unchanged, and the new regression test (`test_scheduled_dates_unique_when_preferred_days_shorter_than_sessions`) passes and asserts 16/16 uniqueness.

**WR-06 (recommended, non-blocking) — closed, independently confirmed:**

Read `backend/routes/_sse.py:96-133` directly. `terminal_event` is set on every loop iteration to the type of the last-yielded event; the post-loop `assistant_sink.append` is gated on `terminal_event == "done"` (not merely "no exception raised"). This is the correct fix for the documented failure mode: `run_turn`'s abnormal paths (`max_tool_turns`, `unexpected_stop`, `max_retries`) yield an `error` event and then `return` normally, so gating on exception-freedom alone would still have persisted partial text.

Named-test verification: `pytest tests/agent/test_sse.py -k "TestAssistantSinkGating" -q` -> `2 passed` (`test_sink_not_appended_on_error_terminated_turn`, `test_sink_appended_on_normal_completion`).

**Full affected-surface run** (matches 03-06-PLAN's own `<verification>` command): `pytest tests/agent/test_tools_phase3.py tests/agent/test_sse.py -q` -> `27 passed, 8 failed` (the 8 are the pre-existing, unrelated `TestSSEEventSequence` auth-gate failures — see below).

### Pre-existing `test_sse.py::TestSSEEventSequence` failures — classification re-confirmed, not accepted uncritically

Independently ran the full repo test suite: `pytest tests/ -q` -> **319 passed, 8 failed**, matching 03-06-SUMMARY's claim exactly (not merely trusted). The 8 failures are all `tests/agent/test_sse.py::TestSSEEventSequence::*`, and inspection confirms:

- Root cause: `backend/routes/chat.py` requires `Depends(get_current_user)` (JWT auth) on `GET /chat/stream`, added in commit `b3fcf39` ("fix(auth): inject authenticated user_id server-side into save_profile/generate_plan"), dated 2026-07-02 — 5 days before this phase's gap-closure work (2026-07-07) and unrelated to CR-01/WR-06 in subject matter (server-side user_id injection vs. scheduling/SSE-persistence fixes).
- Confirmed via `git log --oneline -- backend/routes/chat.py`: `b3fcf39` predates the entire 03-06 branch of work (`29a453f` onward). The failing tests call the endpoint with no `Authorization` header, receive `401` before the endpoint's own validation logic runs (e.g. `test_sse_requires_conversation_id` expects `422`, gets `401`).
- Confirmed already tracked in three places: `.planning/phases/06-core-loop-persistence/deferred-items.md`, `.planning/phases/07-deploy-consolidation/deferred-items.md`, and this phase's own `.planning/phases/03-coaching-loop/deferred-items.md` (all describe the identical 8-test, same-root-cause failure signature).
- Confirmed scoped to Phase 10 (Hygiene and Safety Nets) via `.planning/STATE.md`'s Roadmap Evolution section: "Phase 10: Hygiene and Safety Nets (stale tests, contract tests, token exchange, rate limit, CI)".
- Confirmed 03-06's diff does not touch `TestSSEEventSequence`: the new `TestAssistantSinkGating` class and two new mock generators are pure additions to `tests/agent/test_sse.py`; zero lines changed in the existing class (verified by reading the current file — the new class is appended after the existing one, no modifications to existing test bodies).

**Classification holds:** these 8 failures are genuinely unrelated to Phase 03's requirement set (ONBD/PLAN/FIT/ADAPT/TRANSP) — they test JWT-authenticated HTTP request handling, a cross-cutting auth concern introduced by out-of-phase work, not any of the 23 requirement IDs' scheduling, FIT-parsing, adaptation, or transparency logic. Not treated as a phase-03 gap.

### WR-01 through WR-05 — deferred, not silently dropped

Confirmed these lower-priority findings from the original 03-REVIEW.md (git history commit `a98fb87`, 2026-07-06) remain documented in three places, not lost:

1. **Prior `03-VERIFICATION.md`'s "Gaps Summary"** (superseded by this report but content still readable via git history) explicitly named all six WR items (WR-01 through WR-06) and ranked WR-06 as the only one worth prioritizing; WR-01 through WR-05 were explicitly deprioritized as non-blocking.
2. **`03-06-PLAN.md`'s "Explicitly deferred" section** (still present in the current phase directory) restates all five: WR-01 (parallel-dispatch race in trust-sensitive `generate_plan` injection), WR-02 (non-atomic 2-insert `_persist_generated_plan`), WR-03 (`mark_session_missed` UPDATE missing `user_id` dual-filter), WR-04 (dead `_sanitize_filename` with misleading docstring), WR-05 (unverified self-reported LTHR).
3. **Original `03-REVIEW.md` content** (git commit `a98fb87`) contains the full technical description and suggested fix for each — recoverable via `git show a98fb87:.planning/phases/03-coaching-loop/03-REVIEW.md`, confirmed by direct read during this verification.

The current (working-tree) `03-REVIEW.md` was overwritten by a later, narrower review scoped only to the 03-06 gap-closure diff (this is expected code-review workflow behavior — each review documents its own diff scope — not evidence of the WR-01..05 items being dropped, since they are preserved in the three locations above and none of them independently fails a stated Phase 03 success criterion). No override is needed since these are legitimately deferred, not phase-blocking gaps.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/sports_science/plan.py` | Generates 4-week plan, RPE/HR-first, back-protective, distinct-date sessions | VERIFIED | `_build_sessions` unchanged (confirmed byte-identical per 03-06-SUMMARY's diff claim and independent re-read); still produces duplicate (week,day) pairs by design — uniqueness is guaranteed downstream by the resolver, which is now fixed. |
| `backend/agent/tools.py` (`_resolve_all_scheduled_dates`) | Resolves every session to a unique absolute date | VERIFIED | Collision-aware first pass confirmed present by direct code read (lines 455-513) and by live re-execution (16/16 unique, reproduced above). |
| `backend/routes/onboarding.py` | SSE onboarding interview with confirmation gate | VERIFIED | Unchanged; re-confirmed present. |
| `backend/sports_science/profile.py` | `save_profile` persists back_status/schedule/goals/equipment | VERIFIED | Unchanged; re-confirmed present. |
| `backend/routes/rides.py` | FIT upload -> parse -> TSS/PMC -> persist -> session match | VERIFIED | Pipeline correct in isolation (test passes); session-match query now operates against a guaranteed-unique scheduled_date set, closing the prior collision risk. |
| `backend/routes/adaptations.py` | Signal detection, micro/macro decision, 30% shift guard, adaptation log | VERIFIED | All functions present and tested; upstream data-integrity risk closed. |
| `backend/routes/_sse.py` | Shared SSE generator, persists assistant text only on success | VERIFIED | `terminal_event` gating confirmed present by direct code read (lines 96-133) and by targeted test run (2 passed). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `sports_science/plan.py::_build_sessions` | `agent/tools.py::_resolve_all_scheduled_dates` | Session list -> resolved date list | WIRED, COLLISION-SAFE | Live-reproduced: 16/16 unique dates for the previously-failing input. |
| `agent/tools.py::_persist_generated_plan` | `sessions` table | Insert with resolved `scheduled_date` | WIRED | Insert happens; data is now guaranteed collision-free. |
| `routes/rides.py` upload handler | `sessions` table | `.eq("scheduled_date", ride_date).eq("status","planned").limit(1)` | WIRED, NO LONGER LOSSY | Collision root cause closed upstream; match is now deterministic. |
| `routes/adaptations.py::detect_signals` | `sessions`/`rides` tables | Date-keyed matching | WIRED, NO FALSE POSITIVES | Un-matchable-sibling risk closed. |
| `routes/_sse.py::sse_generator` | `messages` table (via `assistant_sink`) | Append gated on `terminal_event == "done"` | WIRED, CORRECT | Confirmed by code read and targeted test pass. |
| `routes/onboarding.py` | `agent/loop.py::run_turn` | Injected `system_prompt` | WIRED | Unchanged. |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| CR-01 reproduction (2 preferred days, 4 sessions/week) — independent re-execution | Direct Python execution of `_build_sessions` + `_resolve_all_scheduled_dates` against current code | 16/16 unique resolved dates (0 duplicates) | PASS (previously FAIL) |
| CR-01 + pre-existing scheduling tests | `pytest tests/agent/test_tools_phase3.py -k "week1_rollforward or resolve_all_dates_no_roll or unique_when_preferred_days_shorter" -q` | 3 passed | PASS |
| WR-06 sink-gating tests | `pytest tests/agent/test_sse.py -k "TestAssistantSinkGating" -q` | 2 passed | PASS |
| FIT-06 acceptance test (real Zwift .FIT fixture) | `pytest tests/api/test_rides.py -k test_fit_upload_integration -q` | 1 passed | PASS |
| Gap-closure plan's own affected-surface verification | `pytest tests/agent/test_tools_phase3.py tests/agent/test_sse.py -q` | 27 passed, 8 failed (pre-existing, unrelated) | PASS (matches 03-06-SUMMARY claim exactly) |
| Full repo suite (single run, not repeated per-truth) | `pytest tests/ -q` | 319 passed, 8 failed | PASS (matches 03-06-SUMMARY claim exactly; 8 failures re-classified as unrelated, see above) |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| ONBD-01 | 03-03 | Conversational interview establishes baseline/injury/equipment/schedule/goals | SATISFIED | Unchanged from prior pass; ONBOARDING_SYSTEM_PROMPT names all fields |
| ONBD-02 | 03-01/02 | Injury/back status persisted and applied as constraints | SATISFIED | Unchanged; `save_profile` back_status -> constraints JSONB |
| ONBD-03 | 03-01/02/03 | Interview output is a persisted structured profile | SATISFIED | Unchanged; profiles table + save_profile |
| ONBD-04 | 03-03 | Confirmation summary before plan generation | SATISFIED | Unchanged; Live UAT-verified gate |
| PLAN-01 | 03-01/02/06 | Periodised beginner plan | SATISFIED | `_build_sessions` 4-week mesocycle; scheduling invariant now closed |
| PLAN-02 | 03-02 | Cold-start RPE/HR only | SATISFIED | `test_power_targets_cold_start` re-confirmed passing |
| PLAN-03 | 03-02 | Power only after medium FTP confidence | SATISFIED | `use_power` gate re-confirmed |
| PLAN-04 | 03-01/02 | Every session has objective/structure/targets/duration | SATISFIED | Unchanged |
| PLAN-05 | 03-02 | Back-protective constraints reflected in plan | SATISFIED | `test_back_constraints` re-confirmed passing |
| PLAN-06 | 03-02 | Every physiological number traces to a tool call | SATISFIED | Unchanged; server-side injection allowlist |
| FIT-01 | 03-04 | Upload .FIT file | SATISFIED | Unchanged |
| FIT-02 | 03-02/04 | fitdecode with ErrorHandling.WARN, get_value fallback | SATISFIED | Unchanged |
| FIT-03 | 03-04 | Extracts power/HR/cadence/duration, graceful missing-field handling | SATISFIED | Unchanged |
| FIT-04 | 03-01/04/06 | compute_tss + update_pmc run; persists to rides/pmc_history | SATISFIED | Previously AT RISK via CR-01; root cause closed and independently re-verified |
| FIT-05 | 03-04/06 | validate_session_vs_actual produces compliance | SATISFIED | Previously AT RISK via CR-01; root cause closed |
| FIT-06 | 03-02/04 | Real Zwift .FIT acceptance test | SATISFIED | `test_fit_upload_integration` re-confirmed passing |
| ADAPT-01 | 03-05/06 | Adapts on missed sessions, travel, performance, load | SATISFIED | Previously AT RISK via CR-01; missed-detection accuracy no longer depends on a broken invariant |
| ADAPT-02 | 03-05 | Micro (1-3) vs macro (2+ signal) distinction | SATISFIED | `test_micro_macro_branch` re-confirmed passing |
| ADAPT-03 | 03-05 | 30% shift guard | SATISFIED | `test_shift_limit` re-confirmed passing |
| ADAPT-04 | 03-05 | Weekly automated check independent of uploads | SATISFIED | Unchanged; `test_weekly_check` present |
| ADAPT-05 | 03-05 | Dynamic intensity/session-type decisions from tool results | SATISFIED | Unchanged; `test_intensity_from_tools` present |
| TRANSP-01 | 03-03/05/06 | Chat explanation citing TSS/CTL/ATL/TSB + named principle | SATISFIED | Previously carried a WR-06 reliability caveat; now closed and independently re-verified (sink-gating tests pass) |
| TRANSP-02 | 03-01/05 | Adaptation log persisted with trigger/reasoning/timestamp | SATISFIED | `test_log_persisted` re-confirmed passing |
| TRANSP-03 | 03-05 | Adaptation log is human-readable | SATISFIED | Unchanged; `GET /adaptations` + `test_get_adaptations` |

**Orphaned requirements:** None. All 23 requirement IDs declared across `03-01` through `03-06` PLAN frontmatter (03-06 re-declares PLAN-01, FIT-04, FIT-05, ADAPT-01, TRANSP-01 as the requirements its gap-closure work restores) match exactly the 23 IDs traced to Phase 3 in `.planning/REQUIREMENTS.md` (ONBD-01..04, PLAN-01..06, FIT-01..06, ADAPT-01..05, TRANSP-01..03), all marked `Complete` in REQUIREMENTS.md's traceability table.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/agent/tools.py` | 493-499 | Collision-avoidance loop's correctness implicitly depends on `n_sessions <= 6` staying true in `_sessions_per_week` (new 03-REVIEW.md WR-01, 2026-07-07) | INFO | Not currently exploitable (`_sessions_per_week` caps at 4); no test parametrizes beyond 4 sessions/week. Not a Phase 03 blocker; worth a follow-up guard/comment if a higher-session tier is ever added. |
| `tests/agent/test_tools_phase3.py` | n/a | No single test combines the CR-01 duplicate-day scenario with a week-1 roll-forward in one plan (new 03-REVIEW.md IN-01) | INFO | Manually traced by the code reviewer and confirmed correct; a combined regression test would lock this further but its absence does not indicate a defect. |
| WR-01 through WR-05 (original 03-REVIEW.md, `a98fb87`) | various | Parallel-dispatch race, non-atomic plan insert, missing dual-filter, dead sanitization code, unverified self-reported LTHR | WARNING (deferred, documented) | None independently fails a stated Phase 03 success criterion; formally deferred per 03-06-PLAN.md's "Explicitly deferred" section — see analysis above. |

**Debt-marker gate:** No unreferenced `TBD`/`FIXME`/`XXX`/`TODO`/`HACK`/`PLACEHOLDER` markers found in `backend/agent/tools.py`, `backend/routes/_sse.py`, `tests/agent/test_tools_phase3.py`, or `tests/agent/test_sse.py` (grep run directly, zero matches).

### Human Verification Required

None required for this re-verification pass. Both prior gaps (CR-01, WR-06) were resolved through direct code execution and code reading, not human judgment. The previously-completed UAT (03-UAT.md, ONBD-04 confirmation gate) still stands unchanged since 03-06 touched no onboarding-flow code.

### Gaps Summary

No gaps remain. The one BLOCKER from the prior verification pass (CR-01: duplicate `scheduled_date` across sessions when `preferred_days` is shorter than the weekly session count) was independently re-reproduced against current code and confirmed fixed — the same input that previously produced 8 duplicate-date pairs out of 16 sessions now produces 16 unique dates. The recommended non-blocking item (WR-06: SSE partial-text persistence on abnormal termination) was also independently confirmed fixed via direct code read and a targeted test run.

The pre-existing, unrelated `tests/agent/test_sse.py::TestSSEEventSequence` failures (8 tests, JWT-auth-gated endpoint) were re-examined rather than accepted uncritically: their root cause (commit `b3fcf39`, 2026-07-02) genuinely predates and is unrelated to this phase's gap-closure work, is already tracked in three separate deferred-items.md files across Phases 06/07/03, and is already scoped to Phase 10. This classification holds and is not treated as a Phase 03 gap.

WR-01 through WR-05 (lower-priority findings from the original 03-REVIEW.md) are correctly documented as deferred — preserved in the prior VERIFICATION.md's gaps summary, restated explicitly in 03-06-PLAN.md's "Explicitly deferred" section, and recoverable in full from git history (`a98fb87`). None independently fails a Phase 03 success criterion. They are not lost, only deprioritized, consistent with the phase's own stated scope boundary.

**Phase 03 goal is achieved:** a new user can complete the onboarding interview, receive a safe RPE/HR-first plan, upload a real .FIT file that correctly updates the PMC and links to the correct session (no more silent date collisions), and see the plan adapt with a cited sports-science explanation that is reliably persisted to chat only when the turn actually completed.

---

_Verified: 2026-07-07T15:57:29Z_
_Verifier: Claude (gsd-verifier)_
