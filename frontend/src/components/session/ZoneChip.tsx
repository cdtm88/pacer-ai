// ZoneChip: renders a colored badge using the --color-zone-* CSS custom properties.
// Single source of truth — no inline hex values. Zone color/label metadata is
// sourced from lib/zones (D-8 component unification); this file no longer
// maintains its own copy of the zone map.

import { zoneColor, zoneLabel, type ZoneKey } from '@/lib/zones'

// Preserve the public ZoneType export so RideChart.tsx's
// `import { ZoneChip, type ZoneType }` keeps compiling unchanged.
export type ZoneType = ZoneKey

interface ZoneChipProps {
  zone: ZoneType
  label?: string
}

export function ZoneChip({ zone, label }: ZoneChipProps) {
  const color = zoneColor(zone)

  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
      style={{
        // Background: zone color at ~15% opacity using color-mix
        backgroundColor: `color-mix(in srgb, ${color} 15%, transparent)`,
        // Text: zone color (dark enough for readability against the tinted bg)
        color,
        fontSize: 12,
        fontWeight: 500,
        lineHeight: 1.4,
      }}
    >
      {label ?? zoneLabel(zone)}
    </span>
  )
}
