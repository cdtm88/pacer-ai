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
import { sessionTypeLabel, ZONE_META, type ZoneKey } from '@/lib/format'

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
  planned_tss: number | null
}

// Zone order for the intensity legend, low to high.
const LEGEND_ZONES: ZoneKey[] = ['recovery', 'endurance', 'tempo', 'threshold', 'vo2']

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

/** Format a total minute count as "Xh Ym", collapsing zero parts. */
function formatDurationTotal(mins: number): string {
  const h = Math.floor(mins / 60)
  const m = mins % 60
  if (h === 0) return `${m}m`
  if (m === 0) return `${h}h`
  return `${h}h ${m}m`
}

/** Local calendar date as YYYY-MM-DD for "today" row matching. */
function todayISO(): string {
  const d = new Date()
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const da = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${mo}-${da}`
}

interface WeekTotals {
  count: number
  mins: number
  tss: number
}

function computeWeekTotals(weekSessions: SessionRow[]): WeekTotals {
  return weekSessions.reduce<WeekTotals>(
    (acc, s) => ({
      count: acc.count + 1,
      mins: acc.mins + (getDuration(s) ?? 0),
      tss: acc.tss + (s.planned_tss ?? 0),
    }),
    { count: 0, mins: 0, tss: 0 },
  )
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
  const today = todayISO()

  return (
    <div className="max-w-2xl mx-auto pb-8">
      {/* Intensity legend: decode the zone dot colors for beginners */}
      <div className="px-6 pt-4 pb-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
          {LEGEND_ZONES.map((z) => (
            <span key={z} className="flex items-center gap-1.5">
              <span
                className="rounded-full inline-block"
                style={{ width: 10, height: 10, backgroundColor: ZONE_META[z].color }}
              />
              <span style={{ fontSize: 12, color: 'var(--color-ink-2)' }}>
                {ZONE_META[z].label}
              </span>
            </span>
          ))}
        </div>
      </div>

      {weeks.map(([weekStart, weekSessions]) => {
        const totals = computeWeekTotals(weekSessions)
        return (
        <div key={weekStart}>
          {/* Sticky week header with load summary */}
          <div
            className="sticky top-0 z-10 px-6 py-2 flex items-baseline justify-between gap-3"
            style={{ backgroundColor: 'var(--color-bg)' }}
          >
            <span style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ink)' }}>
              {formatWeekHeader(weekStart)}
            </span>
            <span
              className="stat-num"
              style={{ fontSize: 12, fontWeight: 500, color: 'var(--color-ink-2)' }}
            >
              {totals.count} {totals.count === 1 ? 'session' : 'sessions'}
              {' · '}
              {formatDurationTotal(totals.mins)}
              {totals.tss > 0 && ` · ${Math.round(totals.tss)} TSS`}
            </span>
          </div>

          <div className="px-4">
            <Accordion type="multiple">
              {weekSessions.map((s) => {
                const zoneType = isValidZone(s.type) ? s.type : null
                const duration = getDuration(s)
                const structureText = getStructureText(s.structure)
                const isCompleted = s.status === 'completed'
                const isMissed = s.status === 'skipped' || s.status === 'missed'
                const isToday = s.scheduled_date === today

                return (
                  <AccordionItem
                    key={s.id}
                    value={s.id}
                    style={{
                      borderBottom: '1px solid var(--color-line)',
                      backgroundColor: isToday
                        ? 'color-mix(in srgb, var(--color-brand) 8%, var(--color-surface))'
                        : undefined,
                    }}
                  >
                    <AccordionTrigger className="hover:no-underline py-4">
                      <div className="flex items-center gap-3 w-full text-left">
                        {/* Date column */}
                        <span
                          className="stat-num"
                          style={{
                            width: 48,
                            fontSize: 12,
                            color: isToday ? 'var(--color-brand)' : 'var(--color-ink-2)',
                            fontWeight: isToday ? 600 : undefined,
                            flexShrink: 0,
                          }}
                        >
                          {isToday ? 'Today' : formatRowDate(s.scheduled_date)}
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
                            <span
                              style={{
                                fontSize: 12,
                                color: 'var(--color-ink-2)',
                                fontVariantNumeric: 'tabular-nums',
                              }}
                            >
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
                          <p
                            style={{
                              fontSize: 14,
                              color: 'var(--color-ink-2)',
                              fontVariantNumeric: 'tabular-nums',
                            }}
                          >
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
        )
      })}
    </div>
  )
}
