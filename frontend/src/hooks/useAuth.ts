import { useEffect } from 'react'
import { supabase } from '../lib/supabase'
import { useAuthStore } from '../stores/authStore'

/**
 * Subscribe to Supabase auth state changes and keep the authStore in sync.
 * Call once near the app root (e.g., RootProvider or main.tsx).
 * Unsubscribes on cleanup.
 */
export function useAuth() {
  const { session, user, isLoading, setAuth } = useAuthStore()

  useEffect(() => {
    // onAuthStateChange fires INITIAL_SESSION once Supabase has fully determined
    // the session — including parsing magic-link tokens from the URL hash.
    // Using getSession() here races against that hash parsing and can resolve
    // null before the token is extracted, causing AuthGate to redirect to /login
    // and discard the hash before onAuthStateChange fires.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setAuth({
        session: newSession,
        user: newSession?.user ?? null,
        isLoading: false,
      })
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [setAuth])

  return { session, user, isLoading }
}
