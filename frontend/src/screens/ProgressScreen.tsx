import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getRides, getPmcHistory, getLatestPmc, getAdaptations } from '../lib/api'
import type { Ride } from '../lib/api'
import { classifyTsb, triggerLabel, formatDate } from '../lib/format'
import { StatTile } from '../components/ui/StatTile'
import { FitUploadZone } from '../components/history/FitUploadZone'
import { RideRow } from '../components/history/RideRow'
import { PmcChart } from '../components/progress/PmcChart'
import { WeeklyLoadChart } from '../components/progress/WeeklyLoadChart'
import { weekKey, isSameWeek } from '../components/progress/week'

// ---------------------------------------------------------------------------
// ProgressScreen — the emotional core: "am I getting fitter?".
//
// Top to bottom, in a centered ~720px column:
//   1. KPI row: Fitness (CTL + ~28d delta), Form (TSB, classified), This week (TSS)
//   2. PmcChart — CTL/ATL/TSB trend with a time-range toggle
//   3. WeeklyLoadChart — last ~8 ISO weeks of ride TSS
//   4. Ride log (folded in from the old History screen): compact upload zone
//      plus RideRows grouped by ISO week.
// ---------------------------------------------------------------------------

function SkeletonRow() {
  return (
    <div
      style={{
        height: '52px',
        borderRadius: '6px',
        backgroundColor: 'var(--color-line-2)',
        marginBottom: '8px',
        animation: 'pulse 1.5s ease-in-out infinite',
      }}
    />
  )
}

function SectionLabel({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: '0.06em',
        textTransform: 'uppercase',
        color: 'var(--color-ink-3)',
        margin: '0 0 8px',
      }}
    >
      {children}
    </div>
  )
}

// Find the PMC entry closest to `daysBack` days before the latest entry, so the
// Fitness delta reflects roughly a month of change rather than yesterday.
function ctlDelta(history: { date: string; ctl: number }[], daysBack = 28): number | null {
  if (history.length < 2) return null
  const latest = history[history.length - 1]
  const target = new Date(latest.date).getTime() - daysBack * 86_400_000
  let best = history[0]
  let bestGap = Infinity
  for (const row of history) {
    const gap = Math.abs(new Date(row.date).getTime() - target)
    if (gap < bestGap) {
      bestGap = gap
      best = row
    }
  }
  return latest.ctl - best.ctl
}

// Group rides into ISO weeks, most recent week first, rides sorted newest-first.
function groupByWeek(rides: Ride[]): { key: string; label: string; rides: Ride[] }[] {
  const sorted = [...rides].sort(
    (a, b) => new Date(b.ride_date).getTime() - new Date(a.ride_date).getTime()
  )
  const groups: { key: string; label: string; rides: Ride[] }[] = []
  const index = new Map<string, number>()
  for (const ride of sorted) {
    const key = weekKey(ride.ride_date)
    if (!index.has(key)) {
      index.set(key, groups.length)
      const monday = new Date(key)
      const label = isSameWeek(ride.ride_date)
        ? 'This week'
        : `Week of ${monday.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
      groups.push({ key, label, rides: [] })
    }
    groups[index.get(key)!].rides.push(ride)
  }
  return groups
}

export function ProgressScreen() {
  const ridesQuery = useQuery({ queryKey: ['rides'], queryFn: getRides })
  const pmcQuery = useQuery({ queryKey: ['pmc-history'], queryFn: getPmcHistory })
  const latestQuery = useQuery({ queryKey: ['pmc', 'latest'], queryFn: getLatestPmc })
  const adaptationsQuery = useQuery({ queryKey: ['adaptations'], queryFn: getAdaptations })

  const rides = ridesQuery.data ?? []
  const pmcHistory = pmcQuery.data ?? []
  const latest = latestQuery.data ?? null
  const adaptations = adaptationsQuery.data ?? []

  // KPI: Fitness (CTL) + ~28d delta.
  const ctl = latest?.ctl ?? null
  const delta = ctlDelta(pmcHistory)
  const ctlTone = delta == null ? 'flat' : delta > 0.5 ? 'up' : delta < -0.5 ? 'down' : 'flat'

  // KPI: Form (TSB), classified for color + label.
  const tsb = latest?.tsb ?? null
  const tsbClass = tsb != null ? classifyTsb(tsb) : null

  // KPI: This week's ride TSS + ride count.
  const weekRides = rides.filter((r) => isSameWeek(r.ride_date))
  const weekTss = Math.round(
    weekRides.reduce((s, r) => s + (r.tss ?? 0), 0)
  )

  const grouped = groupByWeek(rides)

  return (
    <div
      style={{
        height: '100%',
        overflowY: 'auto',
        backgroundColor: 'var(--color-bg)',
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: 720,
          margin: '0 auto',
          padding: '20px 20px 40px',
          display: 'flex',
          flexDirection: 'column',
          gap: 28,
        }}
      >
        {/* 1. KPI row */}
        <div
          className="card-elev"
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 16,
            padding: '18px 18px',
          }}
        >
          <StatTile
            label="Fitness"
            value={
              <span style={{ fontVariantNumeric: 'tabular-nums' }}>
                {ctl != null ? Math.round(ctl) : '--'}
              </span>
            }
            delta={
              delta != null
                ? `${delta >= 0 ? '+' : ''}${Math.round(delta)} vs 28d ago`
                : undefined
            }
            tone={ctlTone}
          />
          <StatTile
            label="Form"
            value={
              <span style={{ color: tsbClass ? `var(--color-${tsbClass.tone === 'up' ? 'good' : tsbClass.tone === 'down' ? 'bad' : 'ink'})` : 'var(--color-ink)' }}>
                {tsb != null ? `${tsb >= 0 ? '+' : ''}${Math.round(tsb)}` : '--'}
              </span>
            }
            delta={tsbClass?.label}
            tone={tsbClass?.tone ?? 'flat'}
          />
          <StatTile
            label="This week"
            value={<span style={{ fontVariantNumeric: 'tabular-nums' }}>{weekTss}</span>}
            unit="TSS"
            delta={weekRides.length > 0 ? `${weekRides.length} ride${weekRides.length === 1 ? '' : 's'}` : 'No rides yet'}
            tone="flat"
          />
        </div>

        {/* 2. Fitness trend */}
        <PmcChart history={pmcHistory} />

        {/* 3. Weekly load */}
        <WeeklyLoadChart rides={rides} />

        {/* 4. Ride log */}
        <div>
          <SectionLabel>Ride log</SectionLabel>

          {/* Compact upload affordance (secondary, not the hero). */}
          <div style={{ marginBottom: 16 }}>
            <FitUploadZone />
          </div>

          {ridesQuery.isLoading && (
            <>
              <SkeletonRow />
              <SkeletonRow />
              <SkeletonRow />
            </>
          )}

          {ridesQuery.isError && (
            <button
              onClick={() => ridesQuery.refetch()}
              style={{
                display: 'block',
                width: '100%',
                padding: '12px',
                textAlign: 'center',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--color-bad)',
                fontSize: '14px',
              }}
            >
              Could not load history. Tap to retry.
            </button>
          )}

          {!ridesQuery.isLoading && !ridesQuery.isError && rides.length === 0 && (
            <div style={{ textAlign: 'center', paddingTop: 24 }}>
              <h2
                style={{
                  fontSize: '18px',
                  fontWeight: 600,
                  color: 'var(--color-ink)',
                  margin: '0 0 8px',
                }}
              >
                No rides yet
              </h2>
              <p
                style={{
                  fontSize: '15px',
                  color: 'var(--color-ink-2)',
                  margin: 0,
                  lineHeight: '1.5',
                }}
              >
                Upload a .FIT file from Zwift or your head unit to see your history.
              </p>
            </div>
          )}

          {!ridesQuery.isLoading &&
            !ridesQuery.isError &&
            grouped.map((group) => (
              <div key={group.key} style={{ marginBottom: 12 }}>
                <div
                  style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: 'var(--color-ink-2)',
                    margin: '4px 0 2px',
                  }}
                >
                  {group.label}
                </div>
                {group.rides.map((ride) => (
                  <RideRow key={ride.id} ride={ride} />
                ))}
              </div>
            ))}
        </div>

        {/* 5. Adaptations */}
        <div>
          <SectionLabel>Adaptations</SectionLabel>

          {adaptationsQuery.isLoading && (
            <>
              <SkeletonRow />
              <SkeletonRow />
            </>
          )}

          {adaptationsQuery.isError && (
            <button
              onClick={() => adaptationsQuery.refetch()}
              style={{
                display: 'block',
                width: '100%',
                padding: '12px',
                textAlign: 'center',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                color: 'var(--color-bad)',
                fontSize: '14px',
              }}
            >
              Could not load adaptations. Tap to retry.
            </button>
          )}

          {!adaptationsQuery.isLoading && !adaptationsQuery.isError && adaptations.length === 0 && (
            <p
              style={{
                fontSize: 15,
                color: 'var(--color-ink-2)',
                textAlign: 'center',
                lineHeight: 1.5,
                paddingTop: 24,
                margin: 0,
              }}
            >
              No adaptations yet. Your plan hasn't needed adjustment.
            </p>
          )}

          {!adaptationsQuery.isLoading &&
            !adaptationsQuery.isError &&
            adaptations.map((a) => (
              <div
                key={a.id}
                style={{ borderBottom: '1px solid var(--color-line)', padding: '12px 0' }}
              >
                <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ink)' }}>
                  {triggerLabel(a?.trigger)}
                </div>
                <p style={{ fontSize: 13, color: 'var(--color-ink-2)', margin: '2px 0', lineHeight: 1.5 }}>
                  {a?.explanation_text ?? ''}
                </p>
                <span style={{ fontSize: 12, color: 'var(--color-ink-3)' }}>
                  {a?.created_at ? formatDate(a.created_at) : ''}
                </span>
              </div>
            ))}
        </div>
      </div>
    </div>
  )
}
