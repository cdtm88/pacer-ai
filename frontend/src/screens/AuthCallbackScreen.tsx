import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { supabase } from '../lib/supabase'
import { useAuthStore } from '../stores/authStore'

// How long to wait for detectSessionInUrl's background PKCE exchange to
// resolve before assuming the code is genuinely invalid/expired and
// bouncing to /login. The code itself is valid server-side for 5 minutes;
// under normal network conditions the exchange resolves within a second or
// two of page load, so this is a generous ceiling, not a tuned budget.
const CALLBACK_TIMEOUT_MS = 6000

/**
 * Handles Supabase auth callbacks for both PKCE and implicit flows.
 *
 * PKCE flow (supabase-js v2 default): Supabase redirects with ?code=...
 * Implicit flow (older projects): Supabase redirects with #access_token=...
 *
 * IMPORTANT: do NOT call supabase.auth.exchangeCodeForSession() here for the
 * PKCE path. frontend/src/lib/supabase.ts sets detectSessionInUrl: true,
 * which already exchanges the single-use code for a session in the
 * background on client init. A second manual exchange races that background
 * exchange; per Supabase's own PKCE docs, exchanging the same code twice
 * violates the single-use constraint, and the losing attempt bounces a user
 * who actually has a valid session back to /login (item 11, ASVS V2).
 *
 * Instead, this screen watches authStore for the session that
 * useAuth.ts's global onAuthStateChange listener writes once
 * detectSessionInUrl's background exchange resolves, then navigates home.
 * A timeout falls back to /login if no session ever resolves (a genuinely
 * invalid/expired code).
 */
export function AuthCallbackScreen() {
  const navigate = useNavigate()
  const effectRan = useRef(false)
  const settled = useRef(false)

  useEffect(() => {
    if (effectRan.current) return
    effectRan.current = true

    const search = window.location.search
    const hash = window.location.hash

    const code = new URLSearchParams(search).get('code')

    if (code) {
      // PKCE flow — detectSessionInUrl is already exchanging this code in
      // the background; watch the store instead of exchanging it again.
      function tryNavigateHome() {
        if (settled.current) return
        const { session } = useAuthStore.getState()
        if (session) {
          settled.current = true
          navigate('/', { replace: true })
        }
      }

      // In case the session already resolved before this effect subscribed.
      tryNavigateHome()

      const unsubscribe = useAuthStore.subscribe(tryNavigateHome)
      const timeoutId = window.setTimeout(() => {
        if (settled.current) return
        settled.current = true
        navigate('/login', { replace: true })
      }, CALLBACK_TIMEOUT_MS)

      return () => {
        unsubscribe()
        window.clearTimeout(timeoutId)
      }
    }

    // Implicit flow — Supabase puts tokens in the URL hash (#access_token=...).
    // supabase-js parses the hash automatically; getSession() returns the result.
    const hashParams = new URLSearchParams(hash.slice(1))
    const hasImplicitTokens = hashParams.has('access_token')

    if (hasImplicitTokens) {
      supabase.auth.getSession().then(({ data: { session }, error }) => {
        if (error) {
          navigate('/login', { replace: true })
        } else if (session) {
          useAuthStore.getState().setAuth({
            session,
            user: session.user,
            isLoading: false,
          })
          navigate('/', { replace: true })
        } else {
          navigate('/login', { replace: true })
        }
      })
      return
    }

    // No code, no hash tokens — nothing to exchange.
    navigate('/login', { replace: true })
  }, [navigate])

  return (
    <div
      className="min-h-screen flex items-center justify-center"
      style={{ backgroundColor: 'var(--color-bg)' }}
    >
      <div
        className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
        style={{ borderColor: 'var(--color-blue-6)', borderTopColor: 'transparent' }}
        aria-label="Signing in..."
      />
    </div>
  )
}
