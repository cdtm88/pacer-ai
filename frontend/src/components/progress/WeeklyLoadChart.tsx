import {
  BarChart,
  Bar,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import type { Ride } from '../../lib/api'
import { weekStartOf, weekKey } from './week'

// ---------------------------------------------------------------------------
// WeeklyLoadChart — last ~8 ISO weeks of ride TSS, bucketed by week.
// History bars are neutral gray; the current ISO week is highlighted in
// brand blue. A faint ReferenceLine marks the average load across
// non-empty weeks.
// ---------------------------------------------------------------------------

const WEEKS = 8

const AXIS_TICK = { fontSize: 11, fill: 'var(--color-ink-3)', fontVariantNumeric: 'tabular-nums' as const }

interface WeekBucket {
  key: string
  label: string
  tss: number
}

function buildBuckets(rides: Ride[]): WeekBucket[] {
  // Sum TSS per ISO week.
  const totals = new Map<string, number>()
  for (const ride of rides) {
    if (ride.tss == null) continue
    const key = weekKey(ride.ride_date)
    totals.set(key, (totals.get(key) ?? 0) + ride.tss)
  }

  // Build a contiguous run of the last WEEKS weeks (including empty ones) so
  // gaps read as rest weeks rather than being silently collapsed.
  const buckets: WeekBucket[] = []
  const thisMonday = weekStartOf(new Date())
  for (let i = WEEKS - 1; i >= 0; i--) {
    const d = new Date(thisMonday)
    d.setDate(d.getDate() - i * 7)
    const key = weekKey(d.toISOString())
    buckets.push({
      key,
      label: d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }),
      tss: Math.round(totals.get(key) ?? 0),
    })
  }
  return buckets
}

function WeekTooltip({ active, payload }: {
  active?: boolean
  payload?: { payload: WeekBucket }[]
}) {
  if (!active || !payload || payload.length === 0) return null
  const b = payload[0].payload
  return (
    <div className="card-elev" style={{ padding: '8px 10px', fontSize: 12 }}>
      <div style={{ fontWeight: 600, color: 'var(--color-ink)' }}>Week of {b.label}</div>
      <div style={{ color: 'var(--color-ink-2)', marginTop: 2 }}>
        <span className="stat-num" style={{ color: 'var(--color-ink)', fontWeight: 600 }}>
          {b.tss}
        </span>{' '}
        TSS
      </div>
    </div>
  )
}

interface WeeklyLoadChartProps {
  rides: Ride[]
}

export function WeeklyLoadChart({ rides }: WeeklyLoadChartProps) {
  const buckets = buildBuckets(rides)
  const nonZero = buckets.filter((b) => b.tss > 0)

  if (nonZero.length === 0) return null

  const avg = Math.round(nonZero.reduce((s, b) => s + b.tss, 0) / nonZero.length)
  const currentWeekKey = weekKey(weekStartOf(new Date()).toISOString())

  return (
    <div className="card-elev" style={{ padding: '16px 12px 12px' }}>
      <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ink)', margin: '0 0 8px', paddingLeft: 6 }}>
        Weekly load
      </h3>
      <div style={{ height: 180, width: '100%' }} aria-label="Weekly training load in TSS">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={buckets} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
            <CartesianGrid stroke="var(--color-line-2)" vertical={false} />
            <XAxis
              dataKey="label"
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-line)' }}
            />
            <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={40} allowDecimals={false} />
            <Tooltip content={<WeekTooltip />} cursor={{ fill: 'var(--color-bg-2)' }} />
            {avg > 0 && (
              <ReferenceLine
                y={avg}
                stroke="var(--color-ink-3)"
                strokeDasharray="4 4"
                label={{ value: `avg ${avg}`, position: 'insideTopRight', fontSize: 10, fill: 'var(--color-ink-3)' }}
              />
            )}
            <Bar dataKey="tss" radius={[4, 4, 0, 0]} isAnimationActive={false} maxBarSize={40}>
              {buckets.map((b) => {
                const isCurrentWeek = b.key === currentWeekKey
                return (
                  <Cell
                    key={b.key}
                    fill={isCurrentWeek ? 'var(--color-brand)' : 'var(--color-ink-3)'}
                  />
                )
              })}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
