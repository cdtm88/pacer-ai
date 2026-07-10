---
phase: 08-trust-model-integrity
plan: 06
subsystem: agent-runtime
tags: [python, trust-model, dispatch_tool, tool-schema, tdd-style-tests]

requires:
  - phase: 08-trust-model-integrity
    provides: "generate_plan's CTL-gap-aware progression + preferred_days consumption (Plan 04) and durable audit_log + conversation_id threading (Plan 05), both of which this plan's server-injection block builds on"
provides:
  - "dispatch_tool discards ANY LLM-supplied current_ctl/ftp_watts/ftp_confidence/load_targets/preferred_days for generate_plan and injects server-verified values instead (extends the 260702-wev user_id precedent to five more keys)"
  - "generate_plan's LLM-facing TOOL_SCHEMA no longer declares the five server-injected keys"
affects: []

tech-stack:
  added: []
  patterns:
    - "Server-side value injection for trust-sensitive tool inputs, run inside dispatch_tool's existing try/except so a DB failure surfaces as an is_error tool_result (D-14) instead of propagating unhandled"

key-files:
  created: []
  modified:
    - backend/agent/tools.py
    - tests/agent/test_tools_phase3.py

key-decisions:
  - "current_ctl is always queried directly from pmc_history (never the in-memory audit_log), since update_pmc is not guaranteed to run in the same turn as generate_plan -- Open Question 1 resolution from 08-RESEARCH.md"
  - "ftp_watts is sourced from estimate_ftp_from_rides's ToolResult.value['ftp'] key (not 'ftp_watts' as RESEARCH.md's Pattern 2 code example literally wrote) -- verified against the actual backend/sports_science/ftp.py return shape and corrected during implementation (Rule 1 fix)"
  - "The whole generate_plan injection block (DB queries + audit_log lookups) runs inside dispatch_tool's existing try/except wrapping the tool call itself, not before it, so a pmc_history/profiles query failure becomes an is_error tool_result (D-14) rather than an unhandled exception breaking the turn"
  - "ftp_confidence falls back through ftp_entry's value.confidence first, then its inputs.confidence (the insufficient_data/convergence-failed paths in ftp.py put confidence in inputs, not value, since value is None), then the 'insufficient_data' cold-start default"

patterns-established:
  - "Any future trust-sensitive tool input can reuse this same choke point: strip the key(s) unconditionally from inputs, then set them from a verified DB/same-turn-audit source before the fn(**inputs) call"

requirements-completed: [TRUST-07, PLAN-07, PLAN-06]

coverage:
  - id: D1
    description: "dispatch_tool discards bogus LLM-supplied current_ctl/ftp_watts/ftp_confidence/load_targets/preferred_days for generate_plan and replaces them with server-verified values (pmc_history CTL, profiles preferred_days), falling back to cold-start-safe defaults when no same-turn ftp/load audit entry exists"
    requirement: "TRUST-07"
    verification:
      - kind: unit
        ref: "tests/agent/test_tools_phase3.py::test_generate_plan_injection_discards_llm_values"
        status: pass
    human_judgment: false
  - id: D2
    description: "When THIS turn's audit_log already has estimate_ftp_from_rides/progress_load results, generate_plan's injected ftp_watts/ftp_confidence/load_targets come from those results, not the cold-start fallback"
    requirement: "TRUST-07"
    verification:
      - kind: unit
        ref: "tests/agent/test_tools_phase3.py::test_generate_plan_injection_uses_same_turn_ftp_and_load_entries"
        status: pass
    human_judgment: false
  - id: D3
    description: "generate_plan's input_schema.properties no longer contains current_ctl/load_targets/ftp_watts/ftp_confidence; required == [weekly_hours, back_status, hr_zones]; TRUST-02 invariant still holds"
    requirement: "PLAN-06"
    verification:
      - kind: unit
        ref: "inline python check: TOOL_SCHEMAS generate_plan properties assertion"
        status: pass
      - kind: unit
        ref: "tests/agent/test_tools_phase3.py::test_trust02_still_passes_after_new_tools"
        status: pass
    human_judgment: false
  - id: D4
    description: "Pre-existing generate_plan dispatch/persistence tests continue to pass after the injection block is added (mocked Supabase clients extended with a pmc_history/profiles select-chain stub)"
    requirement: "PLAN-06"
    verification:
      - kind: unit
        ref: "tests/agent/test_tools_phase3.py -x -q (18 passed)"
        status: pass
    human_judgment: false

duration: 14min
completed: 2026-07-04
status: complete
---

# Phase 08 Plan 06: Server-Side Injection of generate_plan's Trust-Sensitive Inputs Summary

**Extended the existing user_id server-injection choke point in `dispatch_tool` so `generate_plan`'s five trust-sensitive inputs (current_ctl, ftp_watts, ftp_confidence, load_targets, preferred_days) are always sourced from verified server state -- pmc_history, profiles, and this-turn's audit_log -- and never trusted from the LLM's tool-call arguments, closing the "invent a number, hand it to a tool, get it echoed back as attributed" laundering vector (D-02/D-07).**

## Performance

- **Duration:** ~14 min
- **Tasks:** 2 completed
- **Files modified:** 2

## Accomplishments

- New `_last_audit_result(audit_log, tool_name) -> dict | None` helper returns the most recent in-memory audit_log entry's `result` dict for a given tool name (skipping error-only entries), used to source ephemeral ftp/load values from THIS turn's tool calls.
- `dispatch_tool` gains a `generate_plan`-only injection block, placed inside the existing try/except (so a DB failure surfaces as an `is_error` tool_result per D-14, not an unhandled exception):
  - `current_ctl` is always queried directly from the latest `pmc_history` row (correct 0.0 for cold-start onboarding, since `update_pmc` is not guaranteed to run in the same turn as `generate_plan` -- Open Question 1 resolution).
  - `preferred_days` is queried from the `profiles` row.
  - `ftp_watts`/`ftp_confidence` come from THIS turn's `estimate_ftp_from_rides` audit_log entry (key `value['ftp']`, with confidence falling back to `inputs['confidence']` for the insufficient_data/convergence-failed paths where `value` is `None`); `load_targets` comes from THIS turn's `progress_load` audit_log entry.
  - When no same-turn ftp/load entry exists, the cold-start-safe fallback applies: `ftp_confidence='insufficient_data'`, `ftp_watts=None`, `load_targets={'recommended_ctl_target': current_ctl}` -- never the LLM's supplied values.
  - Any LLM-supplied values for these five keys are unconditionally discarded before the server-sourced values are set.
- `generate_plan`'s LLM-facing `TOOL_SCHEMA` no longer declares `current_ctl`, `load_targets`, `ftp_confidence`, or `ftp_watts` in `properties`/`required` (required shrinks to `[weekly_hours, back_status, hr_zones]`); the description now tells the model these values are server-supplied and any value it provides is discarded. `TOOL_REGISTRY`/`TOOL_SCHEMAS` name sets are unchanged (TRUST-02 invariant intact, still 11 tools).
- Two new dispatch_tool-level tests in `tests/agent/test_tools_phase3.py`: one proving bogus LLM-supplied values for all five keys are discarded and replaced with server-sourced values (with the cold-start fallback), one proving same-turn `estimate_ftp_from_rides`/`progress_load` audit_log entries flow through correctly when present.

## Task Commits

Each task was committed atomically:

1. **Task 1: Inject server-verified generate_plan inputs in dispatch_tool** - `85c9cff` (feat)
2. **Task 2: Tighten the generate_plan schema and add injection tests** - `4a032db` (feat)

**Plan metadata:** SUMMARY.md and REQUIREMENTS.md committed by this worktree agent per parallel-execution convention; STATE.md/ROADMAP.md excluded (orchestrator owns those writes after the wave completes).

## Files Created/Modified

- `backend/agent/tools.py` - `_last_audit_result` helper; `generate_plan`-only server-injection block in `dispatch_tool` (inside the existing try/except); tightened `generate_plan` `TOOL_SCHEMA` (properties/required shrunk, description updated)
- `tests/agent/test_tools_phase3.py` - `_MockSelectChain` chainable select() stub added to the pre-existing generate_plan mock Supabase clients (required for them to keep passing now that dispatch_tool queries pmc_history/profiles on every generate_plan dispatch); two new `generate_plan_injection` tests

## Decisions Made

- **current_ctl always from pmc_history, never the in-memory audit_log** -- confirmed as the correct choice per 08-RESEARCH.md's Open Question 1 resolution: `update_pmc` is not guaranteed to run in the same turn as `generate_plan` (onboarding's D-08 order is `save_profile -> progress_load -> calculate_hr_zones -> generate_plan`, no `update_pmc`), so a durable DB query is the only source that is correct for both first-time cold-start onboarding (returns 0.0) and later coaching-chat re-plans.
- **ftp_watts sourced from `value['ftp']`, not `value['ftp_watts']`** -- 08-RESEARCH.md's Pattern 2 code example and this plan's `<action>` prose both used the key name `ftp_watts`, but `backend/sports_science/ftp.py::estimate_ftp_from_rides`'s actual `ToolResult.value` dict uses the key `ftp` (confirmed by direct source read during implementation). Following the RESEARCH.md example literally would have made `ftp_watts` always `None` even when a valid same-turn FTP estimate existed. Corrected to the real key (Rule 1 -- bug fix within task scope).
- **ftp_confidence fallback checks both `value.confidence` and `inputs.confidence`** -- `estimate_ftp_from_rides`'s insufficient-data and convergence-failed paths return `value=None` with `confidence` living in `inputs`, not `value`. The injection block checks `value.confidence` first (success path), then `inputs.confidence` (failure paths), then the `'insufficient_data'` default (no same-turn entry at all) -- this correctly produces `insufficient_data` in all three of those cases, not just the "no entry" case.
- **Injection block placed inside dispatch_tool's existing try/except**, not before it -- the block performs two Supabase queries (I/O that can fail); placing it inside the existing try/except (which already gives D-14 "never silently swallowed" semantics for the tool call itself) means a DB failure here becomes a proper `is_error` tool_result with an audit entry, consistent with the rest of the module's error-handling architecture, rather than propagating an unhandled exception out of `dispatch_tool` (which is invoked via `asyncio.gather` for potentially multiple concurrent tool calls in `loop.py`).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Pre-existing generate_plan dispatch/persistence tests broke because their mock Supabase clients did not support `select()` chaining**
- **Found during:** Task 1, first verification run of the full `test_tools_phase3.py` file
- **Issue:** `test_dispatch_tool_persists_generate_plan`, `test_persist_generated_plan_writes_tss_target`, and `test_dispatch_tool_generate_plan_uses_injected_user_id` each construct a minimal mock Supabase client supporting only `.table(name).insert(...).execute()` (for the `plans`/`sessions` persistence writes). The new injection block calls `.table("pmc_history").select(...).eq(...).order(...).limit(...).execute()` and `.table("profiles").select(...).eq(...).execute()` on every `generate_plan` dispatch, which these mocks did not support, causing `AttributeError`/assertion failures.
- **Fix:** Added a shared `_MockSelectChain` stub class (`select`/`eq`/`order`/`limit` all return `self`, `execute()` returns `MagicMock(data=...)`) and routed each mock client's `.table("pmc_history"/"profiles")` calls to it (empty data by default, so `current_ctl`/`preferred_days` fall back to their cold-start-safe defaults `0.0`/`[]` in these tests, which don't assert on the injected values themselves).
- **Files modified:** `tests/agent/test_tools_phase3.py`
- **Commit:** `85c9cff`

**2. [Rule 1 - Bug] ftp_watts key mismatch between RESEARCH.md's example and the actual ftp.py return shape**
- **Found during:** Task 1, while writing the injection block against the real `estimate_ftp_from_rides` source
- **Issue:** 08-RESEARCH.md's Pattern 2 code example (and this plan's `<action>` text) used `ftp_entry.get("value", {}).get("ftp_watts")`, but `backend/sports_science/ftp.py`'s actual `ToolResult.value` dict on a successful estimate uses the key `"ftp"`, not `"ftp_watts"`. Following the documented example literally would have silently made the injected `ftp_watts` always `None`, even with a valid same-turn FTP estimate.
- **Fix:** Read `backend/sports_science/ftp.py` directly and used the correct key (`value.get("ftp")`), with a fallback to `inputs.get("confidence")` for the insufficient-data/convergence-failed paths where `value` is `None`.
- **Files modified:** `backend/agent/tools.py`
- **Commit:** `85c9cff`

## Issues Encountered

None beyond the auto-fixed items above. This worktree has no `.venv` checked out per-worktree (consistent with prior Phase 8 plans' documented finding); all test runs used the main repo's `.venv/bin/python` by absolute path.

## User Setup Required

None -- no external service configuration required. Reuses the already-live `pmc_history`/`profiles` tables and the existing `_get_async_supabase()` singleton; no new packages, no migration.

## Next Phase Readiness

- `generate_plan`'s full D-02/D-07 injection story is now closed end-to-end: Plan 04 wired the pure-computation consumption of `current_ctl`/`load_targets`/`preferred_days` into real progression logic, and this plan wires the server-side sourcing of all five trust-sensitive inputs into `dispatch_tool`.
- Full test suite: `9 failed, 285 passed` -- the exact documented pre-existing baseline (`tests/agent/test_sse.py` x8, `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields` x1). Zero new regressions from this plan's changes.
- No blockers for subsequent Phase 8 plans or the milestone completion step.

## Self-Check: PASSED

- FOUND: backend/agent/tools.py
- FOUND: tests/agent/test_tools_phase3.py
- FOUND commit 85c9cff in git log
- FOUND commit 4a032db in git log

---
*Phase: 08-trust-model-integrity*
*Completed: 2026-07-04*
