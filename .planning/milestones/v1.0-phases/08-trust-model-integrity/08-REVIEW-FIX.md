---
phase: 08-trust-model-integrity
fixed_at: 2026-07-04T21:45:00Z
review_path: .planning/phases/08-trust-model-integrity/08-REVIEW.md
iteration: 1
findings_in_scope: 7
fixed: 7
skipped: 0
status: all_fixed
---

# Phase 8: Code Review Fix Report

**Fixed at:** 2026-07-04T21:45:00Z
**Source review:** .planning/phases/08-trust-model-integrity/08-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 7 (3 critical, 4 warning)
- Fixed: 7
- Skipped: 0

## Fixed Issues

### CR-01: `generate_plan`'s `hr_zones` input is never server-verified

**Files modified:** `backend/agent/tools.py`, `tests/agent/test_tools_phase3.py`
**Commit:** dc2cf7c
**Applied fix:** `dispatch_tool`'s `generate_plan` server-injection block now sources
`hr_zones` from this turn's `calculate_hr_zones` audit_log entry (defaulting to `[]`
when no HR-zone tool ran this turn, e.g. onboarding Branch C), discarding any
LLM-supplied value the same way the existing five trust-sensitive keys are handled.
`hr_zones` was also removed from `generate_plan`'s schema `required` list (it is now
optional and always server-overridden) and the tool description was updated to
document the new discard/override behavior. Added 3 regression tests: discard of a
bogus LLM-supplied `hr_zones`, `[]` fallback when Branch C omits `calculate_hr_zones`
entirely, and a schema assertion that `hr_zones` is no longer required.

### CR-02: `save_profile`'s `lthr_estimate` is never cross-checked against `estimate_lthr_from_max_hr`

**Files modified:** `backend/agent/tools.py`, `tests/agent/test_tools_phase3.py`
**Commit:** d3fb62a
**Applied fix:** `dispatch_tool`'s `save_profile` branch now checks this turn's
audit_log for an `estimate_lthr_from_max_hr` entry; when present (Branch B), the
LLM-supplied `lthr_estimate` is unconditionally discarded and replaced with the
tool's actual result value. When no such entry exists (Branch A user self-report, or
Branch C no LTHR), the LLM-supplied value (or its absence) passes through unchanged,
since it is a legitimate self-report rather than a computed value in those branches.
Added 2 regression tests: override-from-tool-result (Branch B) and passthrough
when no tool call occurred (Branch A).

### CR-03: `/chat/stream` threads an unvalidated client-supplied `conversation_id`

**Files modified:** `backend/routes/chat.py`, `tests/api/test_chat.py` (new)
**Commit:** 634326f
**Applied fix:** `chat_stream` now reuses `onboarding.py`'s existing
`_resolve_conversation_id` helper (format validation + ownership check, WR-08/phase 07)
rather than reimplementing it -- imported directly into `chat.py` (no circular-import
risk, since `chat.py` already imports other helpers from `onboarding.py`). A malformed
or foreign `conversation_id` now short-circuits with an `event: error` SSE frame
(`code: "invalid_conversation_id"`) before `load_conversation`, `sse_generator`
(audit_log writes via `dispatch_tool`), or `save_messages` are ever called. Added a
new test file with 3 regression tests: malformed id rejected (no DB query at all),
foreign/unowned id rejected (ownership check fails), and a valid owned id proceeding
normally through the SSE stream.

### WR-01: `_build_sessions` silently drops sessions when `preferred_days` is shorter than the computed session count

**Files modified:** `backend/sports_science/plan.py`, `tests/sports_science/test_plan.py`
**Commit:** 14b0aa5
**Applied fix:** `days` is now built by cycling through `preferred_days` via
`[preferred_days[i % len(preferred_days)] for i in range(n_sessions)]` when
`preferred_days` is non-empty, falling back to `_DEFAULT_DAYS[:n_sessions]` only when
empty/None (matching the reviewer's suggested fix exactly). Added a regression test
asserting 2 preferred days with `n_sessions=4` produces 4 sessions (each day used
twice), not a silently-dropped 2-session week.

### WR-02: `plans.ftp_confidence` is permanently written as `NULL`

**Files modified:** `backend/agent/tools.py`, `tests/agent/test_tools_phase3.py`
**Commit:** b3568d7
**Applied fix:** `_persist_generated_plan` now accepts an explicit `ftp_confidence`
parameter and writes it directly to the `plans` insert payload, instead of reading
`plan_value.get("ftp_confidence")` (which never exists on `generate_plan`'s return
value). The `dispatch_tool` call site now passes `inputs.get("ftp_confidence")` --
the server-injected value already available in local scope. Added a regression test
with a same-turn `estimate_ftp_from_rides` entry (`confidence: "high"`) asserting the
actual Supabase insert payload's `ftp_confidence` field equals `"high"`, not `None`.

### WR-03: `write_audit_entry`'s docstring contradicts its actual (safe) usage

**Files modified:** `backend/agent/audit.py`
**Commit:** 11c4e83
**Applied fix:** Docstring rewritten to describe the actual contract: every call site
awaits `write_audit_entry` synchronously and this is correct/intended (keeps audit
writes ordered relative to the tool_result response and to each other across
concurrent dispatches), not a fire-and-forget pattern. Docstring-only change; no
behavior modified, no new test needed (existing `tests/agent/test_audit.py` suite
re-run and confirmed green).

### WR-04: Numeric-token tolerance attribution can be fooled by date/timestamp components

**Files modified:** `backend/agent/trust.py`, `tests/agent/test_trust.py`
**Commit:** fc30676
**Applied fix:** `_is_attributed` now tries `json.loads(val)` on each
`tool_result_values` entry first. When it parses, a new `_collect_numeric_leaves`
helper recursively walks the structure and compares the candidate only against
genuine JSON number leaves -- digits embedded inside a JSON *string* value (e.g. an
ISO date/timestamp) are structurally invisible to this comparison, since they live
inside a `str` leaf rather than a `number` leaf. This closes the general class of
collision (any short date/time component: day, month, hour, minute), not just the
one timestamp shape the pre-existing regression test happened to cover. When a
`tool_result_values` entry is not valid JSON (e.g. bare prose strings from simpler
call sites), attribution falls back unchanged to the pre-existing boundary-aware
regex token scan, preserving all prior behavior for non-JSON inputs. Added 3
regression tests: a short date component (day-of-month "4" in "2026-07-04") no
longer falsely attributes an unrelated hallucinated "4"; a real JSON number leaf
alongside a date string still attributes correctly; and the legacy non-JSON fallback
path still works. All 24 pre-existing tests in `test_trust.py`/`test_trust_corpus.py`
re-verified green against the rewritten implementation.

## Test Suite Verification

Ran `.venv/bin/pytest tests/ -q` after all 7 fixes were applied and committed:

```
8 failed, 302 passed, 2 warnings
FAILED tests/agent/test_sse.py::TestSSEEventSequence::test_sse_content_type
FAILED tests/agent/test_sse.py::TestSSEEventSequence::test_sse_frame_format
FAILED tests/agent/test_sse.py::TestSSEEventSequence::test_sse_event_ordering_text_only
FAILED tests/agent/test_sse.py::TestSSEEventSequence::test_sse_event_ordering_with_tools
FAILED tests/agent/test_sse.py::TestSSEEventSequence::test_sse_token_data_has_text_field
FAILED tests/agent/test_sse.py::TestSSEEventSequence::test_sse_done_data_is_empty_object
FAILED tests/agent/test_sse.py::TestSSEEventSequence::test_sse_no_live_anthropic_call
FAILED tests/agent/test_sse.py::TestSSEEventSequence::test_sse_requires_conversation_id
```

This is a subset of the documented pre-existing 9-failure baseline (8x `test_sse.py` +
1x `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields`).
All 8 `test_sse.py` failures are present and unchanged. The 9th baseline failure
(`test_capability_gap.py`) passes in this run instead of failing -- **investigated and
confirmed to be pre-existing test-order-dependent flakiness, not a side effect of any
fix in this pass**:

- Re-ran the identical command against unmodified `main` (before any Phase 8 fixes):
  reproduces exactly 9 failures, including `test_capability_gap.py`.
- Re-ran the fixed worktree with `--ignore=tests/api/test_chat.py` (the one new test
  file added by this pass): still 8 failures (test still passes), proving the flip is
  driven by collection-order changes from the added regression tests across the test
  suite, not by any change to `backend/sports_science/capability_gap.py` (a file none
  of these 7 fixes touch).
- Root cause: `test_supabase_insert_called_with_correct_fields` asserts
  `mock_client.table.assert_called_once_with(...)` against a per-test mock, but
  `backend/sports_science/capability_gap.py` caches a module-level `_supabase_client`
  singleton across tests with no reset fixture -- if an earlier test in the run already
  populated that singleton with a different mock, this test's own mock's `.table` is
  never called, and the assertion fails. This is a pre-existing cross-test-pollution
  bug in a module outside this phase's `files_reviewed_list`, orthogonal to trust-model
  integrity, and unaffected by all 7 applied fixes.

Net result: zero new failures introduced; one fewer failure observed, driven entirely
by pre-existing test-order sensitivity in an unrelated module.

---

_Fixed: 2026-07-04T21:45:00Z_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
