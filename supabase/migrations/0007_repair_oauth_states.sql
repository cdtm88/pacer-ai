-- 0007: Repair schema drift -- oauth_states table missing on linked project (2026-07-03).
--
-- Discovered while applying 0008_fk_indexes.sql: `supabase db push --linked` failed
-- with "relation \"public.oauth_states\" does not exist" (SQLSTATE 42P01) even though
-- `supabase migration list --linked` reports 0003 (which defines this table) as
-- already applied. Confirmed via a direct PostgREST query against the live project
-- that the table is genuinely absent from the public schema -- other 0003 changes
-- (e.g. sessions.calendar_event_id) are present, so this is a partial-application
-- drift isolated to this one CREATE TABLE statement, not a wider rollback.
--
-- This migration re-applies the exact oauth_states definition from
-- 0003_phase4_schema.sql verbatim. Idempotent: CREATE TABLE IF NOT EXISTS, safe to
-- re-run and safe on any environment where the table already exists correctly.

CREATE TABLE IF NOT EXISTS public.oauth_states (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    state      text NOT NULL UNIQUE,
    created_at timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.oauth_states ENABLE ROW LEVEL SECURITY;

-- Service role writes; no user read policy needed (nonces are server-internal).
