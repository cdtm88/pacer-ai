-- 0009: Phase 8 Trust Model Integrity (2026-07-04).
--
-- 1. audit_log: durable, verifiable per-tool-call trail (TRUST-04/TRUST-06).
--    Written best-effort from dispatch_tool via backend/agent/audit.py; never
--    blocks the tool result on write failure (D-14). Also serves as the
--    cross-turn reload source for D-04's tool_result_values seeding, since
--    the messages table never receives tool_result content (see RESEARCH.md
--    Pitfall 1).
-- 2. profiles.hr_zones_available: D-05's explicit "neither LTHR nor max HR
--    known" flag. When false, calculate_hr_zones/generate_plan's HR-based
--    targets are skipped entirely in favor of the existing cold-start
--    RPE-only path (Phase 3 D-07). Written by a later plan in this phase.

CREATE TABLE IF NOT EXISTS public.audit_log (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid,           -- nullable: some tool calls precede auth resolution
    conversation_id uuid,           -- nullable: not every dispatch_tool call site has one yet
    tool_use_id     text NOT NULL,
    tool_name       text NOT NULL,
    inputs          jsonb,
    result          jsonb,          -- ToolResult.model_dump(), or null on error
    is_error        boolean NOT NULL DEFAULT false,
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'audit_log'
      AND policyname = 'audit_log: own row'
  ) THEN
    CREATE POLICY "audit_log: own row" ON public.audit_log
        USING (user_id = auth.uid());
  END IF;
END $$;

-- Index for D-04's cross-turn reload (scoped by conversation, ordered by time).
CREATE INDEX IF NOT EXISTS audit_log_conversation_created_idx
    ON public.audit_log (conversation_id, created_at);

-- hr_zones_available: D-05's explicit "neither LTHR nor max HR known" flag.
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS hr_zones_available boolean;
