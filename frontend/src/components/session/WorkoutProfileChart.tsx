import { zoneColor } from '@/lib/format'

// A segment of the workout in the order it is ridden.
export interface ProfileSegment {
  role: 'warmup' | 'main_set' | 'cooldown'
  duration_minutes: number
  description?: string
}

// Structured workout shape (matches SessionStructure in api.ts). A string
// structure carries no per-segment timing, so this component renders nothing.
interface StructureObj {
  warmup?: { duration_minutes?: number; description?: string }
  main_set?: { duration_minutes?: number; description?: string }
  cooldown?: { duration_minutes?: number; description?: string }
}

interface WorkoutProfileChartProps {
  structure: StructureObj | { text?: string } | string | null | undefined
  /** Session type drives the main-set block color via zoneColor(). */
  type: string | null
  /** Bar-row height in px. Defaults to 34 (compact); Today hub passes 56-64 (centerpiece). */
  height?: number
}

const ROLE_ORDER: ProfileSegment['role'][] = ['warmup', 'main_set', 'cooldown']

const ROLE_LABEL: Record<ProfileSegment['role'], string> = {
  warmup: 'Warm up',
  main_set: 'Main set',
  cooldown: 'Cool down',
}

// Extract ordered, positive-duration segments from a structured workout.
// Returns [] for string structures or {text} blobs (no segment timing available).
function toSegments(
  structure: WorkoutProfileChartProps['structure'],
): ProfileSegment[] {
  if (!structure || typeof structure === 'string') return []
  if ('text' in structure && !('warmup' in structure || 'main_set' in structure || 'cooldown' in structure)) {
    return []
  }
  const obj = structure as StructureObj
  const segments: ProfileSegment[] = []
  for (const role of ROLE_ORDER) {
    const seg = obj[role]
    const mins = seg?.duration_minutes
    if (seg && typeof mins === 'number' && mins > 0) {
      segments.push({ role, duration_minutes: mins, description: seg.description })
    }
  }
  return segments
}

/**
 * Compact horizontal workout-structure profile: one color-coded block per
 * segment, width proportional to duration. Warmup and cooldown read as
 * recovery green; the main set takes the session's zone color. Light mode only.
 * Renders nothing when the structure lacks per-segment timing.
 */
export function WorkoutProfileChart({ structure, type, height = 34 }: WorkoutProfileChartProps) {
  const segments = toSegments(structure)
  if (segments.length === 0) return null

  const total = segments.reduce((sum, s) => sum + s.duration_minutes, 0)
  if (total <= 0) return null

  const mainColor = zoneColor(type)
  const recoveryColor = 'var(--color-zone-recovery)'

  return (
    <div className="mb-3">
      <div
        className="flex w-full overflow-hidden"
        style={{ height, borderRadius: 8, gap: 2 }}
        role="img"
        aria-label={`Workout profile: ${segments
          .map((s) => `${ROLE_LABEL[s.role]} ${s.duration_minutes} min`)
          .join(', ')}`}
      >
        {segments.map((s, i) => {
          const isMain = s.role === 'main_set'
          const color = isMain ? mainColor : recoveryColor
          const pct = (s.duration_minutes / total) * 100
          return (
            <div
              key={`${s.role}-${i}`}
              className="flex items-center justify-center"
              style={{
                flexBasis: `${pct}%`,
                flexGrow: s.duration_minutes,
                minWidth: 18,
                backgroundColor: isMain
                  ? color
                  : `color-mix(in srgb, ${color} 22%, var(--color-surface))`,
                border: isMain ? 'none' : `1px solid color-mix(in srgb, ${color} 45%, transparent)`,
              }}
              title={`${ROLE_LABEL[s.role]} · ${s.duration_minutes} min`}
            >
              {pct >= 16 && (
                <span
                  className="stat-num"
                  style={{
                    fontSize: 11,
                    fontWeight: 700,
                    color: isMain ? '#fff' : 'var(--color-ink-2)',
                    fontVariantNumeric: 'tabular-nums',
                  }}
                >
                  {s.duration_minutes}
                </span>
              )}
            </div>
          )
        })}
      </div>
      {/* Segment legend */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-2">
        {segments.map((s, i) => {
          const isMain = s.role === 'main_set'
          const swatch = isMain ? mainColor : recoveryColor
          return (
            <span
              key={`legend-${s.role}-${i}`}
              className="inline-flex items-center gap-1.5"
              style={{ fontSize: 11, color: 'var(--color-ink-3)' }}
            >
              <span
                aria-hidden
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: 2,
                  backgroundColor: swatch,
                  display: 'inline-block',
                }}
              />
              {ROLE_LABEL[s.role]}
            </span>
          )
        })}
      </div>
    </div>
  )
}
