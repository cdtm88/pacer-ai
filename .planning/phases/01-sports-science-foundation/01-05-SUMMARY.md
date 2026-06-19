---
phase: 01-sports-science-foundation
plan: 05
subsystem: database-schema
tags: [supabase, sql, rls, python, capability-gap, trust-model]
status: complete

requires:
  - 01-01: Python venv, ToolResult, constants, test infrastructure
  - 01-02: calculate_power_zones, calculate_hr_zones (zones.py)
  - 01-03: compute_tss, update_pmc (metrics.py, pmc.py)
  - 01-04: estimate_ftp_from_rides, progress_load, validate_session_vs_actual

provides:
  - 8-table Supabase schema migration (supabase/migrations/0001_initial_schema.sql)
  - supabase/config.toml (supabase init output, cloud-first D-07)
  - log_capability_gap (TOOL-08, GAP-01/02/03) in sports_science/capability_gap.py
  - Finalized sports_science/__init__.py with __all__ = 8 public functions + ToolResult (TRUST-02)

affects:
  - Phase 2 tool registry: __all__ is the authoritative registry-eligible surface
  - Phase 3 adaptation transparency: capability_gaps table read by adaptation log
  - All phases: 8-table schema is the persistence backbone

tech-stack:
  added:
    - supabase CLI 2.107.0 (already installed; supabase init run)
    - supabase Python SDK 2.31.0 (already in requirements.txt)
  patterns:
    - Service-role key for backend DB writes that bypass RLS (Pitfall 6, D-07)
    - __all__ as TRUST-02 contract: Phase 2 tool registry wraps only this set
    - GAP-03 user-message sanitization: method_name goes to DB only, never user chat
    - TDD: RED commit (test_capability_gap.py) then GREEN commit (capability_gap.py)

key-files:
  created:
    - supabase/config.toml
    - supabase/migrations/0001_initial_schema.sql
    - sports_science/capability_gap.py
  modified:
    - sports_science/__init__.py (added log_capability_gap import + __all__ entry)
    - tests/sports_science/test_capability_gap.py (replaced stubs with 5 real tests)

decisions:
  - "D-07: supabase init creates config.toml; migrations applied via supabase db push, not dashboard paste (Pitfall 5)"
  - "D-09: profiles.constraints JSONB defaults to {\"back_issues\": false}; full back-issues schema documented in SQL comment"
  - "GAP-03: user_message is a hardcoded generic string; method_name stored in DB only"
  - "TRUST-02: __all__ in __init__.py is the sole surface the Phase 2 tool registry may wrap; no ad-hoc exports"
  - "Pitfall 6: _get_supabase() uses SUPABASE_SERVICE_ROLE_KEY; anon key never used for backend writes"

metrics:
  duration: "2 minutes"
  completed: "2026-06-19T13:44:20Z"
  tasks_total: 4
  tasks_completed: 3
  tasks_pending: 1
  files_created: 4
  files_modified: 2
---

# Phase 01 Plan 05: Supabase Schema + Capability Gap Summary

**One-liner:** 8-table Supabase schema with RLS applied via migration file; log_capability_gap logs structured gap rows and returns a user-safe message that hides the internal method name; package __all__ finalized as the Phase 2 tool-registry contract.

## Tasks Completed

| # | Task | Commit | Status |
|---|------|--------|--------|
| 1 | Author 8-table schema migration with RLS | a09b4ff | DONE |
| 2 (RED) | Add failing tests for log_capability_gap | e700643 | DONE |
| 2 (GREEN) | Implement log_capability_gap + finalize __init__.py | 12fc1c6 | DONE |
| 3 | Apply schema via supabase db push | - | PENDING (manual step required) |
| 4 | Human verify: cloud schema + RLS + live capability-gap insert | - | AWAITING HUMAN |

## Task Details

### Task 1: 8-table Supabase schema migration

`supabase/migrations/0001_initial_schema.sql` creates all 8 tables:
- `users`: references auth.users (cascade delete), email, google_tokens (JSONB)
- `profiles`: user_id FK, constraints JSONB (default `{"back_issues": false}` per D-09), fitness/equipment/goals
- `sessions`: planned session detail, status, scheduled_date
- `rides`: tss, np_watts, intensity_factor, duration_secs, raw_fit_path
- `pmc_history`: date, ctl, atl, tsb, tss_display_ready
- `conversations`: user_id FK
- `messages`: conversation_id FK + user_id FK, role, content
- `capability_gaps`: nullable user_id + conversation_id, method_name NOT NULL, description, context JSONB

RLS enabled on all 8 tables. User-owns-row policy on each. `capability_gaps` read policy plus service-role bypass comment for backend writes (Pitfall 6).

`supabase/config.toml` created by `supabase init` (no local Docker stack started, D-07 cloud-first).

### Task 2: log_capability_gap + __init__.py (TDD)

**RED:** 5 tests written covering: GAP-03 message sanitization, TOOL-09 ToolResult contract, security (no secrets in inputs), GAP-01 structured insert, GAP-02 no physiological number computed.

**GREEN:** `sports_science/capability_gap.py` implemented:
- `_get_supabase()`: reads SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY from env, returns sync client (Phase 2 migrates to async)
- `log_capability_gap(method_name, context, user_id=None)`: inserts structured row, returns generic user-safe ToolResult
- User message is hardcoded generic text; method_name only in DB (GAP-03)
- `inputs={"context_keys": list(context.keys())}`: key names only, no values or secrets

`sports_science/__init__.py` finalized with full `__all__` (9 entries: 8 public functions + ToolResult). No private names exported. Zero LLM SDK imports in package (TRUST-01 verified by test_import_boundary.py).

### Task 3: supabase db push (PENDING)

`supabase db push` could not run automatically: `SUPABASE_ACCESS_TOKEN` is not set in the environment and `.env` does not exist. The supabase CLI requires authentication to link to a cloud project.

**To apply the migration manually:**
```bash
# 1. Authenticate
supabase login

# 2. Link to your cloud project (get ref from Supabase Dashboard -> Project Settings -> General)
supabase link --project-ref <your-project-ref>

# 3. Apply the migration
supabase db push
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] "anthropic" string in __init__.py comment broke import boundary test**
- **Found during:** Task 2 GREEN verification
- **Issue:** The `__init__.py` docstring contained the word "anthropic" (as a comment explaining TRUST-01). The import boundary test `grep -r "anthropic" sports_science/` matched the comment text, causing the test to fail.
- **Fix:** Replaced "anthropic SDK" with "LLM SDK" in the comment to avoid triggering the grep-based boundary test. The __pycache__ was also cleared to remove stale .pyc bytes.
- **Files modified:** `sports_science/__init__.py`
- **Commit:** Included in 12fc1c6

## Threat Flags

None detected beyond those already in the plan's threat model.

## Known Stubs

None. All capability_gap.py functionality is fully implemented. The __all__ list is complete and matches the plan specification exactly.

## Self-Check

Files created/exist:
- [x] supabase/config.toml (from supabase init)
- [x] supabase/migrations/0001_initial_schema.sql (8 tables + RLS)
- [x] sports_science/capability_gap.py (log_capability_gap + _get_supabase)
- [x] tests/sports_science/test_capability_gap.py (5 tests, all passing)
- [x] sports_science/__init__.py (updated with log_capability_gap + __all__)

Commits verified:
- [x] a09b4ff: feat(01-05): schema migration
- [x] e700643: test(01-05): RED tests
- [x] 12fc1c6: feat(01-05): GREEN implementation

Tests passing:
- [x] pytest tests/sports_science/test_capability_gap.py: 5 passed
- [x] pytest tests/sports_science/test_import_boundary.py: 1 passed
- [x] python -c "import sports_science": clean import, __all__ verified

## Pending: Human Checkpoint (Task 4)

Task 4 requires human verification of the cloud schema after `supabase db push`:
1. All 8 tables visible in Supabase Dashboard -> Table Editor
2. RLS enabled on each table (shield icon)
3. RLS smoke test: anon select returns 0 rows
4. Live capability-gap insert: `.venv/bin/python -c "from sports_science import log_capability_gap; print(log_capability_gap('test_method', {'k':'v'}).value)"`
5. No service-role key committed: `git grep -n SUPABASE_SERVICE_ROLE_KEY -- ':!*.example'` returns nothing
