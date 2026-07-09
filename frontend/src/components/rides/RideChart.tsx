import { useState, useCallback, useEffect } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from 'recharts'
import { ZoneChip, type ZoneType } from '../session/ZoneChip'
import type { RideStream, RideStreamPoint, RideZoneDistribution } from '../../lib/api'

// ---------------------------------------------------------------------------
// RideChart — the deep-dive per-ride visualization (RIDE-07/08/09).
//   One line chart per PRESENT channel, synced by Recharts syncId so hovering
//   any chart moves a shared readout row (time / lap / per-channel values).
//   A time-in-zone section renders only when the backend has computed a
//   hr_zone_distribution (requires heart_rate channel + user LTHR). No zone
//   maths happens here — every zone boundary/percentage is backend-sourced
//   (TRUST-01).
// ---------------------------------------------------------------------------

const AXIS_TICK = { fontSize: 11, fill: 'var(--color-ink-3)', fontVariantNumeric: 'tabular-nums' as const }

type ChannelKey = 'power' | 'heart_rate' | 'cadence' | 'speed' | 'altitude'

interface ChartConfigEntry {
  key: ChannelKey
  title: string
  color: string
  unitLabel: string
}

const CHART_CONFIG: ChartConfigEntry[] = [
  { key: 'power', title: 'Power', color: 'var(--color-zone-endurance)', unitLabel: 'POWER' },
  { key: 'heart_rate', title: 'Heart rate', color: 'var(--color-warm)', unitLabel: 'HR' },
  { key: 'cadence', title: 'Cadence', color: 'var(--color-ink-3)', unitLabel: 'CAD' },
  { key: 'speed', title: 'Speed', color: 'var(--color-blue-4)', unitLabel: 'SPEED' },
  { key: 'altitude', title: 'Elevation', color: 'var(--color-good)', unitLabel: 'ELEV' },
]

const ZONE_ORDER: ZoneType[] = ['recovery', 'endurance', 'tempo', 'threshold', 'vo2']

// New formatter, deliberately distinct from DuringSessionScreen's MM:SS colon
// timer (RIDE-08 specifies the letter format explicitly, not a reuse case).
function formatRideTime(seconds: number): string {
  const s = Math.max(0, Math.round(seconds))
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${m}m ${rem}s`
}

function formatChannelValue(key: ChannelKey | 'distance', value: number | null): string {
  if (value == null) return '--'
  switch (key) {
    case 'power':
      return `${Math.round(value)} W`
    case 'heart_rate':
      return `${Math.round(value)} bpm`
    case 'cadence':
      return `${Math.round(value)} rpm`
    case 'speed':
      return `${value.toFixed(1)} km/h`
    case 'altitude':
      return `${Math.round(value)} m`
    case 'distance':
      return `${(value / 1000).toFixed(2)} km`
    default:
      return String(value)
  }
}

interface SyncedTooltipProps {
  active?: boolean
  payload?: { payload: RideStreamPoint }[]
  onHover: (point: RideStreamPoint) => void
}

// Renders nothing visually -- the shared readout row (not a floating box) is
// the actual UI. This component's only job is to drive that row from
// Recharts' synced hover state, mirroring PmcChart's payload-driven pattern.
function SyncedTooltip({ active, payload, onHover }: SyncedTooltipProps) {
  useEffect(() => {
    if (active && payload && payload.length > 0) {
      onHover(payload[0].payload)
    }
  }, [active, payload, onHover])
  return null
}

interface RideChartProps {
  stream: RideStream
}

const EMPTY_POINT: RideStreamPoint = {
  t: 0,
  power: null,
  heart_rate: null,
  cadence: null,
  speed: null,
  altitude: null,
  distance: null,
}

export function RideChart({ stream }: RideChartProps) {
  const [hovered, setHovered] = useState<RideStreamPoint>(stream.series[0] ?? EMPTY_POINT)

  const handleHover = useCallback((point: RideStreamPoint) => setHovered(point), [])

  // Lap N is 1-indexed: the count of lap boundaries at or before the hovered point, plus one.
  let lapNumber = 1
  for (const lapT of stream.laps) {
    if (hovered.t >= lapT) lapNumber += 1
  }

  const presentCharts = CHART_CONFIG.filter((c) => stream.channels[c.key])

  return (
    <div>
      {/* Synced readout row -- first element in the scroll flow, not sticky */}
      <div
        className="card-elev"
        style={{
          padding: '10px 12px',
          display: 'flex',
          flexWrap: 'wrap',
          alignItems: 'center',
          gap: 16,
        }}
      >
        <span
          style={{
            background: 'color-mix(in srgb, var(--color-brand) 10%, transparent)',
            color: 'var(--color-brand)',
            fontSize: 13,
            fontWeight: 600,
            borderRadius: 999,
            padding: '2px 10px',
          }}
        >
          {`Lap ${lapNumber}`}
        </span>
        <span className="stat-num" style={{ fontSize: 13, fontWeight: 400, color: 'var(--color-ink)' }}>
          {formatRideTime(hovered.t)}
        </span>
        {presentCharts.map((c) => (
          <div key={c.key} style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: 11, fontWeight: 400, color: c.color, textTransform: 'uppercase' }}>
              {c.unitLabel}
            </span>
            <span className="stat-num" style={{ fontSize: 13, fontWeight: 400, color: 'var(--color-ink)' }}>
              {formatChannelValue(c.key, hovered[c.key])}
            </span>
          </div>
        ))}
        {stream.channels.distance && (
          <div style={{ display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontSize: 11, fontWeight: 400, color: 'var(--color-ink-3)', textTransform: 'uppercase' }}>
              DIST
            </span>
            <span className="stat-num" style={{ fontSize: 13, fontWeight: 400, color: 'var(--color-ink)' }}>
              {formatChannelValue('distance', hovered.distance)}
            </span>
          </div>
        )}
      </div>

      {/* Chart stack -- one card-elev panel per PRESENT channel, no card for absent ones */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
        {presentCharts.map((c) => (
          <div key={c.key} className="card-elev" style={{ padding: '16px 12px 8px' }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-ink)', marginBottom: 4 }}>
              {c.title}
            </div>
            <div style={{ height: 200, width: '100%' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={stream.series} syncId="ride" margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
                  <CartesianGrid stroke="var(--color-line-2)" vertical={false} />
                  <XAxis
                    dataKey="t"
                    tick={AXIS_TICK}
                    tickLine={false}
                    axisLine={{ stroke: 'var(--color-line)' }}
                    tickFormatter={(s: number) => `${Math.round(s / 60)}m`}
                  />
                  <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={38} />
                  <Tooltip content={<SyncedTooltip onHover={handleHover} />} />
                  {stream.laps.map((t) => (
                    <ReferenceLine key={t} x={t} stroke="var(--color-line)" strokeDasharray="3 3" />
                  ))}
                  <Line
                    type="monotone"
                    dataKey={c.key}
                    stroke={c.color}
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        ))}
      </div>

      {/* Time in zone -- backend-sourced verbatim, no zone maths in TS (TRUST-01) */}
      {stream.hr_zone_distribution != null && (
        <div style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 18, fontWeight: 600, color: 'var(--color-ink)', marginBottom: 16 }}>
            Time in zone
          </h2>
          <div style={{ display: 'flex', height: 12, borderRadius: 6, overflow: 'hidden' }}>
            {stream.hr_zone_distribution.map((row: RideZoneDistribution, i: number) => {
              const zone = ZONE_ORDER[i]
              return (
                <div
                  key={row.zone}
                  style={{ width: `${row.pct}%`, background: `var(--color-zone-${zone})` }}
                />
              )
            })}
          </div>
          <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
            {stream.hr_zone_distribution.map((row: RideZoneDistribution, i: number) => {
              const zone = ZONE_ORDER[i]
              return (
                <div
                  key={row.zone}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}
                >
                  <ZoneChip zone={zone} />
                  <span className="stat-num" style={{ fontSize: 13, color: 'var(--color-ink-2)', textAlign: 'right' }}>
                    {`${formatRideTime(row.seconds)} · ${row.pct}%`}
                  </span>
                </div>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
