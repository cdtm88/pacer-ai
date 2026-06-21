import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { supabase } from '../lib/supabase'
import { useAuthStore } from '../stores/authStore'

/**
 * Handles Supabase auth callbacks for both PKCE and implicit flows.
 *
 * PKCE flow (supabase-js v2 default): Supabase redirects with ?code=...
 * Implicit flow (older projects): Supabase redirects with #access_token=...
 *
 * GoTrue-JS fires SIGNED_IN via setTimeout(0) — after the .then() callback
 * runs. We populate authStore directly from the exchange result so AuthGate
 * sees a valid session when navigate('/') triggers its render.
 */
export function AuthCallbackScreen() {
  const navigate = useNavigate()
  const exchanged = useRef(false)

  useEffect(() => {
    if (exchanged.current) return
    exchanged.current = true

    const search = window.location.search
    const hash = window.location.hash

    // Debug: log what the callback received so we can see which flow is active
    console.log('[AuthCallback] search:', search)
    console.log('[AuthCallback] hash:', hash)

    const code = new URLSearchParams(search).get('code')

    if (code) {
      // PKCE flow — exchange the authorization code for a session
      supabase.auth
        .exchangeCodeForSession(code)
        .then(({ data, error }) => {
          if (error) {
            console.error('[AuthCallback] PKCE exchange failed:', error.message)
            navigate('/login', { replace: true })
          } else {
            // GoTrue fires SIGNED_IN via setTimeout(0) — deferred past this .then().
            // Populate authStore directly so AuthGate sees the session immediately.
            useAuthStore.getState().setAuth({
              session: data.session,
              user: data.session.user,
              isLoading: false,
            })
            navigate('/', { replace: true })
          }
        })
      return
    }

    // Implicit flow — Supabase puts tokens in the URL hash (#access_token=...).
    // supabase-js parses the hash automatically; getSession() returns the result.
    const hashParams = new URLSearchParams(hash.slice(1))
    const hasImplicitTokens = hashParams.has('access_token')

    if (hasImplicitTokens) {
      supabase.auth.getSession().then(({ data: { session }, error }) => {
        if (error) {
          console.error('[AuthCallback] Implicit session failed:', error.message)
          navigate('/login', { replace: true })
        } else if (session) {
          useAuthStore.getState().setAuth({
            session,
            user: session.user,
            isLoading: false,
          })
          navigate('/', { replace: true })
        } else {
          console.warn('[AuthCallback] Implicit flow detected but getSession() returned null')
          navigate('/login', { replace: true })
        }
      })
      return
    }

    // No code, no hash tokens — nothing to exchange.
    console.warn('[AuthCallback] No code or access_token found in callback URL')
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
