---
phase: 03-coaching-loop
plan: "02"
subsystem: sports-science-tools, test-infrastructure
tags: [fitdecode, generate_plan, save_profile, tool-registry, TRUST-02, test-stubs, FIT-fixture]
dependency_graph:
  requires: [03-01]
  provides: [sports_science/plan.py, sports_science/profile.py, agent/tools.py@10-tools, tests/api/, tests/fixtures/sample_zwift.fit]
  affects: [03-03, 03-04, 03-05]
tech_stack:
  added: [fitdecode==0.11.0]
  patterns: [async-supabase-singleton, sync-ToolResult-compute, TRUST-02-import-time-assertion, TDD-stub-scaffold]
key_files:
  created:
    - sports_science/plan.py
    - sports_science/profile.py
    - tests/api/__init__.py
    - tests/api/conftest.py
    - tests/api/test_onboarding.py
    - tests/api/test_rides.py
    - tests/api/test_adaptations.py
    - tests/agent/test_tools_phase3.py
    - tests/fixtures/sample_zwift.fit
  modified:
    - requirements.txt
    - agent/tools.py
decisions:
  - "generate_plan is sync (no async def) so dispatch_tool routes via asyncio.to_thread; no changes needed to dispatcher"
  - "save_profile is async and uses existing iscoroutinefunction branch in dispatch_tool"
  - "Zwift .FIT fixture generated synthetically using raw FIT binary protocol (fitdecode is read-only); 900s, avg ~154W, verified parseable"
  - "back_status=moderate constrains both duration (cap 30min weeks 1-2) and session type (no strength in week 1)"
  - "TRUST-02 atomic edit: imports, TOOL_REGISTRY, and TOOL_SCHEMAS all updated in one operation to prevent import-time RuntimeError"
metrics:
  duration: "7 minutes"
  completed: "2026-06-20"
  tasks_completed: 3
  files_created: 9
  files_modified: 2
status: complete
---

# Phase 03 Plan 02: Wave 1 Foundation (fitdecode, Tools, Test Stubs) Summary

**One-liner:** fitdecode dependency added; `generate_plan` (sync, pure compute) and `save_profile` (async Supabase upsert) created and atomically registered to extend TOOL_REGISTRY and TOOL_SCHEMAS to 10 entries each; Wave 0 test stubs scaffolded with real Zwift .FIT fixture.

## What Was Built

### Task 1: fitdecode dependency + generate_plan + save_profile modules

Added `fitdecode==0.11.0` to `requirements.txt` per CLAUDE.md mandate (over abandoned fitparse).

**`sports_science/plan.py`** -- sync `generate_plan()` function:
- 4-week base mesocycle; pure computation with no DB calls and no imports of other sports_science tools (trust model)
- Session count from `weekly_hours`: <=1h -> 2/week, 2-3h -> 3/week, 4h+ -> 4/week
- Week 1 policy: endurance only, zone 2, capped at 45 min, rpe_target <= 3, power_targets always None
- Week 4 policy: 40% volume reduction (duration * 0.6)
- back_status=moderate: caps weeks 1-2 at 30 min, no strength type in week 1
- Cold-start (ftp_confidence=insufficient_data or low): all power_targets=None; HR/RPE only

**`sports_science/profile.py`** -- async `save_profile()` function:
- Async Supabase singleton pattern from capability_gap.py (WR-04: no connection pool leak)
- Maps back_status to constraints JSONB: moderate -> {back_issues: True, load_ramp_flag_threshold_pct: 10}; mild -> {back_issues: True}; none -> {back_issues: False}
- Upserts on conflict with user_id; returns ToolResult with profile_id and saved=True

### Task 2: Atomic tool registry extension (TRUST-02)

Single atomic edit to `agent/tools.py`:
- Added imports for `save_profile` and `generate_plan` after existing sports_science block
- Added both to `TOOL_REGISTRY` (now 10 entries)
- Appended both schema dicts to `TOOL_SCHEMAS` (now 10 entries)
- TRUST-02 import-time assertion verified: `_schema_names == _registry_names`, `len == 10`

### Task 3: Wave 0 test stubs and Zwift .FIT fixture

**`tests/api/`** package created:
- `__init__.py`: empty package marker
- `conftest.py`: TEST_USER_ID constant, `mock_supabase_factory()` helper, `parse_sse_frames` re-export
- `test_onboarding.py`: 1 non-skipped helper stub + 4 Wave 2 skips (with `_mock_interview_run_turn` generator)
- `test_rides.py`: `test_fixture_exists` (not skipped, asserts .FIT present) + 6 Wave 3 skips
- `test_adaptations.py`: 7 Wave 4 skips

**`tests/agent/test_tools_phase3.py`** (fully implemented, 8 tests passing):
- `test_trust02_still_passes_after_new_tools`: asserts schema_names == registry_names and len == 10
- `test_generate_plan`: basic shape and mesocycle_weeks == 4
- `test_cold_start_hr_only`: verifies zone_targets present in cold-start sessions
- `test_power_targets_cold_start`: asserts all power_targets == None for insufficient_data
- `test_session_schema`: all required keys present on every session
- `test_back_constraints`: moderate back caps weeks 1-2 at 30 min and excludes strength in week 1
- `test_save_profile_upserts`: async mock verifies saved=True and profile_id
- `test_save_profile_moderate_back_constraints`: verifies constraints JSONB for moderate back_status

**`tests/fixtures/sample_zwift.fit`** (8228 bytes):
- Generated using raw FIT binary protocol (fitdecode is read-only; no write API)
- 900 seconds of 1 Hz record messages with power, heart_rate, cadence, timestamp fields
- Average power ~154W; verified parseable with fitdecode (900 power records confirmed)
- Satisfies FIT-06 acceptance test prerequisite (TSS > 0 will be computable via compute_tss)

## Test Results

```
168 passed, 17 skipped, 2 warnings in 0.67s
```

All 168 tests pass; 17 Wave 2-4 stubs skip cleanly; no regressions.

## Deviations from Plan

None -- plan executed exactly as written.

The Zwift .FIT fixture was generated synthetically using the FIT binary protocol. The plan permitted this as option (3): "generate a synthetic but spec-valid .FIT with record messages containing power, heart_rate, cadence, and timestamp fields at 1 Hz for >= 600 seconds". The file is verified parseable by fitdecode with 900 power records.

## Threat Surface Scan

No new threat surface beyond what the plan's threat model already covers:
- `save_profile` is now callable by the LLM but only via TOOL_REGISTRY (T-03-04 mitigated by TRUST-02)
- `generate_plan` performs pure computation with no network calls (T-03-05 confirmed)
- SERVICE_ROLE_KEY read from env, not logged; ToolResult.inputs records user_id/back_status/weekly_hours only (T-03-06 mitigated)

## Self-Check

### Files created/modified:
- /Users/christianmoore/ai/pacer-ai/requirements.txt: FOUND
- /Users/christianmoore/ai/pacer-ai/sports_science/plan.py: FOUND
- /Users/christianmoore/ai/pacer-ai/sports_science/profile.py: FOUND
- /Users/christianmoore/ai/pacer-ai/agent/tools.py: FOUND
- /Users/christianmoore/ai/pacer-ai/tests/api/__init__.py: FOUND
- /Users/christianmoore/ai/pacer-ai/tests/api/conftest.py: FOUND
- /Users/christianmoore/ai/pacer-ai/tests/api/test_onboarding.py: FOUND
- /Users/christianmoore/ai/pacer-ai/tests/api/test_rides.py: FOUND
- /Users/christianmoore/ai/pacer-ai/tests/api/test_adaptations.py: FOUND
- /Users/christianmoore/ai/pacer-ai/tests/agent/test_tools_phase3.py: FOUND
- /Users/christianmoore/ai/pacer-ai/tests/fixtures/sample_zwift.fit: FOUND

### Commits:
- b1b21d9: feat(03-02): add fitdecode dep and create generate_plan + save_profile modules
- f0a72ad: feat(03-02): atomically register save_profile and generate_plan in tool registry (TRUST-02)
- f853e5a: feat(03-02): scaffold Wave 0 test stubs and create real Zwift .FIT fixture

## Self-Check: PASSED
