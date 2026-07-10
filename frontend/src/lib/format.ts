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

/** Canonical display labels for adaptation triggers (D-09 humanization contract). */
const TRIGGER_LABELS: Record<string, string> = {
  missed: 'Missed session',
  underperformance: 'Underperformance',
  overreaching: 'Overreaching',
}

/** Display label for an adaptation trigger, falling back to title-case then "Adaptation". */
export function triggerLabel(trigger: string | null | undefined): string {
  if (!trigger) return 'Adaptation'
  return TRIGGER_LABELS[trigger] ?? titleCase(trigger)
}

/**
 * Shared date formatter (extracted from RideRow so the Adaptations log and
 * Ride log render byte-identical date strings, per D-09). Returns the raw
 * input, rather than "Invalid Date", when the string cannot be parsed.
 */
export function formatDate(isoDate: string): string {
  try {
    const date = new Date(isoDate)
    if (isNaN(date.getTime())) return isoDate
    return date.toLocaleDateString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return isoDate
  }
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
