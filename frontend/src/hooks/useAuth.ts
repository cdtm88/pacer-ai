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
    let active = true

    // Seed the store with the persisted session immediately on mount so
    // AuthGate sees a valid session before onAuthStateChange fires.
    supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
      if (!active) return
      setAuth({
        session: initialSession,
        user: initialSession?.user ?? null,
        isLoading: false,
      })
    })

    // onAuthStateChange keeps the store in sync after the initial seed.
    // Guard against transient null events (e.g. INITIAL_SESSION races) clobbering
    // a valid session — only SIGNED_OUT is allowed to clear it.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, newSession) => {
      if (newSession === null && event !== 'SIGNED_OUT') return
      setAuth({
        session: newSession,
        user: newSession?.user ?? null,
        isLoading: false,
      })
    })

    return () => {
      active = false
      subscription.unsubscribe()
    }
  }, [setAuth])

  return { session, user, isLoading }
}
