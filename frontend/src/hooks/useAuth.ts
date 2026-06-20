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
    // Seed initial state from the current session
    supabase.auth.getSession().then(({ data }) => {
      setAuth({
        session: data.session,
        user: data.session?.user ?? null,
        isLoading: false,
      })
    })

    // Subscribe to ongoing auth state changes
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
