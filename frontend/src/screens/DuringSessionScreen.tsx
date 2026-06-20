// DuringSessionScreen: static during-session layout.
// Phase 4: no timer behavior (D-09). Phase 5 wires the real timer and step advance.

import { useNavigate } from 'react-router'
import { Button } from '@/components/ui/button'
import { SessionStepList } from '@/components/session/SessionStepList'
import type { SessionStep } from '@/components/session/SessionStepList'

// Representative placeholder steps so the layout is verifiable in Phase 4.
const PLACEHOLDER_STEPS: SessionStep[] = [
  { label: 'Zone 2, 20 min', duration: 20, zone: 'endurance' },
  { label: 'Zone 3 Tempo, 10 min', duration: 10, zone: 'tempo' },
  { label: 'Cool-down, 5 min', duration: 5, zone: 'recovery' },
]

export function DuringSessionScreen() {
  const navigate = useNavigate()

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: 'var(--color-bg-2)' }}
    >
      {/* Step hierarchy */}
      <div className="flex-1 flex flex-col justify-center px-6 pt-12 pb-6">
        <SessionStepList steps={PLACEHOLDER_STEPS} currentIndex={0} />

        {/* Static timer */}
        <div className="mt-10">
          <p
            style={{
              fontSize: 32,
              fontWeight: 700,
              color: 'var(--color-ink)',
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: '0.05em',
            }}
          >
            00:00
          </p>
          <p
            style={{
              fontSize: 14,
              color: 'var(--color-ink-3)',
              marginTop: 4,
            }}
          >
            Timer activates in next phase
          </p>
        </div>
      </div>

      {/* End session: bottom-right, outline variant, --color-bad text */}
      <div className="flex justify-end px-6 pb-8">
        <Button
          variant="outline"
          style={{ color: 'var(--color-bad)', borderColor: 'var(--color-bad)' }}
          onClick={() => navigate('/')}
        >
          End session
        </Button>
      </div>
    </div>
  )
}
