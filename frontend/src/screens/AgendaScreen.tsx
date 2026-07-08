import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router'
import { CheckCircle, XCircle } from 'lucide-react'
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Skeleton } from '@/components/ui/skeleton'
import { getUpcomingSessions } from '@/lib/api'
import { sessionTypeLabel } from '@/lib/format'

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

interface SessionRow {
  id: string
  scheduled_date: string
  type: string | null
  objective: string | null
  structure: { text?: string } | string | null
  status: string
  duration_mins: number | null
  duration_minutes: number | null
  rpe_target: number | null
}

function getISOWeekStart(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00')
  const day = d.getDay()
  const diff = d.getDate() - day + (day === 0 ? -6 : 1)
  const monday = new Date(d)
  monday.setDate(diff)
  return monday.toISOString().slice(0, 10)
}

function formatWeekHeader(weekStart: string): string {
  const d = new Date(weekStart + 'T12:00:00')
  return `Week of ${d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}`
}

function formatRowDate(dateStr: string): string {
  const d = new Date(dateStr + 'T12:00:00')
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function getStructureText(structure: SessionRow['structure']): string {
  if (!structure) return ''
  if (typeof structure === 'string') return structure
  return structure.text ?? ''
}

function getDuration(s: SessionRow): number | null {
  return s.duration_minutes ?? s.duration_mins ?? null
}

export function AgendaScreen() {
  const navigate = useNavigate()

  const {
    data: sessions,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['sessions', 'upcoming'],
    queryFn: getUpcomingSessions,
  })

  if (isLoading) {
    return (
      <div className="p-6 max-w-2xl mx-auto space-y-3">
        {[1, 2, 3].map(i => (
          <Skeleton key={i} className="h-16 w-full rounded-lg" />
        ))}
      </div>
    )
  }

  if (isError) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div
          className="rounded-xl p-6 text-center"
          style={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-line)' }}
        >
          <p style={{ color: 'var(--color-ink-2)', marginBottom: 12 }}>
            Could not load your plan. Tap to retry.
          </p>
          <button
            onClick={() => refetch()}
            style={{ color: 'var(--color-blue-7)', fontWeight: 500, fontSize: 14 }}
          >
            Retry
          </button>
        </div>
      </div>
    )
  }

  if (!sessions || sessions.length === 0) {
    return (
      <div className="p-6 max-w-2xl mx-auto">
        <div
          className="rounded-xl p-6 text-center"
          style={{ backgroundColor: 'var(--color-surface)', border: '1px solid var(--color-line)' }}
        >
          <h2 style={{ fontSize: 20, fontWeight: 600, color: 'var(--color-ink)', marginBottom: 8 }}>
            No sessions planned yet
          </h2>
          <p style={{ fontSize: 16, color: 'var(--color-ink-2)', marginBottom: 16 }}>
            Complete the interview in Chat to generate your plan.
          </p>
          <button
            onClick={() => navigate('/chat')}
            style={{ color: 'var(--color-blue-7)', fontWeight: 500, fontSize: 14 }}
          >
            Go to Chat
          </button>
        </div>
      </div>
    )
  }

  // Group sessions by ISO week
  const rows = sessions as unknown as SessionRow[]
  const weekMap = new Map<string, SessionRow[]>()
  for (const s of rows) {
    const weekStart = getISOWeekStart(s.scheduled_date)
    if (!weekMap.has(weekStart)) weekMap.set(weekStart, [])
    weekMap.get(weekStart)!.push(s)
  }
  const weeks = Array.from(weekMap.entries()).sort(([a], [b]) => a.localeCompare(b))

  return (
    <div className="max-w-2xl mx-auto pb-8">
      {weeks.map(([weekStart, weekSessions]) => (
        <div key={weekStart}>
          {/* Sticky week header */}
          <div
            className="sticky top-0 z-10 px-6 py-2"
            style={{
              backgroundColor: 'var(--color-bg)',
              fontSize: 14,
              fontWeight: 500,
              color: 'var(--color-ink-2)',
            }}
          >
            {formatWeekHeader(weekStart)}
          </div>

          <div className="px-4">
            <Accordion type="multiple">
              {weekSessions.map((s) => {
                const zoneType = isValidZone(s.type) ? s.type : null
                const duration = getDuration(s)
                const structureText = getStructureText(s.structure)
                const isCompleted = s.status === 'completed'
                const isMissed = s.status === 'skipped' || s.status === 'missed'

                return (
                  <AccordionItem
                    key={s.id}
                    value={s.id}
                    style={{ borderBottom: '1px solid var(--color-line)' }}
                  >
                    <AccordionTrigger className="hover:no-underline py-4">
                      <div className="flex items-center gap-3 w-full text-left">
                        {/* Date column */}
                        <span
                          style={{
                            width: 48,
                            fontSize: 12,
                            color: 'var(--color-ink-2)',
                            flexShrink: 0,
                          }}
                        >
                          {formatRowDate(s.scheduled_date)}
                        </span>

                        {/* Type + objective preview */}
                        <div className="flex-1 min-w-0">
                          <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ink)' }}>
                            {sessionTypeLabel(s.type)}
                          </p>
                          {s.objective && (
                            <p
                              className="truncate"
                              style={{ fontSize: 12, color: 'var(--color-ink-3)' }}
                            >
                              {s.objective}
                            </p>
                          )}
                        </div>

                        {/* Zone dot + duration + status */}
                        <div className="flex items-center gap-2 shrink-0">
                          {zoneType && (
                            <span
                              className="rounded-full inline-block"
                              style={{
                                width: 12,
                                height: 12,
                                backgroundColor: `var(${ZONE_VAR[zoneType]})`,
                              }}
                            />
                          )}
                          {duration != null && (
                            <span style={{ fontSize: 12, color: 'var(--color-ink-2)' }}>
                              {duration}m
                            </span>
                          )}
                          {isCompleted && (
                            <CheckCircle size={16} style={{ color: 'var(--color-good)' }} />
                          )}
                          {isMissed && (
                            <XCircle size={16} style={{ color: 'var(--color-bad)' }} />
                          )}
                        </div>
                      </div>
                    </AccordionTrigger>

                    <AccordionContent>
                      <div className="pb-4 pl-15 space-y-2">
                        {s.objective && (
                          <p style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-ink)' }}>
                            {s.objective}
                          </p>
                        )}
                        {structureText && (
                          <p style={{ fontSize: 16, color: 'var(--color-ink-2)' }}>
                            {structureText}
                          </p>
                        )}
                        {s.rpe_target != null && (
                          <p style={{ fontSize: 14, color: 'var(--color-ink-2)' }}>
                            Target RPE: {s.rpe_target}
                          </p>
                        )}
                      </div>
                    </AccordionContent>
                  </AccordionItem>
                )
              })}
            </Accordion>
          </div>
        </div>
      ))}
    </div>
  )
}
