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
