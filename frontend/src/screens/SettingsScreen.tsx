import React from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { CalendarStatus } from '@/components/settings/CalendarStatus'
import { supabase } from '@/lib/supabase'
export function SettingsScreen() {
  const navigate = useNavigate()

  async function handleResendMagicLink(email: string) {
    const { error } = await supabase.auth.signInWithOtp({ email })
    if (error) {
      toast.error('Could not send link. Please try again.')
    } else {
      toast.success('Magic link sent. Check your inbox.')
    }
  }

  async function handleSignOut() {
    await supabase.auth.signOut()
    navigate('/login')
  }

  return <SettingsScreenInner onSignOut={handleSignOut} onResendMagicLink={handleResendMagicLink} />
}

interface SettingsInnerProps {
  onSignOut: () => Promise<void>
  onResendMagicLink: (email: string) => Promise<void>
}

function SettingsScreenInner({ onSignOut, onResendMagicLink }: SettingsInnerProps) {
  // Load session synchronously from Supabase local storage.
  // The session is available synchronously via getSession() since it was already
  // resolved on mount by the auth guard higher in the tree.
  const [sessionState, setSessionState] = React.useState<{ email: string; displayName: string } | null>(null)

  React.useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      const s = data.session
      if (s) {
        setSessionState({
          email: s.user.email ?? '',
          displayName: s.user.user_metadata?.display_name ?? s.user.email ?? '',
        })
      }
    })
  }, [])

  return (
    <div
      className="max-w-xl mx-auto px-5 py-8 space-y-8"
      style={{ color: 'var(--color-ink)' }}
    >
      {/* Profile section */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--color-ink-2)' }}>
          Profile
        </h2>

        <div className="space-y-3">
          <div>
            <p className="text-xs mb-1" style={{ color: 'var(--color-ink-2)' }}>Display name</p>
            <p className="text-sm font-medium">{sessionState?.displayName ?? 'Loading...'}</p>
          </div>

          <div>
            <p className="text-xs mb-1" style={{ color: 'var(--color-ink-2)' }}>Email</p>
            <p className="text-sm" style={{ color: 'var(--color-ink-2)' }}>{sessionState?.email ?? 'Loading...'}</p>
          </div>

          {sessionState?.email && (
            <button
              className="text-sm underline"
              style={{ color: 'var(--color-accent)' }}
              onClick={() => onResendMagicLink(sessionState.email)}
            >
              Re-send magic link
            </button>
          )}
        </div>
      </section>

      <div style={{ height: 1, backgroundColor: 'var(--color-line)' }} />

      {/* Google Calendar section */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--color-ink-2)' }}>
          Google Calendar
        </h2>
        <p className="text-sm" style={{ color: 'var(--color-ink-2)' }}>
          Connect your Google Calendar to automatically sync planned sessions. Sessions appear as
          all-day events with full workout details.
        </p>
        <CalendarStatus />
      </section>

      <div style={{ height: 1, backgroundColor: 'var(--color-line)' }} />

      {/* Account section */}
      <section className="space-y-4">
        <h2 className="text-sm font-semibold uppercase tracking-wide" style={{ color: 'var(--color-ink-2)' }}>
          Account
        </h2>
        <button
          className="text-sm font-medium px-4 py-2 rounded-md border"
          style={{
            borderColor: 'var(--color-destructive, #dc2626)',
            color: 'var(--color-destructive, #dc2626)',
          }}
          onClick={onSignOut}
        >
          Sign out
        </button>
      </section>
    </div>
  )
}

