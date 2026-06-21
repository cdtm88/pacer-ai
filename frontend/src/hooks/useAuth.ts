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

    // On /auth/callback, AuthCallbackScreen owns session population via the PKCE
    // code exchange. Reading window.location.pathname once here is safe — the
    // effect fires synchronously on mount, before any navigation occurs.
    const onAuthCallback = window.location.pathname === '/auth/callback'

    // Seed the store with the persisted session immediately on mount so
    // AuthGate sees a valid session before onAuthStateChange fires.
    supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
      if (!active) return

      // Skip the null seed on /auth/callback: if the session is null here it
      // means the PKCE exchange has not completed yet. Writing
      // {session: null, isLoading: false} would cause AuthGate to bounce the
      // user to /login before AuthCallbackScreen can finish the exchange.
      // A non-null session (detectSessionInUrl already resolved) is always
      // written — real sessions are never withheld.
      if (onAuthCallback && initialSession === null) return

      setAuth({
        session: initialSession,
        user: initialSession?.user ?? null,
        isLoading: false,
      })
    })

    // onAuthStateChange keeps the store in sync after the initial seed.
    // Guard against transient INITIAL_SESSION null events clobbering a valid
    // session. Other null events (e.g. TOKEN_REFRESHED with a revoked token)
    // must clear the session so the user is not stuck in an authenticated state.
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((event, newSession) => {
      if (newSession === null && event === 'INITIAL_SESSION') return
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
