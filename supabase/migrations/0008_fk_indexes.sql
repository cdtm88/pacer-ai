-- 0008: Add btree indexes on every user_id/FK column (2026-07-03).
-- Numbered 0008 (not 0007) because 0007 is reserved for the oauth_states
-- schema-drift repair this migration depends on -- see 0007_repair_oauth_states.sql.
--
-- Zero indexing statements existed across migrations 0001-0006. Every
-- list/detail query filtering or joining on a user_id or foreign-key column
-- was doing a sequential scan on the linked project. This migration adds
-- one idempotent index per FK/user_id column across all tables.
--
-- No RLS, policy, permission, table, or column changes -- indexes only.

CREATE INDEX IF NOT EXISTS idx_profiles_user_id ON public.profiles (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON public.sessions (user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_plan_id ON public.sessions (plan_id);
CREATE INDEX IF NOT EXISTS idx_rides_user_id ON public.rides (user_id);
CREATE INDEX IF NOT EXISTS idx_rides_session_id ON public.rides (session_id);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON public.conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON public.messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_user_id ON public.messages (user_id);
CREATE INDEX IF NOT EXISTS idx_capability_gaps_user_id ON public.capability_gaps (user_id);
CREATE INDEX IF NOT EXISTS idx_oauth_states_user_id ON public.oauth_states (user_id);
CREATE INDEX IF NOT EXISTS idx_plans_user_id ON public.plans (user_id);
CREATE INDEX IF NOT EXISTS idx_adaptations_user_id ON public.adaptations (user_id);

-- pmc_history(user_id, date) already has a composite unique index from 0006
-- (pmc_history_user_id_date_key), which serves user_id-only lookups via
-- leftmost-prefix matching -- no additional index needed there.
