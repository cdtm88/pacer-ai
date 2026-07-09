// Zone metadata: single source of truth for zone color + label + % range.
// Percentages are of FTP (Coggan 7-zone collapsed to the 5 PacerAI zones).
//
// This module is the canonical import target every downstream screen should
// point at instead of maintaining a local zone map. lib/format.ts re-exports
// these symbols so existing consumers (SessionCard.tsx, WorkoutProfileChart.tsx)
// keep working unchanged.

export type ZoneKey = 'recovery' | 'endurance' | 'tempo' | 'threshold' | 'vo2'

export interface ZoneMeta {
  color: string
  label: string
  pctLow: number
  pctHigh: number | null
}

/** Zone metadata keyed by zone type; color values are CSS design tokens. */
export const ZONE_META: Record<ZoneKey, ZoneMeta> = {
  recovery: { color: 'var(--color-zone-recovery)', label: 'Recovery', pctLow: 0, pctHigh: 55 },
  endurance: { color: 'var(--color-zone-endurance)', label: 'Endurance', pctLow: 56, pctHigh: 75 },
  tempo: { color: 'var(--color-zone-tempo)', label: 'Tempo', pctLow: 76, pctHigh: 90 },
  threshold: { color: 'var(--color-zone-threshold)', label: 'Threshold', pctLow: 91, pctHigh: 105 },
  vo2: { color: 'var(--color-zone-vo2)', label: 'VO2 Max', pctLow: 106, pctHigh: null },
}

/** CSS color token for a zone type, or a neutral fallback for unknown values. */
export function zoneColor(type: string | null): string {
  if (type && type in ZONE_META) return ZONE_META[type as ZoneKey].color
  return 'var(--color-ink-3)'
}

/** Canonical display label for a zone type, or empty string for null/unknown. */
export function zoneLabel(type: string | null): string {
  if (type && type in ZONE_META) return ZONE_META[type as ZoneKey].label
  return ''
}

/**
 * Thin zone-spectrum gradient rule: recovery -> endurance -> tempo -> threshold -> vo2.
 * The app-wide brand mark (LoginScreen wordmark, DesktopSidebar sidebar logotype).
 */
export const ZONE_SPECTRUM =
  'linear-gradient(90deg, var(--color-zone-recovery), var(--color-zone-endurance), var(--color-zone-tempo), var(--color-zone-threshold), var(--color-zone-vo2))'
