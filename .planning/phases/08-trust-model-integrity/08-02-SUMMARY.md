---
phase: 08-trust-model-integrity
plan: 02
subsystem: trust-model
tags: [regex, python, pytest, agent, security]

# Dependency graph
requires:
  - phase: 04-agent-trust-loop
    provides: original scan_buffer implementation with Pattern A/B substring attribution and the false-positive/false-negative corpus (test_trust_corpus.py)
provides:
  - Boundary-aware numeric-token extraction (_NUMERIC_TOKEN) + tolerance compare (NUMERIC_TOLERANCE) replacing raw substring membership in scan_buffer's attribution checks
  - _is_attributed(candidate_str, tool_result_values) pure helper as the single attribution decision point for both Pattern A and Pattern B
  - Regression test suite proving the substring-collision bypass (250 attributed by 2500/0.250/timestamp digit runs) is closed while real JSON attribution still passes
affects: [08-01, 08-09-integration-if-any, future trust-model work touching agent/trust.py]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Boundary-aware numeric token extraction via negative lookaround regex (?<![\\d.]) ... (?!\\d) instead of substring membership, for any 'is this number present in this JSON blob' check"

key-files:
  created: []
  modified:
    - backend/agent/trust.py
    - tests/agent/test_trust.py

key-decisions:
  - "Kept NUMERIC_TOLERANCE as a named module constant (0.01) per RESEARCH.md Pitfall 3/Assumption A1 -- validated against the existing zero-false-positive/zero-false-negative corpus rather than re-tuned"
  - "Removed the now-dead 'synthetic' string (f'{num} {unit}') from Pattern B since _is_attributed only needs the bare numeric candidate, simplifying the attribution call site"

requirements-completed: [TRUST-08, TRUST-03]

coverage:
  - id: D1
    description: "scan_buffer's Pattern A and Pattern B attribution checks use boundary-aware numeric-token + tolerance matching instead of raw substring membership, closing the D-03 substring-collision bypass"
    requirement: "TRUST-08"
    verification:
      - kind: unit
        ref: "tests/agent/test_trust.py::TestSubstringCollisionBypass -- five new regression cases (longer digit run, decimal substring, real JSON attribution x2, timestamp digit run)"
        status: pass
      - kind: unit
        ref: "tests/agent/test_trust_corpus.py::test_false_positive_rate_is_zero and test_false_negative_rate_is_zero"
        status: pass
    human_judgment: false
  - id: D2
    description: "Existing TRUST-03 detection and TRUST-04 attribution behavior (full test_trust.py suite, including loop-level compliance tests) remains green after the rewrite"
    requirement: "TRUST-03"
    verification:
      - kind: unit
        ref: "tests/agent/test_trust.py (38 tests) and tests/agent/test_trust_corpus.py (39 tests) -- full run"
        status: pass
    human_judgment: false

duration: 12min
completed: 2026-07-04
status: complete
---

# Phase 08 Plan 02: Trust Scanner Numeric-Token Attribution Summary

**Closed the trust-scanner's substring-attribution bypass by replacing raw `s in val` membership checks with a boundary-aware numeric-token regex plus 0.01 float-tolerance compare, so "250" can no longer be falsely attributed by an unrelated "2500", "0.250", or timestamp digit run in a tool result.**

## Performance

- **Duration:** 12 min
- **Started:** 2026-07-04T20:34:36Z
- **Completed:** 2026-07-04T20:46:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Replaced both Pattern A and Pattern B substring-based attribution checks in `scan_buffer` with a single pure `_is_attributed(candidate_str, tool_result_values)` helper built on a boundary-aware `_NUMERIC_TOKEN` regex and `NUMERIC_TOLERANCE = 0.01`
- Closed the D-03 substring-collision bypass: a bare number is now only attributed when it numerically matches (within tolerance) a numeric token that stands on its own boundaries inside a tool-result string
- Added five regression tests locking in the fix (longer digit run, decimal substring, two real-attribution survival cases, timestamp digit run) plus verified the existing zero-false-positive/zero-false-negative corpus (`test_trust_corpus.py`) stays green

## Task Commits

Each task was committed atomically:

1. **Task 1: Replace substring attribution with numeric-token + tolerance matching** - `63e6155` (feat)
2. **Task 2: Add regression tests for the substring-collision class** - `8a9ff75` (test)

**Plan metadata:** committed by orchestrator after wave completion (worktree mode -- STATE.md/ROADMAP.md not touched here)

## Files Created/Modified
- `backend/agent/trust.py` - Added `_NUMERIC_TOKEN` compiled regex, `NUMERIC_TOLERANCE` constant, `_is_attributed` pure helper; rewrote Pattern A and Pattern B attribution decisions to call it instead of raw substring membership; docstrings updated to describe the numeric-token/tolerance contract (TRUST-08)
- `tests/agent/test_trust.py` - Added `TestSubstringCollisionBypass` class with five regression tests proving the bypass is closed and real attribution still passes

## Decisions Made
- Kept `NUMERIC_TOLERANCE = 0.01` as specified in RESEARCH.md Pattern 3 / Pitfall 3 -- validated against the corpus rather than re-tuned, since it correctly handles both one-decimal domains (TSS/IF/CTL/ATL) and integer-rounded watts/bpm (180 vs 180.0 differ by 0.0)
- Dropped the now-unused `synthetic` string construction in Pattern B (`f"{num} {unit}"`) since `_is_attributed` only needs the bare numeric candidate; simplifies the attribution call site without changing behavior

## Deviations from Plan

None - plan executed exactly as written. Task 1's implementation matched RESEARCH.md Pattern 3 and PATTERNS.md's `trust.py::scan_buffer` guidance verbatim; Task 2's five test cases matched the plan's `<behavior>` spec exactly (250/2500, 250/0.250, ftp_watts JSON, lower_bpm/upper_bpm JSON, CTL 42/timestamp).

## Issues Encountered

None. The worktree lacked its own `.venv` (untracked by git), so tests were run via the main repo's `.venv/bin/python` interpreter with the worktree directory as cwd -- this is an execution-environment detail, not a plan deviation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `scan_buffer`'s attribution logic is now hardened against the substring-collision bypass; `handle_violation` and the pure/synchronous contract are unchanged, so no other trust-model consumers (agent/loop.py, routes/chat.py, routes/onboarding.py) require changes for this fix
- The full `tests/agent/test_trust.py` + `tests/agent/test_trust_corpus.py` suite (77 tests) is green; a broader `tests/agent` run shows only the 8 pre-existing `test_sse.py` failures (unrelated to this plan, not introduced by it)
- No blockers for sibling wave-1 plans (08-01, 08-03, 08-04) or later phase-08 plans that build on trust.py's attribution contract

---
*Phase: 08-trust-model-integrity*
*Completed: 2026-07-04*
