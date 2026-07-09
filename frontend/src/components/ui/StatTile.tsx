import type { ReactNode } from 'react'

export interface StatTileProps {
  /** Uppercase micro-label above the value. */
  label: string
  /** Big numeric readout. Pass a colored node for form/zone values. */
  value: ReactNode
  /** Optional small unit rendered next to the value (e.g. "W", "TSS"). */
  unit?: string
  /** Optional delta line (e.g. "+4 vs last week"). */
  delta?: string
  /** Direction of the delta: up (good/green), down (bad/red), flat (neutral). */
  tone?: 'up' | 'down' | 'flat'
}

const DELTA_COLOR: Record<NonNullable<StatTileProps['tone']>, string> = {
  up: 'var(--color-zone-recovery)',
  down: 'var(--color-bad)',
  flat: 'var(--color-ink-3)',
}

/**
 * Compact KPI tile: uppercase micro-label, a large tabular-figures value with an
 * optional unit, and an optional tone-colored delta line. Light mode only.
 */
export function StatTile({ label, value, unit, delta, tone = 'flat' }: StatTileProps) {
  return (
    <div className="flex flex-col gap-1">
      <span
        style={{
          fontSize: 11,
          fontWeight: 600,
          letterSpacing: '0.06em',
          textTransform: 'uppercase',
          color: 'var(--color-ink-3)',
        }}
      >
        {label}
      </span>
      <div className="flex items-baseline gap-1">
        <span
          className="stat-num"
          style={{
            fontSize: 'clamp(34px, 8vw, 52px)',
            lineHeight: 1,
            color: 'var(--color-ink)',
          }}
        >
          {value}
        </span>
        {unit && (
          <span
            style={{ fontSize: 15, fontWeight: 600, color: 'var(--color-ink-3)' }}
          >
            {unit}
          </span>
        )}
      </div>
      {delta && (
        <span
          className="stat-num"
          style={{ fontSize: 12, fontWeight: 600, color: DELTA_COLOR[tone] }}
        >
          {delta}
        </span>
      )}
    </div>
  )
}
