import React from 'react'
import { useNavigate } from 'react-router'
import { toast } from 'sonner'
import { useQuery } from '@tanstack/react-query'
import { getProfileMe } from '@/lib/api'
import { supabase } from '@/lib/supabase'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
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

  // Physiological model the coach uses. Read-only for this pass: FTP, LTHR and
  // weight are estimated from ride data by the backend when not explicitly set,
  // so there is no write endpoint to surface here yet.
  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['profile', 'me'],
    queryFn: getProfileMe,
    staleTime: Infinity,
  })

  return (
    <div
      className="max-w-xl mx-auto px-5 py-8 space-y-6"
      style={{ color: 'var(--color-ink)' }}
    >
      {/* Training section */}
      <Card>
        <CardHeader>
          <CardTitle
            className="text-sm font-semibold uppercase tracking-wide"
            style={{ color: 'var(--color-ink-2)' }}
          >
            Training
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm" style={{ color: 'var(--color-ink-2)' }}>
            The physiological model your coach uses to set every session target.
          </p>

          <div className="space-y-3">
            <TrainingRow
              label="FTP"
              value={profile?.ftp ?? null}
              unit="W"
              loading={profileLoading}
            />
            <TrainingRow
              label="LTHR"
              value={profile?.lthr ?? null}
              unit="bpm"
              loading={profileLoading}
            />
            <TrainingRow
              label="Weight"
              value={profile?.weight_kg ?? null}
              unit="kg"
              loading={profileLoading}
            />
          </div>
        </CardContent>
      </Card>

      {/* Profile section */}
      <Card>
        <CardHeader>
          <CardTitle
            className="text-sm font-semibold uppercase tracking-wide"
            style={{ color: 'var(--color-ink-2)' }}
          >
            Profile
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <p className="text-xs mb-1" style={{ color: 'var(--color-ink-2)' }}>Display name</p>
            <p className="text-sm font-medium">{sessionState?.displayName ?? 'Loading...'}</p>
          </div>

          <div>
            <p className="text-xs mb-1" style={{ color: 'var(--color-ink-2)' }}>Email</p>
            <p className="text-sm" style={{ color: 'var(--color-ink-2)' }}>{sessionState?.email ?? 'Loading...'}</p>
          </div>

          {sessionState?.email && (
            <Button
              variant="link"
              className="h-auto p-0 text-sm"
              onClick={() => onResendMagicLink(sessionState.email)}
            >
              Re-send magic link
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Account section */}
      <Card>
        <CardHeader>
          <CardTitle
            className="text-sm font-semibold uppercase tracking-wide"
            style={{ color: 'var(--color-ink-2)' }}
          >
            Account
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="destructive" onClick={onSignOut}>
            Sign out
          </Button>
        </CardContent>
      </Card>
    </div>
  )
}

interface TrainingRowProps {
  label: string
  value: number | null
  unit: string
  loading: boolean
}

// A label/value row for the Training section. Shows the numeric value with
// tabular figures, or an "estimated from rides" hint when the value is null.
function TrainingRow({ label, value, unit, loading }: TrainingRowProps) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <p className="text-xs" style={{ color: 'var(--color-ink-2)' }}>{label}</p>
      {loading ? (
        <p className="text-sm" style={{ color: 'var(--color-ink-2)' }}>Loading...</p>
      ) : value != null ? (
        <p className="text-sm font-medium">
          <span className="stat-num">{value}</span>
          <span className="ml-1 text-xs" style={{ color: 'var(--color-ink-2)' }}>{unit}</span>
        </p>
      ) : (
        <p className="text-sm text-right" style={{ color: 'var(--color-ink-2)' }}>
          Not set yet
          <span className="block text-xs" style={{ color: 'var(--color-ink-3, var(--color-ink-2))' }}>
            Estimated from your rides
          </span>
        </p>
      )}
    </div>
  )
}

