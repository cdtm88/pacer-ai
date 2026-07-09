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
// Extracted to ./zones (D-8 unification); re-exported here so existing
// importers of lib/format.ts keep working unchanged.
// ---------------------------------------------------------------------------

export { ZONE_META, zoneColor, zoneLabel, type ZoneKey } from './zones'
export type { ZoneMeta } from './zones'

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
