-- PacerAI: Phase 6 core loop persistence fixes
-- Migration: 0005_phase6_persistence
-- Applied via: supabase db push --linked --yes
-- Purpose: Removes schema drift that makes the core loop silently fail against a real
--          database. pmc_history is missing tss/days_of_data columns the code already
--          writes, sessions.status rejects 'missed', profiles.ftp does not exist while
--          sessions.py selects it, rides has no server-side dedup guard, and adaptations
--          is missing trigger/status columns used by the adaptation audit trail.
--          All changes are idempotent (ADD COLUMN IF NOT EXISTS / DROP+ADD CONSTRAINT
--          IF EXISTS) so a repeated `supabase db push --linked --yes` is a safe no-op.

-- ============================================================
-- 1. pmc_history: add tss and days_of_data columns (Pitfall 1)
-- ============================================================
-- tss: written by rides.py PMC upsert; column did not exist so upserts silently no-op
ALTER TABLE public.pmc_history
  ADD COLUMN IF NOT EXISTS tss numeric;

-- days_of_data: written by rides.py PMC upsert alongside tss
ALTER TABLE public.pmc_history
  ADD COLUMN IF NOT EXISTS days_of_data int NOT NULL DEFAULT 0;

-- ============================================================
-- 2. sessions: allow 'missed' status (Pitfall 2)
-- ============================================================
-- Drop-then-add is the idempotent form for a CHECK constraint; existing values
-- ('planned','completed','skipped','partial') are preserved, 'missed' is added.
ALTER TABLE public.sessions
  DROP CONSTRAINT IF EXISTS sessions_status_check;

ALTER TABLE public.sessions
  ADD CONSTRAINT sessions_status_check
  CHECK (status IN ('planned','completed','skipped','partial','missed'));

-- ============================================================
-- 3. profiles: add ftp and lthr columns
-- ============================================================
-- ftp: write-back-populated by 06-05; sessions.py already selects this column
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS ftp numeric;

-- lthr: written by save_profile in 06-02; existing lthr_estimate column untouched
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS lthr numeric;

-- ============================================================
-- 4. rides: add content_hash with a user-scoped UNIQUE dedup guard (T-06-01)
-- ============================================================
ALTER TABLE public.rides
  ADD COLUMN IF NOT EXISTS content_hash text;

-- Composite key is user-scoped so one user's hash can never block or collide with
-- another user's upload. Existing rows have content_hash NULL and multiple NULLs
-- remain distinct under a UNIQUE constraint, so no violation occurs on existing data.
ALTER TABLE public.rides
  DROP CONSTRAINT IF EXISTS rides_user_content_hash_unique;

ALTER TABLE public.rides
  ADD CONSTRAINT rides_user_content_hash_unique UNIQUE (user_id, content_hash);

-- ============================================================
-- 5. adaptations: add trigger_session_ids and status columns
-- ============================================================
-- trigger_session_ids: the specific sessions that caused this adaptation to fire
ALTER TABLE public.adaptations
  ADD COLUMN IF NOT EXISTS trigger_session_ids uuid[];

-- status: lifecycle values are 'applied' | 'proposed' | 'superseded', enforced at the
-- application layer (no CHECK constraint here) so this migration stays idempotent.
-- Existing rows backfill to 'applied'.
ALTER TABLE public.adaptations
  ADD COLUMN IF NOT EXISTS status text NOT NULL DEFAULT 'applied';
