// SessionStepList: renders the static during-session step hierarchy.
// Phase 4 only: no ticking, no auto-advance — Phase 5 wires behavior.

import type { ZoneType } from './ZoneChip'

export interface SessionStep {
  label: string        // e.g. "Zone 2, 20 min"
  duration: number     // minutes
  zone?: ZoneType
}

const ZONE_VAR: Record<ZoneType, string> = {
  recovery:  '--color-zone-recovery',
  endurance: '--color-zone-endurance',
  tempo:     '--color-zone-tempo',
  threshold: '--color-zone-threshold',
  vo2:       '--color-zone-vo2',
}

interface SessionStepListProps {
  steps: SessionStep[]
  currentIndex?: number
}

export function SessionStepList({ steps, currentIndex = 0 }: SessionStepListProps) {
  const current = steps[currentIndex]
  const next = steps[currentIndex + 1]
  const remaining = steps.slice(currentIndex + 2, currentIndex + 5)

  if (!current) return null

  const zoneColor = current.zone ? `var(${ZONE_VAR[current.zone]})` : 'var(--color-blue-6)'

  return (
    <div className="flex flex-col gap-3 w-full">
      {/* Current step: Display 40px bold */}
      <div>
        <p
          style={{
            fontSize: 40,
            fontWeight: 700,
            color: 'var(--color-ink)',
            lineHeight: 1.1,
            letterSpacing: '-0.02em',
          }}
        >
          {current.label}
        </p>
        {/* 4px zone-color horizontal strip */}
        <div
          style={{
            height: 4,
            borderRadius: 2,
            backgroundColor: zoneColor,
            marginTop: 8,
            width: '100%',
          }}
        />
      </div>

      {/* Next step: Heading 20px semibold */}
      {next && (
        <p
          style={{
            fontSize: 20,
            fontWeight: 600,
            color: 'var(--color-ink-2)',
            lineHeight: 1.3,
          }}
        >
          Next: {next.label}
        </p>
      )}

      {/* Remaining steps: Body 16px */}
      {remaining.length > 0 && (
        <div className="flex flex-col gap-1">
          {remaining.map((step, i) => (
            <p
              key={i}
              style={{
                fontSize: 16,
                color: 'var(--color-ink-3)',
                lineHeight: 1.4,
              }}
            >
              {step.label}
            </p>
          ))}
        </div>
      )}
    </div>
  )
}
