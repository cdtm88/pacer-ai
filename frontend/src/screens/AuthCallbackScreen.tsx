import { useEffect, useRef } from 'react'
import { useNavigate } from 'react-router'
import { supabase } from '../lib/supabase'

/**
 * Handles the PKCE magic-link callback.
 *
 * Supabase v2 sends the user back with ?code= (PKCE flow). The code must be
 * explicitly exchanged for a session via exchangeCodeForSession() before
 * onAuthStateChange fires SIGNED_IN. Without this step the app has no session
 * and AuthGate redirects to /login, discarding the code.
 *
 * Supabase docs: https://supabase.com/docs/guides/auth/pkce-flow
 */
export function AuthCallbackScreen() {
  const navigate = useNavigate()
  const exchanged = useRef(false)

  useEffect(() => {
    if (exchanged.current) return
    exchanged.current = true

    const code = new URLSearchParams(window.location.search).get('code')

    if (!code) {
      // No code param — nothing to exchange, send to login.
      navigate('/login', { replace: true })
      return
    }

    supabase.auth
      .exchangeCodeForSession(code)
      .then(({ error }) => {
        if (error) {
          console.error('[AuthCallback] PKCE exchange failed:', error.message)
          navigate('/login', { replace: true })
        } else {
          // onAuthStateChange in useAuth will fire SIGNED_IN and populate authStore.
          // Navigate to root; AuthGate will let the user through once session is set.
          navigate('/', { replace: true })
        }
      })
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
