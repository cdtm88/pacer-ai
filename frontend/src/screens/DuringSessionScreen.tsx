import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { getSessionToday, getProfileMe } from '@/lib/api'
import { useSessionTimer } from '@/hooks/useSessionTimer'
import { useWakeLock } from '@/hooks/useWakeLock'
import { useUiStore } from '@/stores/uiStore'
import {
  loadSession,
  saveSession,
  clearSession,
  type PersistedSession,
} from '@/lib/sessionPersistence'

// ---------------------------------------------------------------------------
// Types & helpers
// ---------------------------------------------------------------------------

type ZoneType = 'recovery' | 'endurance' | 'tempo' | 'threshold' | 'vo2'

export interface SessionStep {
  label: string
  duration: number // minutes
  zone?: ZoneType
}

const ZONE_META: Record<ZoneType, { color: string; label: string; pctLow: number; pctHigh: number | null }> = {
  recovery:  { color: 'var(--color-zone-recovery)',  label: 'Recovery',  pctLow: 0,   pctHigh: 55  },
  endurance: { color: 'var(--color-zone-endurance)', label: 'Endurance', pctLow: 56,  pctHigh: 75  },
  tempo:     { color: 'var(--color-zone-tempo)',     label: 'Tempo',     pctLow: 76,  pctHigh: 90  },
  threshold: { color: 'var(--color-zone-threshold)', label: 'Threshold', pctLow: 91,  pctHigh: 105 },
  vo2:       { color: 'var(--color-zone-vo2)',       label: 'VO2 Max',   pctLow: 106, pctHigh: null },
}

function powerTarget(zone: ZoneType, ftp: number | null): string {
  const { pctLow, pctHigh } = ZONE_META[zone]
  if (ftp && ftp > 0) {
    const lo = Math.round(ftp * pctLow / 100)
    const hi = pctHigh ? Math.round(ftp * pctHigh / 100) : null
    return hi ? `${lo}–${hi}W` : `${lo}W+`
  }
  return pctHigh ? `${pctLow}–${pctHigh}% FTP` : `${pctLow}%+ FTP`
}

function formatTimer(secs: number): string {
  const s = Math.max(0, secs)
  const mm = Math.floor(s / 60)
  const ss = s % 60
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}`
}

function validZone(z: unknown): ZoneType {
  const valid: ZoneType[] = ['recovery', 'endurance', 'tempo', 'threshold', 'vo2']
  return valid.includes(z as ZoneType) ? (z as ZoneType) : 'endurance'
}

// ---------------------------------------------------------------------------
// Step builders
// ---------------------------------------------------------------------------

interface SessionStructure {
  warmup?: { duration_minutes?: number; description?: string }
  main_set?: { duration_minutes?: number; description?: string }
  cooldown?: { duration_minutes?: number; description?: string }
}

function parseSteps(structure: unknown, sessionType: string): SessionStep[] {
  if (!structure || typeof structure !== 'object') return []
  const s = structure as SessionStructure
  const steps: SessionStep[] = []
  if (s.warmup) steps.push({ label: s.warmup.description ?? 'Warm-up', duration: s.warmup.duration_minutes ?? 10, zone: 'recovery' })
  if (s.main_set) steps.push({ label: s.main_set.description ?? 'Main set', duration: s.main_set.duration_minutes ?? 20, zone: validZone(sessionType) })
  if (s.cooldown) steps.push({ label: s.cooldown.description ?? 'Cool-down', duration: s.cooldown.duration_minutes ?? 5, zone: 'recovery' })
  return steps
}

function generateFreeRideSteps(totalMins: number): SessionStep[] {
  const MIN_SEG = 3
  const warmup = Math.max(MIN_SEG, Math.round(totalMins * 0.1))
  const cooldown = Math.max(MIN_SEG, Math.round(totalMins * 0.1))
  const main = Math.max(MIN_SEG, totalMins - warmup - cooldown)
  return [
    { label: 'Warm-up', duration: warmup, zone: 'recovery' },
    { label: 'Free ride', duration: main, zone: 'endurance' },
    { label: 'Cool-down', duration: cooldown, zone: 'recovery' },
  ]
}

// ---------------------------------------------------------------------------
// Persistence restore
// ---------------------------------------------------------------------------

interface RestoredState {
  stepIndex: number
  completedDurationSecs: number
  stepStartEpoch: number
}

function computeRestoredState(saved: PersistedSession | null, steps: SessionStep[]): RestoredState {
  if (!saved || saved.stepIndex >= steps.length) {
    return { stepIndex: 0, completedDurationSecs: 0, stepStartEpoch: Date.now() }
  }
  let stepIndex = saved.stepIndex
  let completedDurationSecs = saved.completedDurationSecs
  let elapsedInStepMs = Date.now() - saved.stepStartEpoch
  while (stepIndex < steps.length) {
    const stepTotalMs = steps[stepIndex].duration * 60 * 1000
    if (elapsedInStepMs < stepTotalMs) break
    completedDurationSecs += steps[stepIndex].duration * 60
    elapsedInStepMs -= stepTotalMs
    stepIndex++
  }
  return { stepIndex, completedDurationSecs, stepStartEpoch: Date.now() - elapsedInStepMs }
}

// ---------------------------------------------------------------------------
// SessionRunner
// ---------------------------------------------------------------------------

function SessionRunner({ steps, ftp }: { steps: SessionStep[]; ftp: number | null }) {
  const navigate = useNavigate()

  const restoredRef = useRef<RestoredState | null>(null)
  if (restoredRef.current === null) {
    restoredRef.current = computeRestoredState(loadSession(), steps)
  }

  const [currentIndex, setCurrentIndex] = useState(restoredRef.current.stepIndex)
  const [completedDurationSecs, setCompletedDurationSecs] = useState(restoredRef.current.completedDurationSecs)
  const [stepStartEpoch, setStepStartEpoch] = useState(restoredRef.current.stepStartEpoch)

  const isDone = currentIndex >= steps.length
  const currentStep = steps[currentIndex]
  const stepDuration = currentStep ? currentStep.duration * 60 : 0
  const { secondsLeft } = useSessionTimer(stepDuration, stepStartEpoch)

  const goNext = useCallback(() => {
    if (currentIndex >= steps.length) return
    const nextIndex = currentIndex + 1
    const nextCompleted = completedDurationSecs + steps[currentIndex].duration * 60
    const nextEpoch = Date.now()
    setCurrentIndex(nextIndex)
    setCompletedDurationSecs(nextCompleted)
    setStepStartEpoch(nextEpoch)
    saveSession({ stepIndex: nextIndex, completedDurationSecs: nextCompleted, stepStartEpoch: nextEpoch })
  }, [currentIndex, completedDurationSecs, steps])

  // Save on mount
  useEffect(() => {
    if (!isDone) saveSession({ stepIndex: currentIndex, completedDurationSecs, stepStartEpoch })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 1s interval save
  useEffect(() => {
    if (isDone) return
    const id = setInterval(() => {
      saveSession({ stepIndex: currentIndex, completedDurationSecs, stepStartEpoch })
    }, 1000)
    return () => clearInterval(id)
  }, [currentIndex, completedDurationSecs, stepStartEpoch, isDone])

  // visibilitychange + pagehide save
  useEffect(() => {
    const save = () => {
      if (!isDone) saveSession({ stepIndex: currentIndex, completedDurationSecs, stepStartEpoch })
    }
    document.addEventListener('visibilitychange', save)
    window.addEventListener('pagehide', save)
    return () => {
      document.removeEventListener('visibilitychange', save)
      window.removeEventListener('pagehide', save)
    }
  }, [currentIndex, completedDurationSecs, stepStartEpoch, isDone])

  useEffect(() => { if (isDone) clearSession() }, [isDone])

  useEffect(() => {
    if (!isDone && secondsLeft === 0 && stepDuration > 0) goNext()
  }, [secondsLeft, isDone, stepDuration, goNext])

  // ── Session complete ──────────────────────────────────────────────────────

  if (isDone) {
    const totalMins = Math.floor(completedDurationSecs / 60)
    const totalHours = Math.floor(totalMins / 60)
    const remainMins = totalMins % 60
    const timeStr = totalMins >= 60 ? `${totalHours}h ${remainMins}m` : `${totalMins}m`

    return (
      <div style={{
        minHeight: '100dvh',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--color-surface)',
        padding: '24px',
        paddingTop: 'env(safe-area-inset-top)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}>
        <p style={{ fontSize: 13, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-zone-recovery)', marginBottom: 16 }}>
          Complete
        </p>
        <p style={{ fontSize: 56, fontWeight: 700, color: 'var(--color-ink)', letterSpacing: '-0.03em', lineHeight: 1, marginBottom: 8 }}>
          {timeStr}
        </p>
        <p style={{ fontSize: 15, color: 'var(--color-ink-3)', marginBottom: 48 }}>
          {steps.length} steps finished
        </p>
        <button
          onClick={() => { clearSession(); navigate('/') }}
          style={{
            backgroundColor: 'var(--color-ink)',
            color: 'var(--color-surface)',
            border: 'none',
            borderRadius: 12,
            padding: '14px 32px',
            fontSize: 15,
            fontWeight: 600,
            cursor: 'pointer',
            minHeight: 48,
          }}
        >
          Back to today
        </button>
      </div>
    )
  }

  // ── Active session ────────────────────────────────────────────────────────

  const zone = currentStep.zone ?? 'endurance'
  const { color: zoneColor, label: zoneLabel } = ZONE_META[zone]
  const target = powerTarget(zone, ftp)
  const nextStep = steps[currentIndex + 1]
  const nearEnd = secondsLeft <= 5 && secondsLeft > 0 && nextStep

  return (
    <div style={{
      minHeight: '100dvh',
      display: 'flex',
      flexDirection: 'column',
      backgroundColor: 'var(--color-surface)',
    }}>
      {/* Zone color strip */}
      <div style={{ height: 5, backgroundColor: zoneColor, width: '100%', flexShrink: 0 }} />

      {/* Content — centred column */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        paddingTop: 'max(20px, env(safe-area-inset-top))',
        paddingBottom: 'max(20px, env(safe-area-inset-bottom))',
        paddingLeft: 28,
        paddingRight: 28,
      }}>

        {/* Step counter */}
        <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-ink-3)', marginBottom: 20 }}>
          Step {currentIndex + 1} / {steps.length}
        </p>

        {/* Zone badge */}
        <span style={{
          fontSize: 11,
          fontWeight: 700,
          letterSpacing: '0.07em',
          textTransform: 'uppercase',
          color: zoneColor,
          border: `1.5px solid ${zoneColor}`,
          borderRadius: 20,
          padding: '5px 12px',
          marginBottom: 16,
          display: 'inline-block',
        }}>
          {zoneLabel}
        </span>

        {/* Step name */}
        <p style={{
          fontSize: 18,
          fontWeight: 500,
          color: 'var(--color-ink-2)',
          lineHeight: 1.4,
          maxWidth: 280,
        }}>
          {currentStep.label}
        </p>

        {/* Timer + power target — hero block */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
          <p style={{
            fontSize: 96,
            fontWeight: 700,
            color: 'var(--color-ink)',
            fontVariantNumeric: 'tabular-nums',
            letterSpacing: '-0.03em',
            lineHeight: 1,
            marginBottom: 14,
          }}>
            {formatTimer(secondsLeft)}
          </p>

          {/* Power target */}
          <p style={{
            fontSize: 28,
            fontWeight: 700,
            color: zoneColor,
            letterSpacing: '-0.01em',
            lineHeight: 1,
          }}>
            {target}
          </p>
        </div>

        {/* Next step */}
        {nextStep && (
          <div style={{ marginBottom: 24 }}>
            <p style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.07em',
              textTransform: 'uppercase',
              color: nearEnd ? zoneColor : 'var(--color-ink-3)',
              marginBottom: 4,
              transition: 'color 0.3s',
            }}>
              {nearEnd ? `Up next in ${secondsLeft}s` : 'Next'}
            </p>
            <p style={{ fontSize: 15, color: 'var(--color-ink-2)', fontWeight: 500, lineHeight: 1.4 }}>
              {nextStep.label}
            </p>
          </div>
        )}

        {/* Skip step */}
        <button
          onClick={goNext}
          style={{
            width: '100%',
            padding: '14px',
            marginBottom: 12,
            background: 'none',
            border: '1.5px solid var(--color-line)',
            borderRadius: 12,
            fontSize: 14,
            fontWeight: 600,
            color: 'var(--color-ink-2)',
            cursor: 'pointer',
            minHeight: 48,
          }}
        >
          Skip step
        </button>

        {/* End session */}
        <button
          onClick={() => { clearSession(); navigate('/') }}
          style={{
            background: 'none',
            border: 'none',
            fontSize: 13,
            fontWeight: 600,
            color: 'var(--color-bad)',
            cursor: 'pointer',
            padding: '8px 0',
            minHeight: 44,
          }}
        >
          End session
        </button>

      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// DuringSessionScreen — data loader
// ---------------------------------------------------------------------------

export function DuringSessionScreen() {
  const freeRideDurationMins = useUiStore(s => s.freeRideDurationMins)
  const setFreeRideDurationMins = useUiStore(s => s.setFreeRideDurationMins)

  useWakeLock()

  useEffect(() => {
    return () => { setFreeRideDurationMins(null) }
  }, [setFreeRideDurationMins])

  const { data: session } = useQuery({
    queryKey: ['session', 'today'],
    queryFn: getSessionToday,
    staleTime: Infinity,
  })

  const { data: profile } = useQuery({
    queryKey: ['profile', 'me'],
    queryFn: getProfileMe,
    staleTime: Infinity,
  })

  const ftp = profile?.ftp ?? null

  let steps: SessionStep[]
  if (freeRideDurationMins != null) {
    steps = generateFreeRideSteps(freeRideDurationMins)
  } else if (session) {
    const raw = (session as unknown as { structure?: unknown }).structure
    steps = parseSteps(raw, session.type)
  } else {
    steps = []
  }

  if (steps.length === 0) {
    return (
      <div style={{
        minHeight: '100dvh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--color-surface)',
      }}>
        <p style={{ color: 'var(--color-ink-3)', fontSize: 15 }}>No session steps available.</p>
      </div>
    )
  }

  return <SessionRunner steps={steps} ftp={ftp} />
}
