import { createClient } from '@supabase/supabase-js'

// Supabase client singleton — used for auth session management ONLY.
// Data queries go through api.ts via the FastAPI backend, not direct Supabase calls.
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY,
)
