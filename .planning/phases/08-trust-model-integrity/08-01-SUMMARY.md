---
phase: 08-trust-model-integrity
plan: 01
subsystem: database
tags: [supabase, postgres, audit-log, migrations, trust-model, tdd]

requires: []
provides:
  - "public.audit_log table (id, user_id, conversation_id, tool_use_id, tool_name, inputs, result, is_error, created_at) with RLS policy and composite index"
  - "public.profiles.hr_zones_available nullable boolean column"
  - "backend/agent/audit.py: write_audit_entry (best-effort per-dispatch write) and load_prior_audit_values (conversation-scoped reload)"
affects: [08-02, 08-05, 08-07]

tech-stack:
  added: []
  patterns:
    - "Best-effort DB write (try/except: pass) mirrored from capability_gap.py, but client acquired via centralized backend.db.get_async_supabase() instead of a new duplicated module-level singleton"
    - "Defence-in-depth app-layer .eq('user_id', user_id) re-enforcement on top of RLS for a conversation-scoped read, matching onboarding.load_conversation"

key-files:
  created:
    - supabase/migrations/0009_audit_log_and_hr_zones_flag.sql
    - backend/agent/audit.py
    - tests/agent/test_audit.py
  modified: []

key-decisions:
  - "audit_log RLS policy wrapped in a DO $$ ... IF NOT EXISTS $$ guard (CREATE POLICY has no native IF NOT EXISTS) to keep the migration idempotent/re-runnable, matching the idempotent style of every other migration in this repo"
  - "Test mocking patches backend.agent.audit.get_async_supabase directly (the name imported into this module) rather than backend.db._supabase_client, following the same convention already used in tests/agent/test_tools_phase3.py for tools_module._get_async_supabase"

patterns-established:
  - "write_audit_entry / load_prior_audit_values pair as the single persistence mechanism serving both the audit trail (TRUST-04/06) and cross-turn trust-scanner seeding (D-04) -- one table, two read/write access patterns, no duplicate singleton"

requirements-completed: [TRUST-06, TRUST-04]

coverage:
  - id: D1
    description: "audit_log table + RLS policy + composite index + profiles.hr_zones_available column exist in the live linked Supabase project"
    requirement: "TRUST-06"
    verification:
      - kind: other
        ref: "supabase migration list --linked (0009 local == remote)"
        status: pass
    human_judgment: false
  - id: D2
    description: "write_audit_entry inserts one audit_log row per call and never raises, even when the DB write fails"
    requirement: "TRUST-04"
    verification:
      - kind: unit
        ref: "tests/agent/test_audit.py#test_write_audit_entry_inserts_one_row"
        status: pass
      - kind: unit
        ref: "tests/agent/test_audit.py#test_write_audit_entry_swallows_insert_exception"
        status: pass
    human_judgment: false
  - id: D3
    description: "load_prior_audit_values returns prior tool-result JSON strings scoped by conversation_id + user_id, ordered by created_at, [] on empty/failure, skips null results"
    requirement: "TRUST-04"
    verification:
      - kind: unit
        ref: "tests/agent/test_audit.py#test_load_prior_audit_values_empty_conversation"
        status: pass
      - kind: unit
        ref: "tests/agent/test_audit.py#test_load_prior_audit_values_returns_result_json_strings"
        status: pass
      - kind: unit
        ref: "tests/agent/test_audit.py#test_load_prior_audit_values_enforces_user_id_filter"
        status: pass
      - kind: unit
        ref: "tests/agent/test_audit.py#test_load_prior_audit_values_never_raises"
        status: pass
      - kind: unit
        ref: "tests/agent/test_audit.py#test_load_prior_audit_values_skips_null_results"
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-07-04
status: complete
---

# Phase 08 Plan 01: Audit Log Persistence Layer Summary

**New `audit_log` Postgres table (RLS + composite index) plus `backend/agent/audit.py`'s `write_audit_entry`/`load_prior_audit_values`, live-migrated to the linked Supabase project and fully unit-tested (TDD RED/GREEN).**

## Performance

- **Duration:** ~8 min
- **Tasks:** 2 (Task 1: migration + live push; Task 2: TDD module + tests)
- **Files modified:** 3 (all new)

## Accomplishments
- `supabase/migrations/0009_audit_log_and_hr_zones_flag.sql` created and pushed to the live linked project (`supabase db push --linked --yes`; confirmed via `supabase migration list --linked` showing local `0009` == remote `0009`)
- `public.audit_log` table live: `id`, `user_id`, `conversation_id`, `tool_use_id`, `tool_name`, `inputs`, `result`, `is_error`, `created_at`, with RLS policy `"audit_log: own row"` (`user_id = auth.uid()`) and composite index `audit_log_conversation_created_idx (conversation_id, created_at)`
- `public.profiles.hr_zones_available` (nullable boolean) column live, ready for a later plan in this phase to write
- `backend/agent/audit.py` implements `write_audit_entry` (best-effort insert, never raises) and `load_prior_audit_values` (conversation-scoped reload, app-layer `user_id` re-enforcement, never raises, skips null-result rows)
- Both functions acquire their client via the already-centralized `backend.db.get_async_supabase()` — no new duplicated module-level singleton was added (WR-003 preserved)
- `tests/agent/test_audit.py`: 7 tests, all green, following full RED (failing on missing module) → GREEN (implementation) TDD gates
- Full suite (`pytest tests/ -q`): 257 passed, 9 failed — the exact pre-existing baseline from 08-RESEARCH.md, zero new regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Create the audit_log migration and push it to the linked project** - `2211477` (feat)
2. **Task 2 (RED): add failing test for backend/agent/audit.py** - `c98dd61` (test)
3. **Task 2 (GREEN): implement write_audit_entry and load_prior_audit_values** - `5e5751d` (feat)

## Files Created/Modified
- `supabase/migrations/0009_audit_log_and_hr_zones_flag.sql` - audit_log table, RLS policy, composite index, profiles.hr_zones_available column
- `backend/agent/audit.py` - write_audit_entry + load_prior_audit_values
- `tests/agent/test_audit.py` - 7 unit tests covering both functions' behaviors

## Decisions Made
- Wrapped `CREATE POLICY` in a `DO $$ ... IF NOT EXISTS (SELECT ... pg_policies ...) $$` guard since `CREATE POLICY` has no native `IF NOT EXISTS` clause — keeps the migration safely re-runnable, matching the idempotent style every other migration in this repo already follows (Rule 2: missing idempotency safeguard, consistent with the plan's own "idempotent" requirement).
- This worktree had no linked Supabase project state (`supabase/.temp/`, gitignored, not checked out into git worktrees). Copied the main repo's `supabase/.temp/` link-state directory into this worktree so `supabase db push --linked --yes` could resolve the project ref; the CLI's own auth session (already logged in outside this worktree) supplied push credentials. No secrets were created or persisted in git — `.temp/` stays gitignored.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Idempotent RLS policy creation**
- **Found during:** Task 1 (migration authoring)
- **Issue:** `CREATE POLICY "audit_log: own row" ...` as written in RESEARCH.md/PATTERNS.md has no `IF NOT EXISTS` guard; re-running the migration (e.g. accidental double-push) would fail with "policy already exists", breaking the file's stated idempotent design intent.
- **Fix:** Wrapped the `CREATE POLICY` statement in a `DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE ...) THEN CREATE POLICY ... END IF; END $$;` block.
- **Files modified:** `supabase/migrations/0009_audit_log_and_hr_zones_flag.sql`
- **Verification:** `supabase db push --linked --yes` applied cleanly on first run and reported "Remote database is up to date" on a second run with no error.
- **Committed in:** `2211477` (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical/idempotency safeguard)
**Impact on plan:** Necessary for migration correctness on re-run; no scope creep — column names/types/RLS semantics match RESEARCH.md exactly.

## Issues Encountered
- This worktree lacked `.venv` (not checked out per-worktree) and `supabase/.temp/` link state (gitignored, not shared across worktrees). Resolved by invoking the main repo's `.venv/bin/python` by absolute path for tests, and copying the main repo's `supabase/.temp/` directory into this worktree to resolve `supabase db push --linked`'s project ref. Neither workaround touches git-tracked state.

## User Setup Required
None - `SUPABASE_ACCESS_TOKEN`/CLI auth was already available via the machine's existing `supabase` CLI login session; no new credential was requested or created.

## Next Phase Readiness
- `audit_log` table and `backend/agent/audit.py`'s read/write functions are ready for Plan 05 (this phase) to wire into `dispatch_tool`/`run_turn` for the actual per-dispatch writes and cross-turn `tool_result_values` seeding.
- `profiles.hr_zones_available` column is ready for Plan 07 (this phase) to write during onboarding's LTHR/HR-zone-availability question.
- No blockers.

---
*Phase: 08-trust-model-integrity*
*Completed: 2026-07-04*

## Self-Check: PASSED

All created files and commit hashes verified present on disk / in git log.
