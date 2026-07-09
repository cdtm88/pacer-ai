import { useState } from 'react'
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import type { PmcEntry } from '../../lib/api'

// ---------------------------------------------------------------------------
// PmcChart — the "am I getting fitter?" trend.
//   CTL (fitness)  -> filled Area, endurance blue, left axis
//   ATL (fatigue)  -> thin Line, tempo amber, left axis
//   TSB (form)     -> Line on the right axis with a ReferenceLine at y=0
//
// Time-range toggle (6w / 3m / All) slices the ascending series by date.
// Gate: if the series is empty or no row is tss_display_ready, we show a
// friendly "trend appears after ~4 weeks" empty state instead of a chart.
// ---------------------------------------------------------------------------

type Range = '6w' | '3m' | 'all'

const RANGE_DAYS: Record<Range, number | null> = {
  '6w': 42,
  '3m': 90,
  all: null,
}

const RANGE_LABEL: Record<Range, string> = {
  '6w': '6w',
  '3m': '3m',
  all: 'All',
}

const AXIS_TICK = { fontSize: 11, fill: 'var(--color-ink-3)', fontVariantNumeric: 'tabular-nums' as const }

function formatTick(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  } catch {
    return iso
  }
}

function PmcTooltip({ active, payload, label }: {
  active?: boolean
  payload?: { dataKey: string; value: number; color: string }[]
  label?: string
}) {
  if (!active || !payload || payload.length === 0) return null
  const byKey: Record<string, number> = {}
  for (const p of payload) byKey[p.dataKey] = p.value
  const rows: { key: string; name: string; color: string }[] = [
    { key: 'ctl', name: 'Fitness', color: 'var(--color-zone-endurance)' },
    { key: 'atl', name: 'Fatigue', color: 'var(--color-zone-tempo)' },
    { key: 'tsb', name: 'Form', color: 'var(--color-ink-2)' },
  ]
  return (
    <div
      className="card-elev"
      style={{ padding: '8px 10px', fontSize: 12, minWidth: 128 }}
    >
      <div style={{ fontWeight: 600, color: 'var(--color-ink)', marginBottom: 4 }}>
        {label ? formatTick(label) : ''}
      </div>
      {rows.map((r) => (
        <div
          key={r.key}
          style={{ display: 'flex', justifyContent: 'space-between', gap: 12, color: 'var(--color-ink-2)' }}
        >
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: 2, background: r.color }} />
            {r.name}
          </span>
          <span className="stat-num" style={{ color: 'var(--color-ink)', fontWeight: 600 }}>
            {byKey[r.key] != null ? Math.round(byKey[r.key]) : '--'}
          </span>
        </div>
      ))}
    </div>
  )
}

interface PmcChartProps {
  history: PmcEntry[]
}

export function PmcChart({ history }: PmcChartProps) {
  const [range, setRange] = useState<Range>('3m')

  const hasReady = history.some((h) => h.tss_display_ready)

  if (history.length === 0 || !hasReady) {
    return (
      <div
        className="card-elev"
        style={{
          padding: '32px 20px',
          textAlign: 'center',
          color: 'var(--color-ink-2)',
        }}
      >
        <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-ink)', marginBottom: 6 }}>
          Your fitness trend is building
        </div>
        <div style={{ fontSize: 14, lineHeight: 1.5 }}>
          The trend chart appears after about 4 weeks of rides, once there is
          enough data to show a stable line.
        </div>
      </div>
    )
  }

  // Slice by date relative to the most recent entry (series is ascending).
  const days = RANGE_DAYS[range]
  let data = history
  if (days != null && history.length > 0) {
    const lastDate = new Date(history[history.length - 1].date).getTime()
    const cutoff = lastDate - days * 86_400_000
    data = history.filter((h) => new Date(h.date).getTime() >= cutoff)
  }

  return (
    <div className="card-elev" style={{ padding: '16px 12px 8px' }}>
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 6px 8px',
        }}
      >
        <h3 style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ink)', margin: 0 }}>
          Fitness trend
        </h3>
        <div style={{ display: 'flex', gap: 4 }} role="group" aria-label="Time range">
          {(Object.keys(RANGE_LABEL) as Range[]).map((r) => {
            const active = r === range
            return (
              <button
                key={r}
                onClick={() => setRange(r)}
                aria-pressed={active}
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  padding: '4px 10px',
                  borderRadius: 999,
                  border: '1px solid',
                  borderColor: active ? 'var(--color-brand)' : 'var(--color-line)',
                  background: active ? 'var(--color-brand)' : 'var(--color-surface)',
                  color: active ? 'var(--color-surface)' : 'var(--color-ink-2)',
                  cursor: 'pointer',
                }}
              >
                {RANGE_LABEL[r]}
              </button>
            )
          })}
        </div>
      </div>

      <div style={{ height: 240, width: '100%' }} aria-label="Fitness, fatigue and form trend chart">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="ctlFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="var(--color-zone-endurance)" stopOpacity={0.22} />
                <stop offset="100%" stopColor="var(--color-zone-endurance)" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--color-line-2)" vertical={false} />
            <XAxis
              dataKey="date"
              tickFormatter={formatTick}
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-line)' }}
              minTickGap={28}
            />
            <YAxis
              yAxisId="load"
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              width={38}
            />
            <YAxis
              yAxisId="form"
              orientation="right"
              tick={AXIS_TICK}
              tickLine={false}
              axisLine={false}
              width={30}
            />
            <Tooltip content={<PmcTooltip />} />
            <ReferenceLine yAxisId="form" y={0} stroke="var(--color-line)" strokeDasharray="3 3" />
            <Area
              yAxisId="load"
              type="monotone"
              dataKey="ctl"
              stroke="var(--color-zone-endurance)"
              strokeWidth={2}
              fill="url(#ctlFill)"
              isAnimationActive={false}
            />
            <Line
              yAxisId="load"
              type="monotone"
              dataKey="atl"
              stroke="var(--color-zone-tempo)"
              strokeWidth={1.5}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              yAxisId="form"
              type="monotone"
              dataKey="tsb"
              stroke="var(--color-ink-2)"
              strokeWidth={1.5}
              dot={false}
              strokeDasharray="4 3"
              isAnimationActive={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 16,
          padding: '8px 6px 4px',
          fontSize: 12,
          color: 'var(--color-ink-2)',
        }}
      >
        {[
          { name: 'Fitness (CTL)', color: 'var(--color-zone-endurance)' },
          { name: 'Fatigue (ATL)', color: 'var(--color-zone-tempo)' },
          { name: 'Form (TSB)', color: 'var(--color-ink-2)' },
        ].map((l) => (
          <span key={l.name} style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
            <span style={{ width: 10, height: 3, borderRadius: 2, background: l.color }} />
            {l.name}
          </span>
        ))}
      </div>
    </div>
  )
}
