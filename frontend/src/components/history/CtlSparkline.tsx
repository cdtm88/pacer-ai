import { LineChart, Line, ResponsiveContainer } from 'recharts'
import type { PmcEntry } from '../../lib/api'

// ---------------------------------------------------------------------------
// CtlSparkline — shows a simple CTL trend line above the ride list.
//
// D-14 gate: returns null unless the most recent pmc entry has
// tss_display_ready === true (requires 28+ days of data).
// When not shown: no placeholder, no empty space.
// ---------------------------------------------------------------------------

interface CtlSparklineProps {
  history: PmcEntry[]
}

export function CtlSparkline({ history }: CtlSparklineProps) {
  // D-14 gate: only show when the latest row indicates 28+ days of data
  if (!history || history.length === 0) return null

  const latest = history[history.length - 1]
  if (!latest.tss_display_ready) return null

  // Take up to 30 most recent days (already ascending from API)
  const window = history.slice(-30)
  const chartData = window.map((row) => ({ date: row.date, ctl: row.ctl }))

  return (
    <div
      style={{ height: '48px', width: '100%' }}
      aria-label="CTL fitness trend"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={chartData}>
          <Line
            type="monotone"
            dataKey="ctl"
            stroke="var(--color-blue-6)"
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
