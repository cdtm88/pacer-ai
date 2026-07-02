-- PacerAI: Auto-provision public.users on auth.users insert (+ backfill)
-- Migration: 0004_auto_provision_users
-- Applied via: supabase db push --linked --yes
-- Purpose: A new signup lands only in auth.users; public.users had no matching row,
--          so inserting a conversations row (FK conversations_user_id_fkey ->
--          public.users.id) raised foreign_key_violation (23503) surfaced as HTTP 409.
--          This AFTER INSERT trigger provisions public.users automatically, and the
--          backfill repairs the existing orphaned auth.users rows.
-- Re-runnable: CREATE OR REPLACE + DROP TRIGGER IF EXISTS + ON CONFLICT DO NOTHING.

-- ============================================================
-- 1. Trigger function: insert (id, email) into public.users
--    SECURITY DEFINER: required so a function fired on auth.users can write into
--    public.users regardless of the invoking role.
--    SET search_path = public: hardens the SECURITY DEFINER function against
--    search_path hijacking.
-- ============================================================
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.users (id, email)
  VALUES (NEW.id, NEW.email)
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

-- ============================================================
-- 2. Trigger: fire after each new auth.users row
-- ============================================================
DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================
-- 3. Idempotent backfill for existing auth.users rows missing from public.users
-- ============================================================
INSERT INTO public.users (id, email)
SELECT id, email FROM auth.users
WHERE id NOT IN (SELECT id FROM public.users)
ON CONFLICT (id) DO NOTHING;
