import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { SessionStepList } from '@/components/session/SessionStepList'
import type { SessionStep } from '@/components/session/SessionStepList'
import { getSessionToday } from '@/lib/api'
import { useSessionTimer } from '@/hooks/useSessionTimer'
import { useWakeLock } from '@/hooks/useWakeLock'
import { useUiStore } from '@/stores/uiStore'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTimer(secondsLeft: number): string {
  const s = Math.max(0, secondsLeft)
  const mm = Math.floor(s / 60)
  const ss = s % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

type ZoneType = 'recovery' | 'endurance' | 'tempo' | 'threshold' | 'vo2'

function validZone(z: unknown): ZoneType {
  const valid: ZoneType[] = ['recovery', 'endurance', 'tempo', 'threshold', 'vo2']
  return valid.includes(z as ZoneType) ? (z as ZoneType) : 'endurance'
}

interface SessionStructure {
  warmup?: { duration_minutes?: number; description?: string }
  main_set?: { duration_minutes?: number; description?: string }
  cooldown?: { duration_minutes?: number; description?: string }
}

function parseSteps(structure: unknown, sessionType: string): SessionStep[] {
  if (!structure || typeof structure !== 'object') return []
  const s = structure as SessionStructure

  const steps: SessionStep[] = []

  if (s.warmup) {
    steps.push({
      label: s.warmup.description ?? 'Warm-up',
      duration: s.warmup.duration_minutes ?? 10,
      zone: 'recovery',
    })
  }
  if (s.main_set) {
    steps.push({
      label: s.main_set.description ?? 'Main set',
      duration: s.main_set.duration_minutes ?? 20,
      zone: validZone(sessionType),
    })
  }
  if (s.cooldown) {
    steps.push({
      label: s.cooldown.description ?? 'Cool-down',
      duration: s.cooldown.duration_minutes ?? 5,
      zone: 'recovery',
    })
  }

  return steps
}

function generateFreeRideSteps(totalMins: number): SessionStep[] {
  const MIN_SEG = 3
  const warmupRaw = Math.round(totalMins * 0.1)
  const cooldownRaw = Math.round(totalMins * 0.1)
  const warmup = Math.max(MIN_SEG, warmupRaw)
  const cooldown = Math.max(MIN_SEG, cooldownRaw)
  const main = Math.max(MIN_SEG, totalMins - warmup - cooldown)

  return [
    { label: 'Warm-up', duration: warmup, zone: 'recovery' },
    { label: 'Free ride', duration: main, zone: 'endurance' },
    { label: 'Cool-down', duration: cooldown, zone: 'recovery' },
  ]
}

// ---------------------------------------------------------------------------
// Inner component that owns timer state for a given step set
// ---------------------------------------------------------------------------

interface SessionRunnerProps {
  steps: SessionStep[]
}

function SessionRunner({ steps }: SessionRunnerProps) {
  const navigate = useNavigate()
  const [currentIndex, setCurrentIndex] = useState(0)
  const [completedDurationSecs, setCompletedDurationSecs] = useState(0)

  const isDone = currentIndex >= steps.length
  const currentStep = steps[currentIndex]
  const stepDuration = currentStep ? currentStep.duration * 60 : 0

  const { secondsLeft, advance } = useSessionTimer(stepDuration)

  // Advance to next step
  const goNext = useCallback(() => {
    if (currentIndex < steps.length) {
      setCompletedDurationSecs(prev => prev + steps[currentIndex].duration * 60)
      setCurrentIndex(prev => prev + 1)
    }
  }, [currentIndex, steps])

  // Reset timer when step changes
  useEffect(() => {
    advance()
  }, [currentIndex, advance])

  // Auto-advance when timer hits 0
  useEffect(() => {
    if (!isDone && secondsLeft === 0 && stepDuration > 0) {
      goNext()
    }
  }, [secondsLeft, isDone, stepDuration, goNext])

  if (isDone) {
    const totalSecs = completedDurationSecs
    const totalMins = Math.floor(totalSecs / 60)
    const totalHours = Math.floor(totalMins / 60)
    const remainMins = totalMins % 60
    const remainSecs = totalSecs % 60

    const timeStr =
      totalMins >= 60
        ? `${totalHours}h ${remainMins}m`
        : `${totalMins}m ${remainSecs}s`

    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center px-6"
        style={{ backgroundColor: 'var(--color-bg-2)' }}
      >
        <p
          style={{
            fontSize: 40,
            fontWeight: 700,
            color: 'var(--color-ink)',
            marginBottom: 12,
            letterSpacing: '-0.02em',
          }}
        >
          Session complete
        </p>
        <p style={{ fontSize: 16, color: 'var(--color-ink-2)', marginBottom: 4 }}>
          Total time: {timeStr}
        </p>
        <p style={{ fontSize: 16, color: 'var(--color-ink-2)', marginBottom: 32 }}>
          {steps.length} steps completed
        </p>
        <Button
          onClick={() => navigate('/')}
          style={{
            backgroundColor: 'var(--color-blue-6)',
            color: '#fff',
            border: 'none',
            borderRadius: 10,
            padding: '12px 28px',
            fontSize: 16,
            fontWeight: 600,
            minHeight: 44,
          }}
        >
          Back to today
        </Button>
      </div>
    )
  }

  const nextStep = steps[currentIndex + 1]
  const showWarning = secondsLeft <= 3 && secondsLeft > 0 && nextStep

  return (
    <div
      className="min-h-screen flex flex-col"
      style={{ backgroundColor: 'var(--color-bg-2)' }}
    >
      <div className="flex-1 flex flex-col justify-center px-6 pt-12 pb-6">
        <SessionStepList steps={steps} currentIndex={currentIndex} />

        {/* Timer */}
        <div className="mt-10">
          <p
            style={{
              fontSize: 40,
              fontWeight: 700,
              color: 'var(--color-ink)',
              fontVariantNumeric: 'tabular-nums',
              letterSpacing: '0.05em',
            }}
          >
            {formatTimer(secondsLeft)}
          </p>

          {/* 3-second countdown warning */}
          {showWarning ? (
            <p
              style={{
                fontSize: 14,
                color: 'var(--color-warn)',
                marginTop: 4,
              }}
            >
              Starting {nextStep.label} in {secondsLeft}...
            </p>
          ) : null}
        </div>

        {/* Skip step */}
        <div className="mt-6">
          <button
            onClick={goNext}
            style={{
              fontSize: 14,
              color: 'var(--color-ink-2)',
              background: 'none',
              border: '1px solid var(--color-line)',
              borderRadius: 8,
              padding: '10px 16px',
              minHeight: 44,
              cursor: 'pointer',
            }}
          >
            Skip step
          </button>
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

// ---------------------------------------------------------------------------
// Main screen: loads data, computes steps, delegates to SessionRunner
// ---------------------------------------------------------------------------

export function DuringSessionScreen() {
  const freeRideDurationMins = useUiStore(s => s.freeRideDurationMins)
  const setFreeRideDurationMins = useUiStore(s => s.setFreeRideDurationMins)

  // Wake lock: keep screen on during session (IOS-01)
  useWakeLock()

  // Clean up free-ride state on unmount so it does not leak into a real session
  useEffect(() => {
    return () => {
      setFreeRideDurationMins(null)
    }
  }, [setFreeRideDurationMins])

  const { data: session } = useQuery({
    queryKey: ['session', 'today'],
    queryFn: getSessionToday,
    // Do not refetch while riding
    staleTime: Infinity,
  })

  // Derive steps
  let steps: SessionStep[]
  if (freeRideDurationMins != null) {
    steps = generateFreeRideSteps(freeRideDurationMins)
  } else if (session) {
    const raw = (session as unknown as { structure?: unknown }).structure
    steps = parseSteps(raw, session.type)
  } else {
    // No session and no free-ride duration; fallback to empty (guard against crash)
    steps = []
  }

  if (steps.length === 0) {
    // Minimal empty guard
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ backgroundColor: 'var(--color-bg-2)' }}
      >
        <p style={{ color: 'var(--color-ink-2)', fontSize: 16 }}>
          No session steps available.
        </p>
      </div>
    )
  }

  return <SessionRunner steps={steps} />
}
