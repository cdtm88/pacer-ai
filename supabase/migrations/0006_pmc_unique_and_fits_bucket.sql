-- 0006: Close two live-verification gaps found during Phase 6 UAT (2026-07-03).
--
-- 1. pmc_history was missing the composite unique key that the bulk upsert in
--    backend/pmc_recompute.py targets with on_conflict="user_id,date".
--    Without it PostgREST rejects the upsert with 42P10 and the PMC series is
--    never written. Idempotent: skip if the constraint already exists.
--
-- 2. The `fits` storage bucket referenced by the ride upload pipeline
--    (backend/routes/rides.py) was never provisioned as code; uploads logged
--    "Bucket not found" and raw_fit_path stayed NULL. Private bucket; access
--    is service-role only (no storage RLS policies added).

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'pmc_history_user_id_date_key'
      AND conrelid = 'public.pmc_history'::regclass
  ) THEN
    ALTER TABLE public.pmc_history
      ADD CONSTRAINT pmc_history_user_id_date_key UNIQUE (user_id, date);
  END IF;
END $$;

INSERT INTO storage.buckets (id, name, public)
VALUES ('fits', 'fits', false)
ON CONFLICT (id) DO NOTHING;
