-- PacerAI: Phase 4 schema additions
-- Migration: 0003_phase4_schema
-- Applied via: supabase db push --linked --yes
-- Purpose: Adds calendar tracking, TSS target, duration alias, compliance pct,
--          and conversation context storage columns required by Phase 4 UI endpoints.
--          All ADD COLUMN statements use IF NOT EXISTS for idempotency against a live
--          schema that may already carry some of these columns (Open Question 2).

-- ============================================================
-- 1. sessions: calendar tracking and missing columns
-- ============================================================
-- calendar_event_id: Google Calendar event id for CAL-02 update/delete
ALTER TABLE public.sessions
  ADD COLUMN IF NOT EXISTS calendar_event_id text;

-- tss_target: referenced by adaptations.py detect_signals but absent from Phase 3 schema
ALTER TABLE public.sessions
  ADD COLUMN IF NOT EXISTS tss_target numeric;

-- duration_minutes: adaptations.py queries this name; existing column is duration_mins
-- Kept separate from duration_mins (no rename) to avoid breaking existing queries
ALTER TABLE public.sessions
  ADD COLUMN IF NOT EXISTS duration_minutes int;

-- ============================================================
-- 2. rides: compliance percentage from validate_session_vs_actual
-- ============================================================
-- compliance_pct: written by rides.py from validate_session_vs_actual (ADAPT-05)
ALTER TABLE public.rides
  ADD COLUMN IF NOT EXISTS compliance_pct numeric;

-- ============================================================
-- 3. conversations: ride debrief context storage
-- ============================================================
-- context_data: used by rides.py for ride_debrief context (D-23)
ALTER TABLE public.conversations
  ADD COLUMN IF NOT EXISTS context_data text;

-- ============================================================
-- 4. oauth_states: short-lived CSRF nonces for Google OAuth (T-04-21)
-- ============================================================
-- Used by /calendar/auth-redirect-url and /calendar/auth callback to
-- store and verify state nonces, preventing CSRF attacks.
CREATE TABLE IF NOT EXISTS public.oauth_states (
    id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    state      text NOT NULL UNIQUE,
    created_at timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.oauth_states ENABLE ROW LEVEL SECURITY;

-- Service role writes; no user read policy needed (nonces are server-internal)
