---
phase: 03-coaching-loop
plan: "01"
subsystem: database
tags: [migration, supabase, schema, rls, phase3]
dependency_graph:
  requires: []
  provides: [plans_table, adaptations_table, profiles_phase3_columns, sessions_phase3_columns, rides_phase3_columns, conversations_context_type]
  affects: [03-02, 03-03, 03-04, 03-05]
tech_stack:
  added: []
  patterns: [supabase-migration, rls-user-owns-row, fk-ordering]
key_files:
  created:
    - supabase/migrations/0002_phase3_schema.sql
  modified: []
decisions:
  - "Migration applied via supabase db push --linked (non-interactive with --yes flag)"
  - "Statement order: profiles ALTERs first, then CREATE plans, then ALTER sessions (FK dependency), then ALTER rides, then ALTER conversations, then CREATE adaptations"
  - "RLS SELECT-only policies on new tables; backend writes bypass via SERVICE_ROLE_KEY (same as capability_gaps pattern from 0001)"
metrics:
  duration: "5min"
  completed: "2026-06-20"
  tasks_completed: 2
  files_created: 1
status: complete
---

# Phase 03 Plan 01: Phase 3 Schema Migration Summary

**One-liner:** Phase 3 Postgres migration adding `plans` and `adaptations` tables with RLS, plus column additions to `profiles`, `sessions`, `rides`, and `conversations` — applied to remote Supabase.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Write 0002_phase3_schema migration file | ace332a | supabase/migrations/0002_phase3_schema.sql |
| 2 | Push migration to remote Supabase | (verified via migration list) | — |

## What Was Built

A single migration file (`supabase/migrations/0002_phase3_schema.sql`) covering all Phase 3 schema requirements, applied to the remote Supabase project (`pxdfmlvrqveofguyxxfo`):

**Column additions to existing tables:**

- `profiles`: `back_status` (text, NOT NULL, CHECK none/mild/moderate, DEFAULT none), `weekly_hours` (numeric), `preferred_days` (text[]), `rpe_baseline` (text), `lthr_estimate` (numeric), plus `UNIQUE (user_id)` constraint for upsert support
- `sessions`: `plan_id` (uuid FK -> plans ON DELETE CASCADE), `type` (text CHECK endurance/recovery/strength/interval), `zone_targets` (jsonb), `power_targets` (jsonb), `week_num` (int), `rpe_target` (int)
- `rides`: `session_id` (uuid FK -> sessions ON DELETE SET NULL), `ride_date` (date), `avg_power` (numeric), `avg_hr` (numeric), `avg_cadence` (numeric), `ftp_used` (numeric)
- `conversations`: `context_type` (text NOT NULL DEFAULT coaching, CHECK onboarding/coaching/ride_debrief)

**New tables:**

- `plans`: stores the 4-week plan JSON (id, user_id, sessions jsonb, mesocycle_weeks, ftp_confidence, status, created_at); RLS enabled; `plans: own row` policy
- `adaptations`: audit trail for every plan change (id, user_id, trigger, signal_count, scope, before_snapshot, after_snapshot, explanation_text, created_at); RLS enabled; `adaptations: own row` policy

## Deviations from Plan

None - plan executed exactly as written.

## Threat Coverage

T-03-01: Information Disclosure — RLS `USING (user_id = auth.uid())` on both `plans` and `adaptations`. Users cannot read another user's data.

T-03-02: Elevation of Privilege — No INSERT/UPDATE policies granted. Backend writes via SERVICE_ROLE_KEY only (consistent with `capability_gaps` pattern established in 0001).

T-03-03: Tampering — FK constraints with ON DELETE behavior prevent orphaned rows: `sessions.plan_id` CASCADE, `rides.session_id` SET NULL.

## Self-Check: PASSED

- [x] `supabase/migrations/0002_phase3_schema.sql` exists (1 file, 85 lines)
- [x] `CREATE TABLE public.plans` present
- [x] `CREATE TABLE public.adaptations` present
- [x] `profiles_user_id_unique` constraint present
- [x] `context_type` column present
- [x] 2x `ENABLE ROW LEVEL SECURITY` statements
- [x] `CREATE TABLE public.plans` appears before `ALTER TABLE public.sessions ADD COLUMN plan_id` (FK ordering correct)
- [x] `supabase migration list --linked` shows 0002 in both Local and Remote columns
- [x] Task 1 committed: ace332a
