---
phase: 08-trust-model-integrity
plan: 08
subsystem: agent
tags: [trust-scanner, attribution, onboarding, python, pytest]

# Dependency graph
requires:
  - phase: 08-trust-model-integrity
    provides: scan_buffer/_is_attributed tool_result_values attribution channel (Plan 04), cross-turn audit seeding (Plan 05/TRUST-09)
provides:
  - "collect_self_reported_values(messages) pure extractor in backend/agent/trust.py"
  - "self_reported_values as a distinct scan_buffer attribution channel, same numeric-token + tolerance rigor as tool_result_values"
  - "run_turn per-turn self-report snapshot threaded into every trust_scanner call"
  - "ONBD-05 Branch A (user states LTHR directly, no tool call) now passes end-to-end"
affects: [09-frontend-resilience, onboarding, agent-loop]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Distinct attribution channels resolved by the same _is_attributed helper, checked via two separate calls (never merged into one list) so each channel's security narrative stays explicit in code"
    - "Self-report snapshot taken once, before the while loop, from role==\"user\" string messages only — excludes assistant text and tool-result content-block lists to prevent echo->source laundering"

key-files:
  created: []
  modified:
    - backend/agent/trust.py
    - backend/agent/loop.py
    - tests/agent/conftest.py
    - tests/agent/test_trust.py
    - tests/agent/test_loop.py

key-decisions:
  - "self_reported_values is a third, optional scan_buffer parameter (default None) rather than merging into tool_result_values — keeps the tool-result and self-report attribution sources structurally distinct for the security narrative (T-08-08-01/02/03) and preserves 100% backward compatibility for every existing 2-argument call site"
  - "Extraction snapshot taken once before run_turn's while loop, not per-iteration — ensures the loop's own corrective/retry user message and any tool-result content-block lists can never enter the self-report channel"

requirements-completed: [ONBD-05, TRUST-03]

coverage:
  - id: D1
    description: "collect_self_reported_values extracts only role==\"user\" string-content messages, excluding assistant text and non-string (tool-result block) content"
    requirement: "TRUST-03"
    verification:
      - kind: unit
        ref: "tests/agent/test_trust.py::TestSelfReportedAttribution::test_collect_self_reported_values_keeps_user_string_content"
        status: pass
      - kind: unit
        ref: "tests/agent/test_trust.py::TestSelfReportedAttribution::test_collect_self_reported_values_excludes_assistant_messages"
        status: pass
      - kind: unit
        ref: "tests/agent/test_trust.py::TestSelfReportedAttribution::test_collect_self_reported_values_excludes_non_string_user_content"
        status: pass
      - kind: unit
        ref: "tests/agent/test_trust.py::TestSelfReportedAttribution::test_collect_self_reported_values_empty_input_returns_empty_list"
        status: pass
    human_judgment: false
  - id: D2
    description: "scan_buffer attributes a self-reported number (Branch A positive) while still flagging a hallucinated number absent from both channels (anti-laundering negative control) and rejecting substring bypasses"
    requirement: "TRUST-03"
    verification:
      - kind: unit
        ref: "tests/agent/test_trust.py::TestSelfReportedAttribution::test_branch_a_self_reported_lthr_echo_is_not_violation"
        status: pass
      - kind: unit
        ref: "tests/agent/test_trust.py::TestSelfReportedAttribution::test_anti_laundering_hallucinated_number_still_violates"
        status: pass
      - kind: unit
        ref: "tests/agent/test_trust.py::TestSelfReportedAttribution::test_boundary_safety_no_substring_bypass"
        status: pass
      - kind: unit
        ref: "tests/agent/test_trust.py::TestSelfReportedAttribution::test_distinct_channel_self_report_only_number_attributes"
        status: pass
      - kind: unit
        ref: "tests/agent/test_trust.py::TestSelfReportedAttribution::test_backward_compatible_two_argument_call_unaffected"
        status: pass
    human_judgment: false
  - id: D3
    description: "ONBD-05 Branch A completes end-to-end through run_turn (user-stated LTHR echoed in the confirmation summary, no tool call) with a done event and zero trust_violation/max_retries events; a hallucinated number in the same shape still violates"
    requirement: "ONBD-05"
    verification:
      - kind: integration
        ref: "tests/agent/test_loop.py::test_self_reported_lthr_echo_passes_branch_a"
        status: pass
      - kind: integration
        ref: "tests/agent/test_loop.py::test_self_reported_control_hallucinated_number_still_violates"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-07-06
status: complete
---

# Phase 8 Plan 08: Self-Reported Attribution Channel Summary

**Closed the ONBD-05 Branch A blocker by adding a distinct `self_reported_values` attribution channel to the trust scanner, sourced from the user's own chat messages, so a directly-stated LTHR can be confirmed with no tool call and no false trust_violation.**

## Performance

- **Duration:** 15 min
- **Completed:** 2026-07-06T16:27:50Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- `collect_self_reported_values(messages)` pure extractor added to `backend/agent/trust.py` — filters `role=="user"` string content only, never raises
- `scan_buffer` gained a third, backward-compatible `self_reported_values` parameter checked via a separate `_is_attributed` call per channel (never merged), preserving the D-03/TRUST-08 numeric-token + tolerance rigor and the boundary-aware substring-collision protections for the new channel
- `run_turn` now takes a one-time snapshot of `self_reported_values` before the while loop and threads it into every `trust_scanner` call, so the loop's own retry/correction message can never leak into the self-report channel
- ONBD-05 Branch A (user states LTHR directly, assistant restates it in the D-03 confirmation-gate summary, no tool call) now completes with a `done` event and zero `trust_violation`/`max_retries` events, proven end-to-end with the real `scan_buffer`
- Anti-laundering negative control proven at both the unit level (`TestSelfReportedAttribution`) and the loop-integration level (`test_self_reported_control_hallucinated_number_still_violates`): a hallucinated number absent from every user message and every tool result is still flagged

## Task Commits

Each task was committed atomically:

1. **Task 1: Add a self-reported attribution channel to trust.py** - `409877e` (feat)
2. **Task 2: Thread per-turn self-report extraction through run_turn** - `79ec044` (feat)

**Plan metadata:** (this commit, docs: complete plan)

## Files Created/Modified
- `backend/agent/trust.py` - `collect_self_reported_values` extractor + `self_reported_values` attribution channel in `scan_buffer`
- `backend/agent/loop.py` - per-turn `self_reported_values` snapshot (before the while loop) threaded into every `trust_scanner` call
- `tests/agent/conftest.py` - `no_op_scanner` / `always_violating_scanner` updated to the 3-argument scanner signature
- `tests/agent/test_trust.py` - `TestSelfReportedAttribution` (extractor filtering, Branch A positive, anti-laundering control, boundary safety, distinct-channel, backward compatibility)
- `tests/agent/test_loop.py` - `test_self_reported_lthr_echo_passes_branch_a` + `test_self_reported_control_hallucinated_number_still_violates`

## Decisions Made
- Kept `tool_result_values` and `self_reported_values` as two structurally distinct lists, each checked via its own `_is_attributed` call, rather than merging them into a single allowlist — this keeps the security narrative for each channel explicit (self-report never authorizes a tool's computed-output field) and matches the plan's `must_haves.key_links` requirement.
- Took the self-report snapshot once, before `run_turn`'s while loop, exactly mirroring the existing `tool_result_values` cross-turn seeding position, so retries and tool-result content-block lists can never contaminate the channel.

## Deviations from Plan

None — plan executed exactly as written. One process note: Task 1 was tagged `tdd="true"`, but the test additions (`TestSelfReportedAttribution`) and the implementation (`collect_self_reported_values` + the `scan_buffer` channel) were written and committed together in a single `feat` commit rather than as separate RED (`test(...)`) then GREEN (`feat(...)`) commits. See TDD Gate Compliance below.

## Issues Encountered
None. Both tasks' verification commands passed on the first run; no auto-fixes were needed.

## TDD Gate Compliance

Task 1 (`tdd="true"`) does not have a separate `test(...)` RED commit preceding the `feat(...)` GREEN commit — both the new `TestSelfReportedAttribution` tests and the `collect_self_reported_values`/`scan_buffer` implementation landed in the single commit `409877e`. The tests were written and verified failing-then-passing in-session before committing (the RED/GREEN discipline was followed in spirit — implementation was driven by the test behavior spec in the plan's `<behavior>` block), but the git history does not carry the distinct `test(...)` -> `feat(...)` gate-sequence commits the TDD execution flow expects. No functional impact: `tests/agent/test_trust.py::TestSelfReportedAttribution` (9 tests) and the full `test_trust.py` + `test_trust_corpus.py` suites are green.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- ONBD-05 Branch A is now unblocked; the full agent test surface relevant to this plan (`test_trust.py` + `test_loop.py` + `test_trust_corpus.py`, 103 tests) is green.
- No changes were made to `backend/routes/onboarding.py`, `backend/routes/_sse.py`, or `backend/routes/chat.py` — the fix is entirely internal to `run_turn`'s extraction, as the plan required.
- Pre-existing, unrelated failures in `tests/agent/test_sse.py` (8 tests, all a 401-vs-422 auth-status mismatch) were observed during the full `tests/agent` sweep; confirmed via `git stash` to pre-exist this plan's changes and are out of this plan's scope (not modified, not caused by this diff).
- Recommend live re-verification of ONBD-05 Branch A (the original UAT reproduction conversation flow) as the closing step for Phase 8's UAT gap before milestone completion.

---
*Phase: 08-trust-model-integrity*
*Completed: 2026-07-06*

## Self-Check: PASSED

All created/modified files verified present on disk; both task commits (409877e, 79ec044) verified present in git log.
