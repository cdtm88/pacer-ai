// Shared display formatters.

/**
 * Title-case a session type / zone label for display.
 * "tempo" -> "Tempo", "vo2" -> "VO2 Max" handled by ZONE_LABELS below.
 */
export function titleCase(value: string | null | undefined): string {
  if (!value) return ''
  return value.charAt(0).toUpperCase() + value.slice(1)
}

/** Canonical display labels for training zones / session types. */
const ZONE_LABELS: Record<string, string> = {
  recovery: 'Recovery',
  endurance: 'Endurance',
  tempo: 'Tempo',
  threshold: 'Threshold',
  vo2: 'VO2 Max',
}

/** Display label for a session type, falling back to title-case then "Session". */
export function sessionTypeLabel(type: string | null | undefined): string {
  if (!type) return 'Session'
  return ZONE_LABELS[type] ?? titleCase(type)
}

// ---------------------------------------------------------------------------
// Zone metadata: single source of truth for zone color + label + % range.
// Percentages are of FTP (Coggan 7-zone collapsed to the 5 PacerAI zones).
// ---------------------------------------------------------------------------

export type ZoneKey = 'recovery' | 'endurance' | 'tempo' | 'threshold' | 'vo2'

export interface ZoneMeta {
  color: string
  label: string
  pctLow: number
  pctHigh: number
}

/** Zone metadata keyed by zone type; color values are CSS design tokens. */
export const ZONE_META: Record<ZoneKey, ZoneMeta> = {
  recovery: { color: 'var(--color-zone-recovery)', label: 'Recovery', pctLow: 0, pctHigh: 55 },
  endurance: { color: 'var(--color-zone-endurance)', label: 'Endurance', pctLow: 56, pctHigh: 75 },
  tempo: { color: 'var(--color-zone-tempo)', label: 'Tempo', pctLow: 76, pctHigh: 90 },
  threshold: { color: 'var(--color-zone-threshold)', label: 'Threshold', pctLow: 91, pctHigh: 105 },
  vo2: { color: 'var(--color-zone-vo2)', label: 'VO2 Max', pctLow: 106, pctHigh: 120 },
}

/** CSS color token for a zone type, or a neutral fallback for unknown values. */
export function zoneColor(type: string | null): string {
  if (type && type in ZONE_META) return ZONE_META[type as ZoneKey].color
  return 'var(--color-ink-3)'
}

// ---------------------------------------------------------------------------
// TSB (form) classification. Thresholds: >5 fresh, <-10 fatigued, else balanced.
// ---------------------------------------------------------------------------

export interface TsbClass {
  key: 'fresh' | 'balanced' | 'fatigued'
  label: string
  tone: 'up' | 'flat' | 'down'
}

/** Classify a TSB (form) value into fresh / balanced / fatigued. */
export function classifyTsb(tsb: number): TsbClass {
  if (tsb > 5) return { key: 'fresh', label: 'Fresh', tone: 'up' }
  if (tsb < -10) return { key: 'fatigued', label: 'Fatigued', tone: 'down' }
  return { key: 'balanced', label: 'Balanced', tone: 'flat' }
}
