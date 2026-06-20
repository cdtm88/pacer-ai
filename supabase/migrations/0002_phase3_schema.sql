-- PacerAI: Phase 3 schema additions
-- Migration: 0002_phase3_schema
-- Applied via: supabase db push
-- RLS strategy: user-owns-row (user_id = auth.uid()) on all tables
-- New tables use SERVICE_ROLE_KEY for backend inserts (same as capability_gaps)

-- ============================================================
-- 1. profiles: add interview-collected fields
-- ============================================================
ALTER TABLE public.profiles
  ADD COLUMN back_status    text NOT NULL DEFAULT 'none'
                            CHECK (back_status IN ('none', 'mild', 'moderate')),
  ADD COLUMN weekly_hours   numeric,
  ADD COLUMN preferred_days text[],
  ADD COLUMN rpe_baseline   text,
  ADD COLUMN lthr_estimate  numeric;

-- profiles: unique constraint so save_profile can upsert via ON CONFLICT (user_id) DO UPDATE
ALTER TABLE public.profiles
  ADD CONSTRAINT profiles_user_id_unique UNIQUE (user_id);

-- ============================================================
-- 2. plans: new table (must exist before sessions.plan_id FK)
-- ============================================================
CREATE TABLE public.plans (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    sessions        jsonb NOT NULL,         -- array of session objects from generate_plan
    mesocycle_weeks int NOT NULL DEFAULT 4,
    ftp_confidence  text,                   -- confidence at plan generation time
    status          text NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'completed', 'superseded')),
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.plans ENABLE ROW LEVEL SECURITY;
CREATE POLICY "plans: own row" ON public.plans USING (user_id = auth.uid());

-- ============================================================
-- 3. sessions: add plan linkage and richer schema
-- ============================================================
-- plans table already created above, so sessions.plan_id FK resolves
ALTER TABLE public.sessions
  ADD COLUMN plan_id       uuid REFERENCES public.plans ON DELETE CASCADE,
  ADD COLUMN type          text CHECK (type IN ('endurance', 'recovery', 'strength', 'interval')),
  ADD COLUMN zone_targets  jsonb,
  ADD COLUMN power_targets jsonb,
  ADD COLUMN week_num      int,
  ADD COLUMN rpe_target    int;

-- ============================================================
-- 4. rides: add session linkage and raw metrics
-- ============================================================
ALTER TABLE public.rides
  ADD COLUMN session_id   uuid REFERENCES public.sessions ON DELETE SET NULL,
  ADD COLUMN ride_date    date,
  ADD COLUMN avg_power    numeric,
  ADD COLUMN avg_hr       numeric,
  ADD COLUMN avg_cadence  numeric,
  ADD COLUMN ftp_used     numeric;  -- FTP value used for TSS calc (audit trail)

-- ============================================================
-- 5. conversations: add context_type (D-21)
-- ============================================================
ALTER TABLE public.conversations
  ADD COLUMN context_type text NOT NULL DEFAULT 'coaching'
             CHECK (context_type IN ('onboarding', 'coaching', 'ride_debrief'));

-- ============================================================
-- 6. adaptations: audit trail for every plan change (D-20, TRANSP-02)
-- ============================================================
CREATE TABLE public.adaptations (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    trigger          text NOT NULL CHECK (trigger IN ('missed', 'underperformance', 'overreaching')),
    signal_count     int NOT NULL DEFAULT 1,
    scope            text NOT NULL CHECK (scope IN ('micro', 'macro')),
    before_snapshot  jsonb,       -- sessions before change
    after_snapshot   jsonb,       -- sessions after change
    explanation_text text,        -- user-facing explanation cited in chat
    created_at       timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.adaptations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "adaptations: own row" ON public.adaptations USING (user_id = auth.uid());
