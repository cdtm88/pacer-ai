-- PacerAI: Initial 8-table schema with Row Level Security
-- Migration: 0001_initial_schema
-- Applied via: supabase db push
-- RLS strategy: user-owns-row (user_id = auth.uid()) on all tables
-- capability_gaps: backend inserts use SUPABASE_SERVICE_ROLE_KEY to bypass RLS (Pitfall 6)

-- ============================================================
-- 1. users
-- ============================================================
CREATE TABLE public.users (
    id          uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
    email       text NOT NULL,
    google_tokens jsonb,             -- encrypted at app layer (Phase 3)
    created_at  timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users: own row" ON public.users
    USING (id = auth.uid());

-- ============================================================
-- 2. profiles
-- ============================================================
CREATE TABLE public.profiles (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    -- Back-protective and fitness constraints (D-09)
    -- Default: no back issues. Full schema example:
    -- {"back_issues": true, "max_initial_weekly_hours": 3.5,
    --  "no_standing_efforts": true, "no_sprint_efforts": true,
    --  "load_ramp_flag_threshold_pct": 10}
    constraints jsonb DEFAULT '{"back_issues": false}'::jsonb NOT NULL,
    -- Baseline interview data
    fitness_level   text,
    equipment       jsonb,
    goals           jsonb,
    created_at  timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

CREATE POLICY "profiles: own row" ON public.profiles
    USING (user_id = auth.uid());

-- ============================================================
-- 3. sessions
-- ============================================================
CREATE TABLE public.sessions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    objective       text,
    structure       jsonb,
    targets         jsonb,
    duration_mins   int,
    status          text NOT NULL DEFAULT 'planned',
    scheduled_date  date,
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.sessions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "sessions: own row" ON public.sessions
    USING (user_id = auth.uid());

-- ============================================================
-- 4. rides
-- ============================================================
CREATE TABLE public.rides (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    tss             numeric,
    np_watts        numeric,
    intensity_factor numeric,
    duration_secs   int,
    raw_fit_path    text,           -- path in Supabase Storage
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.rides ENABLE ROW LEVEL SECURITY;

CREATE POLICY "rides: own row" ON public.rides
    USING (user_id = auth.uid());

-- ============================================================
-- 5. pmc_history
-- ============================================================
CREATE TABLE public.pmc_history (
    id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    date                date NOT NULL,
    ctl                 numeric NOT NULL,
    atl                 numeric NOT NULL,
    tsb                 numeric NOT NULL,
    tss_display_ready   boolean NOT NULL DEFAULT false,
    created_at          timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.pmc_history ENABLE ROW LEVEL SECURITY;

CREATE POLICY "pmc_history: own row" ON public.pmc_history
    USING (user_id = auth.uid());

-- ============================================================
-- 6. conversations
-- ============================================================
CREATE TABLE public.conversations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    created_at  timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.conversations ENABLE ROW LEVEL SECURITY;

CREATE POLICY "conversations: own row" ON public.conversations
    USING (user_id = auth.uid());

-- ============================================================
-- 7. messages
-- ============================================================
CREATE TABLE public.messages (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id uuid NOT NULL REFERENCES public.conversations ON DELETE CASCADE,
    user_id         uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    role            text NOT NULL,  -- 'user' | 'assistant'
    content         text NOT NULL,
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.messages ENABLE ROW LEVEL SECURITY;

CREATE POLICY "messages: own row" ON public.messages
    USING (user_id = auth.uid());

-- ============================================================
-- 8. capability_gaps
-- ============================================================
-- Backend inserts use SUPABASE_SERVICE_ROLE_KEY to bypass RLS (Pitfall 6, D-07).
-- The RLS read policy still exists so authenticated users can read their own gaps.
-- Never use the anon key for writes to this table from the backend.
CREATE TABLE public.capability_gaps (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid,           -- nullable: gaps can be logged before auth
    method_name     text NOT NULL,
    description     text,
    context         jsonb,
    conversation_id uuid,           -- nullable: may not be in a conversation context
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.capability_gaps ENABLE ROW LEVEL SECURITY;

-- Read policy: users can read their own gaps (backend writes bypass this via service-role key)
CREATE POLICY "capability_gaps: own row" ON public.capability_gaps
    USING (user_id = auth.uid());
