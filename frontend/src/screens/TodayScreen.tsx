import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { Skeleton } from '@/components/ui/skeleton'
import { SessionCard } from '@/components/session/SessionCard'
import { getSessionToday, getUpcomingSessions, getLatestPmc } from '@/lib/api'

function formatNextRideDay(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { weekday: 'long' })
}

function formatStripDate(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

type ZoneType = 'recovery' | 'endurance' | 'tempo' | 'threshold' | 'vo2'
const ZONE_VAR: Record<ZoneType, string> = {
  recovery:  '--color-zone-recovery',
  endurance: '--color-zone-endurance',
  tempo:     '--color-zone-tempo',
  threshold: '--color-zone-threshold',
  vo2:       '--color-zone-vo2',
}
function isValidZone(type: string | null): type is ZoneType {
  return ['recovery', 'endurance', 'tempo', 'threshold', 'vo2'].includes(type ?? '')
}

export function TodayScreen() {
  const navigate = useNavigate()

  const {
    data: session,
    isLoading: sessionLoading,
    isError: sessionError,
    refetch: refetchSession,
  } = useQuery({
    queryKey: ['session', 'today'],
    queryFn: getSessionToday,
  })

  const {
    data: pmc,
  } = useQuery({
    queryKey: ['pmc', 'latest'],
    queryFn: getLatestPmc,
  })

  const {
    data: upcoming,
  } = useQuery({
    queryKey: ['sessions', 'upcoming'],
    queryFn: getUpcomingSessions,
  })

  // Loading state
  if (sessionLoading) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <Skeleton className="h-48 w-full rounded-xl mb-4" />
        <Skeleton className="h-10 w-full mb-2" />
        <Skeleton className="h-10 w-full" />
      </div>
    )
  }

  // Error state
  if (sessionError) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div
          className="rounded-xl p-6 text-center"
          style={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-line)' }}
        >
          <p style={{ color: 'var(--color-ink-2)', marginBottom: 12 }}>
            Could not load today's session. Pull down to refresh.
          </p>
          <button
            onClick={() => refetchSession()}
            style={{ color: 'var(--color-blue-7)', fontWeight: 500, fontSize: 14 }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  // Next upcoming session for empty state day label
  const nextSession = upcoming?.find(s => s.status === 'planned')

  // Empty state: no session today
  if (!session) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div
          className="rounded-xl p-6 text-center"
          style={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-line)' }}
        >
          <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--color-ink)', marginBottom: 8 }}>
            No session today
          </h2>
          <p style={{ fontSize: 16, color: 'var(--color-ink-2)' }}>
            {nextSession
              ? `Your next ride is ${formatNextRideDay((nextSession as {scheduled_date?: string}).scheduled_date ?? '')}. Rest up.`
              : 'Enjoy your rest day.'}
          </p>
        </div>
      </div>
    )
  }

  // Strip upcoming sessions (exclude today; show next few)
  const stripSessions = (upcoming ?? [])
    .filter(s => s.id !== session.id)
    .slice(0, 4)

  return (
    <div className="p-6 max-w-2xl mx-auto md:grid md:grid-cols-2 md:gap-6">
      {/* Left column: card + next-few-days */}
      <div>
        <SessionCard
          session={session as Parameters<typeof SessionCard>[0]['session']}
          pmc={pmc as Parameters<typeof SessionCard>[0]['pmc']}
        />

        {/* Next-few-days strip */}
        {stripSessions.length > 0 && (
          <div className="mt-6">
            <h3
              className="mb-3"
              style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-ink-2)' }}
            >
              Coming up
            </h3>
            <div
              className="flex md:flex-col gap-3 overflow-x-auto md:overflow-visible pb-2 md:pb-0"
            >
              {stripSessions.map((s) => {
                const zoneType = isValidZone((s as {type?: string | null}).type ?? null)
                  ? ((s as {type?: string | null}).type as ZoneType)
                  : null
                const scheduledDate = (s as {scheduled_date?: string}).scheduled_date ?? ''
                const durationMins = (s as {duration_mins?: number | null}).duration_mins
                  ?? (s as {duration_minutes?: number | null}).duration_minutes
                  ?? null

                return (
                  <button
                    key={s.id}
                    onClick={() => navigate('/agenda')}
                    className="flex items-center gap-3 rounded-lg px-4 py-3 shrink-0 text-left transition-colors"
                    style={{
                      backgroundColor: 'var(--color-surface)',
                      border: '1px solid var(--color-line)',
                      minWidth: 160,
                    }}
                  >
                    <span style={{ fontSize: 12, color: 'var(--color-ink-2)', width: 40 }}>
                      {formatStripDate(scheduledDate)}
                    </span>
                    <span style={{ fontSize: 14, fontWeight: 500, color: 'var(--color-ink)', flex: 1 }}>
                      {(s as {type?: string | null}).type ?? 'Session'}
                    </span>
                    {zoneType && (
                      <span
                        className="rounded-full shrink-0"
                        style={{
                          width: 8,
                          height: 8,
                          backgroundColor: `var(${ZONE_VAR[zoneType]})`,
                          display: 'inline-block',
                        }}
                      />
                    )}
                    {durationMins != null && (
                      <span style={{ fontSize: 12, color: 'var(--color-ink-3)' }}>
                        {durationMins}m
                      </span>
                    )}
                  </button>
                )
              })}
            </div>
          </div>
        )}
      </div>

      {/* Right column: reserved for Phase 2 fitness panel */}
      <div className="hidden md:block" />
    </div>
  )
}
