---
phase: quick-260702-vsp
plan: 01
subsystem: trust-model
tags: [trust-scanner, security, regex, false-positive]

requires: []
provides:
  - "Pattern A attribution fallback to bare number, mirroring Pattern B"
  - "Regression + safety negative-control tests locking in the fix"
affects: [onboarding, chat, trust-enforcement]

tech-stack:
  added: []
  patterns:
    - "Attribution candidate list [matched, bare_number] checked against tool_result_values (mirrors Pattern B's [full_match, synthetic, num])"

key-files:
  created: []
  modified:
    - backend/agent/trust.py
    - tests/agent/test_trust.py

key-decisions:
  - "Fixed only Pattern A's attribution check, not the detection regexes (PHYSIO_PATTERN_A/B) or Pattern B's logic — the bug was purely in how a detected match gets attributed to a tool result, not in what counts as a physio-number match"
  - "Accepted that the bare-number fallback gives Pattern A the same attribution blast radius Pattern B already has (a coincidental digit match in an unrelated JSON value could theoretically attribute a hallucination) — this is a pre-existing, out-of-scope risk already present in Pattern B, not introduced or worsened by this fix"
  - "Updated one existing test (test_attribution_substring_match) that had asserted the exact buggy behavior being fixed, with an explicit docstring justification referencing this quick task, rather than leaving a test that encodes a known bug as 'passing'"
  - "Added a safety negative-control test (test_pattern_a_unattributed_number_still_flagged) to lock in that a hallucinated number is still caught even when tool_result_values is non-empty — this is what prevents the fix from silently weakening trust enforcement"

patterns-established: []

requirements-completed: [TRUST-04, TRUST-03]

coverage:
  - id: D1
    description: "scan_buffer('...134 bpm...', {JSON containing 134}) returns None — Pattern A false positive fixed"
    requirement: "TRUST-04"
    verification:
      - kind: unit
        ref: "tests/agent/test_trust.py::TestScanBuffer::test_pattern_a_number_unit_attributed_via_json_value"
        status: pass
    human_judgment: false
  - id: D2
    description: "scan_buffer('...300 watts...', {JSON NOT containing 300}) still returns a TrustViolation — hallucinated number still caught"
    requirement: "TRUST-03"
    verification:
      - kind: unit
        ref: "tests/agent/test_trust.py::TestScanBuffer::test_pattern_a_unattributed_number_still_flagged"
        status: pass
    human_judgment: false
  - id: D3
    description: "All tests/agent/test_trust_corpus.py tests still pass (zero false negatives / zero false positives preserved)"
    requirement: "TRUST-03"
    verification:
      - kind: unit
        ref: "tests/agent/test_trust_corpus.py (test_violations_all_flagged, test_qualitative_no_false_positive, test_attributed_passes, test_false_positive_rate_is_zero, test_false_negative_rate_is_zero — all pass)"
        status: pass
    human_judgment: false
  - id: D4
    description: "A real onboarding confirmation turn (calculate_hr_zones + generate_plan output referenced in prose) no longer trips trust_violation / max_retries in production"
    requirement: "TRUST-04"
    verification: []
    human_judgment: true
    rationale: "Not driven from within this executor per plan constraints — full live confirmation happens via the ongoing Playwright E2E test session after this deploy."

duration: 12min
completed: 2026-07-02
status: complete
---

# Quick Task 260702-vsp: Fix trust scanner Pattern A false positive Summary

**Added a bare-number attribution fallback to the trust scanner's Pattern A (number+unit) check, fixing a false positive that was blocking every onboarding confirmation from completing — tool results serialize as JSON (`"lower_bpm": 134`), never as adjacent "number unit" prose, so Pattern A could never attribute a real tool-sourced number.**

## Performance

- **Duration:** ~12 min
- **Tasks:** 3/3 complete (TDD: RED, GREEN, verify+ship)
- **Files modified:** 2

## Accomplishments
- `backend/agent/trust.py`: Pattern A's attribution check now falls back to the bare number extracted from the match (`re.match(r"\d+(?:\.\d+)?", matched)`), checked against `tool_result_values` alongside the full matched string — mirroring Pattern B's existing `[full_match, synthetic, num]` approach exactly.
- `tests/agent/test_trust.py`: added `test_pattern_a_number_unit_attributed_via_json_value` (regression, reproduces the exact live false positive) and `test_pattern_a_unattributed_number_still_flagged` (safety negative control, proves a hallucinated number is still caught). Updated `test_attribution_substring_match`, which had asserted the buggy behavior, with a documented justification.
- Verified RED before the fix (both new/updated tests failed against unmodified `trust.py`), then GREEN after (all 72 tests across `test_trust.py` + `test_trust_corpus.py` pass, including the corpus's `test_false_positive_rate_is_zero` and `test_false_negative_rate_is_zero`).
- Ran the full backend suite (`pytest tests/ -q`): 9 pre-existing failures in `test_sse.py` and `test_capability_gap.py`, confirmed unrelated by stashing this fix and re-running — identical failures on unmodified code. Not caused by this change; left untouched (out of scope).
- Committed and pushed to `origin/main` (`e1b6d88`), auto-deploying the Vercel Python function.

## Task Commits

1. **Task 1: Add regression + safety tests, correct the buggy-behavior test (RED)** - included in `e1b6d88`
2. **Task 2: Add bare-number fallback to Pattern A (GREEN)** - included in `e1b6d88`
3. **Task 3: Full suite + commit + push** - `e1b6d88` (fix)

## Files Created/Modified
- `backend/agent/trust.py` - Pattern A attribution now checks `(matched, bare_number)` against tool_result_values
- `tests/agent/test_trust.py` - two new tests, one corrected test with documented rationale

## Decisions Made
- Did not touch `PHYSIO_PATTERN_A`/`PHYSIO_PATTERN_B`/`PHYSIO_PATTERN` regexes or Pattern B's logic — only Pattern A's post-match attribution decision changed.
- Accepted that the bare-number fallback gives Pattern A the same (not worse) attribution looseness Pattern B already has; tightening that shared looseness was explicitly out of scope.
- Updated `test_attribution_substring_match` rather than leaving it green-but-wrong, since it asserted the identical bug shape being fixed; documented why in its docstring for future auditability.

## Deviations from Plan
None — plan executed exactly as written, including the TDD RED/GREEN sequence and the pre-existing-failure verification via git stash.

## Issues Encountered
- Full `tests/` run surfaced 9 failures outside the scope of this fix (`test_sse.py`, `test_capability_gap.py`). Confirmed pre-existing (identical failures with this fix stashed out) — not investigated further, out of scope for this task.

## User Setup Required
None.

## Next Phase Readiness
- Combined with the `save_profile` column fix (260702-vs6, executed in the same session), the onboarding confirmation flow should now complete end-to-end in production. Full live confirmation is happening via the ongoing Playwright E2E test session.
- The 9 pre-existing test failures in `test_sse.py`/`test_capability_gap.py` are worth a follow-up investigation at some point — not blocking, not part of this session's scope.

---
*Quick task: 260702-vsp*
*Completed: 2026-07-02*
</content>
