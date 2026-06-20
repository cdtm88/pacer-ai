// ZoneChip: renders a colored badge using the --color-zone-* CSS custom properties.
// Single source of truth — no inline hex values.

export type ZoneType = 'recovery' | 'endurance' | 'tempo' | 'threshold' | 'vo2'

// Map zone type to the CSS custom property name
const ZONE_VAR: Record<ZoneType, string> = {
  recovery:  '--color-zone-recovery',
  endurance: '--color-zone-endurance',
  tempo:     '--color-zone-tempo',
  threshold: '--color-zone-threshold',
  vo2:       '--color-zone-vo2',
}

const ZONE_LABEL: Record<ZoneType, string> = {
  recovery:  'Recovery',
  endurance: 'Endurance',
  tempo:     'Tempo',
  threshold: 'Threshold',
  vo2:       'VO2max',
}

interface ZoneChipProps {
  zone: ZoneType
  label?: string
}

export function ZoneChip({ zone, label }: ZoneChipProps) {
  const cssVar = ZONE_VAR[zone]

  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
      style={{
        // Background: zone color at ~15% opacity using color-mix
        backgroundColor: `color-mix(in srgb, var(${cssVar}) 15%, transparent)`,
        // Text: zone color (dark enough for readability against the tinted bg)
        color: `var(${cssVar})`,
        fontSize: 12,
        fontWeight: 500,
        lineHeight: 1.4,
      }}
    >
      {label ?? ZONE_LABEL[zone]}
    </span>
  )
}
