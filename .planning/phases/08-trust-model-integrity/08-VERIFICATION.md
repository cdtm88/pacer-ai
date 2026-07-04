---
phase: 08-trust-model-integrity
verified: 2026-07-04T22:30:00Z
status: human_needed
score: 12/12 must-haves verified (code-level); 1 item requires live human verification
behavior_unverified: 0
overrides_applied: 0
must_haves:
  truths:
    - "TRUST-06: audit_log Postgres table persisted, one row per tool dispatch, queryable by user_id+conversation_id"
    - "TRUST-04 (re-verify): every physiological number traceable to a tool-library call, verifiable in application logs"
    - "TRUST-08: bare-number attribution uses numeric-token + tolerance matching, not substring"
    - "TRUST-03 (re-verify): unsourced physiological numbers still trigger retry + capability-gap log after the attribution rewrite"
    - "TRUST-09: tool_result_values seeded from persisted audit_log at start of every turn, killing cross-turn false positives"
    - "TRUST-07: generate_plan's trust-sensitive inputs (current_ctl, ftp_watts, ftp_confidence, load_targets, preferred_days, hr_zones) are server-injected; LLM-supplied values discarded"
    - "ONBD-05: onboarding collects LTHR / max-HR-estimate / neither, with an explicit hr_zones_available flag and RPE-only fallback; LLM never invents LTHR"
    - "TOOL-02 (amend): HR_ZONE_BOUNDARIES corrected to true Coggan/Allen percentages; Zone 2 ceiling drops to 0.83 for beginner safety"
    - "PLAN-07: generate_plan consumes current_ctl/load_targets/preferred_days for CTL-gap-aware progression and real day scheduling"
    - "PLAN-06 (re-verify): every physiological number in a generated plan traceable to a tool-library call"
    - "save_profile's lthr_estimate is cross-checked against this-turn's estimate_lthr_from_max_hr result (CR-02), closing a second number-laundering path"
    - "chat_stream's client-supplied conversation_id is validated for format+ownership before touching audit writes / message persistence (CR-03)"
  artifacts:
    - supabase/migrations/0009_audit_log_and_hr_zones_flag.sql
    - backend/agent/audit.py
    - backend/agent/trust.py
    - backend/agent/loop.py
    - backend/agent/tools.py
    - backend/routes/_sse.py
    - backend/routes/chat.py
    - backend/routes/onboarding.py
    - backend/sports_science/constants.py
    - backend/sports_science/zones.py
    - backend/sports_science/plan.py
    - backend/sports_science/profile.py
  key_links:
    - "dispatch_tool -> write_audit_entry (all 4 outcomes) -> public.audit_log"
    - "run_turn -> load_prior_audit_values -> tool_result_values seed"
    - "dispatch_tool generate_plan branch -> pmc_history/profiles/same-turn audit_log -> discards LLM current_ctl/ftp_watts/ftp_confidence/load_targets/preferred_days/hr_zones"
    - "dispatch_tool save_profile branch -> same-turn estimate_lthr_from_max_hr audit entry -> overrides LLM lthr_estimate"
    - "chat_stream -> onboarding._resolve_conversation_id -> load_conversation/sse_generator/save_messages"
human_verification:
  - test: "Run a real onboarding conversation in a dev environment and exercise all three HR branches: (A) user states LTHR directly, (B) user gives only max HR, (C) user knows neither"
    expected: "The interview asks the HR baseline question before any plan/HR-zone tool call; Branch A uses the stated LTHR as-is; Branch B calls estimate_lthr_from_max_hr and presents the result as an estimate (not measured); Branch C skips calculate_hr_zones entirely and the plan falls back to RPE-only targets; profiles.hr_zones_available is true for A/B and false for C"
    why_human: "This is LLM-driven conversational behavior — the exact wording/timing and whether the model actually follows the three-branch instruction at runtime cannot be proven by unit tests of the prompt string alone (explicitly flagged Manual-Only in 08-VALIDATION.md)"
---

# Phase 8: Trust Model Integrity Verification Report

**Phase Goal:** The trust model is airtight and verifiable: audit log persisted per turn (TRUST-04), tool inputs scanned so invented numbers cannot launder through tool calls, bare-number attribution uses word-boundary and tolerance matching instead of substring, prior-turn numbers seeded to kill cross-turn false positives, LTHR (or explicit RPE-only fallback) collected in onboarding, HR zone constants match the claimed Coggan methodology, Zone 2 targets safe for a returning beginner, and generate_plan consumes current_ctl/load_targets/preferred_days so back-protective caps actually constrain sessions.

**Verified:** 2026-07-04T22:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

This verification went beyond trusting 08-SUMMARY.md claims: every plan's `must_haves` was cross-checked against the actual source (not just grep for keyword presence), the full test suite was re-run from a clean invocation (not copy-pasted from the SUMMARY), and — because the task explicitly called out CR-01/CR-02 as "literal instances of the exact number-laundering bug class this phase exists to close" — the post-review fix commits (dc2cf7c, d3fb62a, 634326f, 14b0aa5, b3568d7, 11c4e83, fc30676) were read in full and their regression tests inspected line-by-line, not just counted.

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | TRUST-06: `audit_log` table persisted, one row/dispatch, queryable by user_id+conversation_id | ✓ VERIFIED | Migration `0009_audit_log_and_hr_zones_flag.sql` contains the 9-column table + RLS policy + composite index; `supabase migration list --linked` run live during this verification shows Local==Remote at `0009` (table is live in the linked project, not just in a file). `dispatch_tool` (backend/agent/tools.py:648,672,819,841) calls `write_audit_entry` on all 4 dispatch outcomes (unknown tool, missing identity, success, exception). |
| 2 | TRUST-04 (re-verify): every physiological number traceable to a tool call, verifiable in logs | ✓ VERIFIED | Durable audit_log row per dispatch (above) plus CR-01/CR-02 fixes close the two remaining laundering paths (hr_zones, lthr_estimate) that the code-reviewer found after the 7 plans executed — strengthens rather than merely preserves TRUST-04. |
| 3 | TRUST-08: numeric-token + tolerance attribution, not substring | ✓ VERIFIED | `backend/agent/trust.py` `_NUMERIC_TOKEN`/`NUMERIC_TOLERANCE`/`_is_attributed`; `tests/agent/test_trust.py` + `test_trust_corpus.py` pass (72 tests incl. WR-04 date-collision regressions), run live: `2500`/`0.250`/timestamp no longer attribute `250`/`42`. |
| 4 | TRUST-03 (re-verify): violations still trigger retry + capability-gap log | ✓ VERIFIED | `scan_buffer`'s Pattern A/B structure and `handle_violation` untouched; `test_trust_violation_triggers_retry` and the full corpus pass. |
| 5 | TRUST-09: `tool_result_values` seeded from `audit_log` at turn start | ✓ VERIFIED | `backend/agent/loop.py:100-103` extends `tool_result_values` from `load_prior_audit_values` before the first scan when `conversation_id` is set; `test_cross_turn_seed_suppresses_false_positive` and its `conversation_id=None` control both pass. |
| 6 | TRUST-07: generate_plan's trust-sensitive inputs server-injected, LLM values discarded | ✓ VERIFIED | `dispatch_tool`'s `generate_plan` branch (tools.py:688-776) discards and overrides current_ctl/ftp_watts/ftp_confidence/load_targets/preferred_days **and** hr_zones (CR-01 closure); schema no longer declares these as required; `test_generate_plan_injection_discards_llm_values`, `..._discards_llm_hr_zones`, `..._hr_zones_defaults_empty_when_skipped` all pass. |
| 7 | ONBD-05: LTHR/max-HR/neither collected; explicit hr_zones_available flag; LLM never invents LTHR | ✓ VERIFIED (code) / **human check required for live conversational behavior** | `ONBOARDING_SYSTEM_PROMPT` (onboarding.py:58-102) specifies the 3 branches, names `estimate_lthr_from_max_hr`, and the RPE-only fallback; `save_profile` persists `hr_zones_available = lthr_estimate is not None` (profile.py:107); `dispatch_tool`'s save_profile branch cross-checks `lthr_estimate` against this turn's `estimate_lthr_from_max_hr` audit entry (CR-02) rather than trusting the LLM unconditionally. Prompt-contract + persistence tests pass. The live "does the model actually ask the question and follow the branch at the right point" behavior is inherently unit-untestable and was already flagged Manual-Only in 08-VALIDATION.md — routed to human verification below. |
| 8 | TOOL-02 (amend): HR_ZONE_BOUNDARIES = true Coggan/Allen; Zone 2 ceiling 0.83 | ✓ VERIFIED | `constants.py` HR_ZONE_BOUNDARIES: Z1 0.00-0.68, Z2 0.68-0.83, Z3 0.83-0.94, Z4 0.94-1.05, Z5 1.05+; contiguous; `estimate_lthr_from_max_hr` registered in both TOOL_REGISTRY and TOOL_SCHEMAS (TRUST-02 invariant holds); `tests/sports_science/test_zones.py` boundary + Zone-2-ceiling + estimator tests pass. |
| 9 | PLAN-07: generate_plan consumes current_ctl/load_targets/preferred_days | ✓ VERIFIED | `_is_true_beginner_ramp` flattens weeks 2-3 and tightens week 1 for a true low-base/back-moderate beginner; `preferred_days` cycles (not truncates, WR-01 fix) via `[preferred_days[i % len(preferred_days)] for i in range(n_sessions)]`; `tests/sports_science/test_plan.py` (12 cases incl. non-beginner-preserved and preferred_days-cycling) pass. |
| 10 | PLAN-06 (re-verify): every physiological number in a plan traceable to a tool call | ✓ VERIFIED | `_build_zone2_targets`/`_build_power_targets` consume server-injected hr_zones/ftp_watts (not raw LLM input, post CR-01); WR-02 fix makes `plans.ftp_confidence` actually persist the server-injected value instead of permanent NULL. |
| 11 | save_profile's lthr_estimate cross-checked against tool result (CR-02) | ✓ VERIFIED | `dispatch_tool`'s save_profile branch (tools.py:777-791): when a same-turn `estimate_lthr_from_max_hr` audit entry exists, `lthr_estimate` is unconditionally overridden from it; Branch A (self-report) and Branch C (no LTHR) pass through unchanged since no computed value exists to launder. `test_dispatch_tool_save_profile_overrides_lthr_from_tool_result` and `..._keeps_llm_lthr_when_no_tool_call` pass. |
| 12 | chat_stream conversation_id ownership validated (CR-03) | ✓ VERIFIED | `chat.py` now calls `onboarding._resolve_conversation_id` before `load_conversation`/`sse_generator`/`save_messages`; a malformed or foreign id short-circuits with an `invalid_conversation_id` SSE error frame. `tests/api/test_chat.py` (malformed-rejected / foreign-rejected / owned-proceeds) all pass. |

**Score:** 12/12 code-level truths verified (0 present-but-behavior-unverified); 1 truth (ONBD-05's live conversational flow) additionally requires a human-run onboarding session per 08-VALIDATION.md's own Manual-Only classification.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `supabase/migrations/0009_audit_log_and_hr_zones_flag.sql` | audit_log table + RLS + index + hr_zones_available column | ✓ VERIFIED | All 4 DDL statements present; confirmed applied to the linked project live (`supabase migration list --linked` shows 0009 at Remote). |
| `backend/agent/audit.py` | write_audit_entry + load_prior_audit_values, best-effort, using centralized client | ✓ VERIFIED | No new `_supabase_client` singleton; imports `get_async_supabase` from `backend.db`; both functions wrapped in try/except returning gracefully. |
| `backend/agent/trust.py` | numeric-token + tolerance attribution, JSON-leaf-aware (WR-04) | ✓ VERIFIED | `_NUMERIC_TOKEN`, `NUMERIC_TOLERANCE`, `_is_attributed`, `_collect_numeric_leaves` all present and wired into both Pattern A and Pattern B paths. |
| `backend/agent/loop.py` | conversation_id threading + seeding | ✓ VERIFIED | `run_turn` accepts `conversation_id`, seeds `tool_result_values` before the while-loop, passes it to `dispatch_tool`. |
| `backend/agent/tools.py` | dispatch_tool writes durable audit rows + injects 6 generate_plan keys + cross-checks save_profile lthr_estimate | ✓ VERIFIED | All confirmed by direct source read (lines 604-856); matches SUMMARY and REVIEW-FIX claims exactly, not just in spirit. |
| `backend/routes/_sse.py`, `chat.py`, `onboarding.py` | conversation_id threading + ownership validation | ✓ VERIFIED | `_sse.py` forwards conversation_id via kwargs; `chat.py` validates via `_resolve_conversation_id` before any read/write (CR-03); `onboarding.py` already had this from Phase 7 (WR-08), reused not reimplemented. |
| `backend/sports_science/constants.py`, `zones.py` | corrected HR zones + LTHR estimator | ✓ VERIFIED | Values and new tool match plan spec exactly. |
| `backend/sports_science/plan.py` | preferred_days + CTL-gap ramp + hr_zones-derived targets | ✓ VERIFIED | `_is_true_beginner_ramp`, day-cycling, zone2/power target builders present and match spec. |
| `backend/sports_science/profile.py` | hr_zones_available persistence | ✓ VERIFIED | Derived field written to the upsert; no new LLM-facing parameter added (as specified). |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|----|--------|---------|
| `dispatch_tool` (tools.py) | `public.audit_log` | `write_audit_entry` awaited on all 4 outcomes | ✓ WIRED | Confirmed at lines 648, 672, 819, 841. |
| `run_turn` (loop.py) | `public.audit_log` | `load_prior_audit_values` seeding | ✓ WIRED | Confirmed at loop.py:100-103; no-op when conversation_id is None. |
| `dispatch_tool` generate_plan branch | `pmc_history` / `profiles` / same-turn `audit_log` | Postgres query + `_last_audit_result` | ✓ WIRED | Confirmed at tools.py:695-776; discards 6 keys including hr_zones (CR-01). |
| `dispatch_tool` save_profile branch | same-turn `estimate_lthr_from_max_hr` audit entry | `_last_audit_result` override | ✓ WIRED | Confirmed at tools.py:777-791 (CR-02). |
| `chat_stream` (chat.py) | `onboarding._resolve_conversation_id` | import + await before any read/write | ✓ WIRED | Confirmed at chat.py:63-67, 118-138 (CR-03). |
| `calculate_hr_zones` result | `generate_plan`'s persisted `zone_targets` | server-injected hr_zones -> `_build_zone2_targets` | ✓ WIRED | No longer a raw LLM passthrough; sourced from this-turn's audit_log entry or `[]`. |

### Behavioral Spot-Checks / Test Suite

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full test suite baseline unchanged | `.venv/bin/python -m pytest tests/ -q` | `9 failed, 301 passed` — identical failure identities to the documented pre-existing baseline (8x test_sse.py stale-auth + 1x test_capability_gap.py test-order flake) | ✓ PASS (no regressions) |
| Phase 8-relevant test files, isolated | `pytest tests/agent/test_audit.py tests/agent/test_trust.py tests/agent/test_trust_corpus.py tests/sports_science/test_zones.py tests/sports_science/test_plan.py tests/agent/test_tools_phase3.py tests/agent/test_loop.py tests/api/test_onboarding.py tests/api/test_chat.py -q` | `164 passed` | ✓ PASS |
| TRUST-02 invariant + schema shrink | `python -c "from backend.agent.tools import TOOL_REGISTRY, TOOL_SCHEMAS; ..."` | generate_plan required == `['weekly_hours', 'back_status']`; properties == `['weekly_hours','back_status','hr_zones']`; registry/schema names match | ✓ PASS |
| Migration applied to live linked project | `supabase migration list --linked` | Local `0009` == Remote `0009` | ✓ PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| TRUST-06 | 08-01, 08-05 | audit_log persisted, queryable, wired into dispatch_tool | ✓ SATISFIED | See truths #1 above. |
| TRUST-04 (re-verify) | 08-01, 08-05 | physiological numbers traceable in logs | ✓ SATISFIED | See truth #2. |
| TRUST-08 | 08-02 | numeric-token + tolerance attribution | ✓ SATISFIED | See truth #3. |
| TRUST-03 (re-verify) | 08-02 | violations still enforced | ✓ SATISFIED | See truth #4. |
| TRUST-09 | 08-05 | cross-turn seeding | ✓ SATISFIED | See truth #5. |
| TRUST-07 | 08-06 | generate_plan server-injection | ✓ SATISFIED | See truth #6 (extended by CR-01 to include hr_zones). |
| ONBD-05 | 08-03, 08-07 | LTHR/max-HR/neither + hr_zones_available | ✓ SATISFIED (code) / human check pending | See truth #7. |
| TOOL-02 (amend) | 08-03 | corrected HR zone constants | ✓ SATISFIED | See truth #8. |
| PLAN-07 | 08-04, 08-06 | current_ctl/load_targets/preferred_days consumed | ✓ SATISFIED | See truth #9. |
| PLAN-06 (re-verify) | 08-04 | plan numbers traceable | ✓ SATISFIED | See truth #10. |

**Orphaned requirements check:** None. All Phase 8 requirement IDs declared across the 7 plans (TRUST-06, TRUST-08, TOOL-02, ONBD-05, PLAN-07, PLAN-06, TRUST-06 (again, 08-05), TRUST-09, TRUST-04, TRUST-07) appear in REQUIREMENTS.md's traceability table mapped to Phase 8, matching the phase's declared requirement set exactly.

**REQUIREMENTS.md staleness (documentation-only, not a functional gap):** REQUIREMENTS.md's checkbox for **ONBD-05** is still unchecked (`- [ ]`) and its traceability-table row plus **TOOL-02 (amend)**'s row are still marked "Pending" (lines 48, 178, 180), even though both are fully implemented, tested, and green (Plans 08-03 and 08-07 completed and were never followed by a REQUIREMENTS.md status-flip commit, unlike every other Phase 8 requirement which does show "Complete"). This is a bookkeeping gap in the tracking artifact itself, not in the code — flagged here since the task explicitly asked to cross-reference REQUIREMENTS.md. Recommend flipping the checkbox and traceability status to Complete as part of phase close-out; not blocking the phase goal, which is about code behavior.

### Anti-Patterns Found

None blocking. Two pre-existing `TODO` markers in `backend/routes/onboarding.py` (lines 23, 139, about deferring token-count-based message truncation to a documented future phase) predate this phase, are unrelated to trust-model integrity, and reference a specific deferred item (RESEARCH.md Open Question 5) — not flagged as phase-8 debt.

### Human Verification Required

### 1. Live onboarding conversation exercising all three HR branches

**Test:** Run a real onboarding conversation in a dev/staging environment. Provide (a) a stated LTHR, (b) only a max HR, (c) neither, across three separate interview runs.
**Expected:** The interview asks the heart-rate baseline question before any HR-zone/plan tool call. Branch A uses the stated LTHR as-is for `save_profile`/`calculate_hr_zones`. Branch B calls `estimate_lthr_from_max_hr`, tells the user the result is an estimate (not measured), and uses it for `save_profile`/`calculate_hr_zones`. Branch C tells the user the plan will use RPE targets, calls `save_profile` with no LTHR, and skips `calculate_hr_zones` entirely. `profiles.hr_zones_available` ends up `true` for A/B and `false` for C.
**Why human:** This is genuine LLM-driven conversational behavior — whether Claude actually asks the question at the right point and follows the three-branch instruction at runtime cannot be proven by a prompt-string content-assertion test. 08-VALIDATION.md itself classifies this as Manual-Only.

### Gaps Summary

No functional gaps. All 12 code-level must-have truths (spanning the phase's own plans plus the 7 post-review fixes on `main`) are genuinely implemented, wired, and covered by passing regression tests — not stubs, not partial fixes, not narrowly-scoped patches that miss the broader bug class. The two critical findings the task specifically asked to double-check (CR-01 hr_zones laundering, CR-02 lthr_estimate laundering) are closed with the same discard-and-server-inject pattern used for the original five TRUST-07 keys, and both are proven by tests that assert the bogus LLM-supplied value is replaced, not merely tolerated. The one remaining item (live onboarding conversation across all three branches) is inherent human-verification territory that the phase's own validation plan already scoped as Manual-Only, not a gap introduced by incomplete work. A minor REQUIREMENTS.md bookkeeping staleness (ONBD-05 / TOOL-02 amend rows not flipped to Complete) is noted for phase close-out but does not affect the goal achievement determination.

---

_Verified: 2026-07-04T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
