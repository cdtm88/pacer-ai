import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getSessionToday, getProfileMe, markSessionDone } from '@/lib/api'
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
  sessionStartTimestamp: number
}

function computeRestoredState(saved: PersistedSession | null, steps: SessionStep[]): RestoredState {
  const now = Date.now()
  if (!saved || saved.stepIndex >= steps.length) {
    return { stepIndex: 0, completedDurationSecs: 0, stepStartEpoch: now, sessionStartTimestamp: now }
  }
  let stepIndex = saved.stepIndex
  let completedDurationSecs = saved.completedDurationSecs
  let elapsedInStepMs = now - saved.stepStartEpoch
  while (stepIndex < steps.length) {
    const stepTotalMs = steps[stepIndex].duration * 60 * 1000
    if (elapsedInStepMs < stepTotalMs) break
    completedDurationSecs += steps[stepIndex].duration * 60
    elapsedInStepMs -= stepTotalMs
    stepIndex++
  }
  // Preserve the original sessionStartTimestamp so total elapsed is always
  // computed from Date.now() - sessionStartTimestamp, not re-anchored on restore.
  const sessionStartTimestamp = saved.sessionStartTimestamp ?? now - (completedDurationSecs * 1000) - elapsedInStepMs
  return { stepIndex, completedDurationSecs, stepStartEpoch: now - elapsedInStepMs, sessionStartTimestamp }
}

// ---------------------------------------------------------------------------
// SessionRunner
// ---------------------------------------------------------------------------

function SessionRunner({
  steps,
  ftp,
  freeRideDurationMins,
  sessionId,
}: {
  steps: SessionStep[]
  ftp: number | null
  freeRideDurationMins: number | null
  sessionId: string | null
}) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const finishSession = useCallback(async () => {
    clearSession()
    if (sessionId) {
      try { await markSessionDone(sessionId) } catch { /* navigate anyway */ }
    }
    await queryClient.invalidateQueries({ queryKey: ['session', 'today'] })
    navigate('/')
  }, [sessionId, queryClient, navigate])

  const restoredRef = useRef<RestoredState | null>(null)
  if (restoredRef.current === null) {
    restoredRef.current = computeRestoredState(loadSession(), steps)
  }

  const [currentIndex, setCurrentIndex] = useState(restoredRef.current.stepIndex)
  const [completedDurationSecs, setCompletedDurationSecs] = useState(restoredRef.current.completedDurationSecs)
  const [stepStartEpoch, setStepStartEpoch] = useState(restoredRef.current.stepStartEpoch)
  // sessionStartTimestamp is the wall-clock epoch when this session started.
  // It never changes after first mount — used as the absolute anchor for total elapsed time.
  const sessionStartTimestampRef = useRef(restoredRef.current.sessionStartTimestamp)

  const isDone = currentIndex >= steps.length
  const currentStep = steps[currentIndex]
  const stepDuration = currentStep ? currentStep.duration * 60 : 0
  const { secondsLeft } = useSessionTimer(stepDuration, stepStartEpoch)

  // Build the persisted payload from current state.
  // freeRideDurationMins is included so iOS kill+reopen can reconstruct free-ride steps.
  const buildPayload = useCallback(() => ({
    stepIndex: currentIndex,
    completedDurationSecs,
    stepStartEpoch,
    sessionStartTimestamp: sessionStartTimestampRef.current,
    ...(freeRideDurationMins != null ? { freeRideDurationMins } : {}),
  }), [currentIndex, completedDurationSecs, stepStartEpoch, freeRideDurationMins])

  const goNext = useCallback(() => {
    if (currentIndex >= steps.length) return
    const nextIndex = currentIndex + 1
    const nextCompleted = completedDurationSecs + steps[currentIndex].duration * 60
    const nextEpoch = Date.now()
    setCurrentIndex(nextIndex)
    setCompletedDurationSecs(nextCompleted)
    setStepStartEpoch(nextEpoch)
    saveSession({
      stepIndex: nextIndex,
      completedDurationSecs: nextCompleted,
      stepStartEpoch: nextEpoch,
      sessionStartTimestamp: sessionStartTimestampRef.current,
      ...(freeRideDurationMins != null ? { freeRideDurationMins } : {}),
    })
  }, [currentIndex, completedDurationSecs, steps, freeRideDurationMins])

  // Save on mount — synchronous within the effect, fires before any background suspension.
  useEffect(() => {
    if (!isDone) saveSession(buildPayload())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // 1s interval save — keeps localStorage fresh so iOS kill never loses more than 1s.
  useEffect(() => {
    if (isDone) return
    const id = setInterval(() => saveSession(buildPayload()), 1000)
    return () => clearInterval(id)
  }, [buildPayload, isDone])

  // visibilitychange + pagehide: save immediately on every visibility transition.
  // These fire before iOS suspends JS — most reliable save opportunity.
  useEffect(() => {
    const save = () => { if (!isDone) saveSession(buildPayload()) }
    document.addEventListener('visibilitychange', save)
    window.addEventListener('pagehide', save)
    return () => {
      document.removeEventListener('visibilitychange', save)
      window.removeEventListener('pagehide', save)
    }
  }, [buildPayload, isDone])

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
          onClick={() => { void finishSession() }}
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
          onClick={() => { void finishSession() }}
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
  const freeRideDurationMinsFromStore = useUiStore(s => s.freeRideDurationMins)
  const setFreeRideDurationMins = useUiStore(s => s.setFreeRideDurationMins)

  useWakeLock()

  useEffect(() => {
    return () => { setFreeRideDurationMins(null) }
  }, [setFreeRideDurationMins])

  const { data: session, isLoading: sessionLoading } = useQuery({
    queryKey: ['session', 'today'],
    queryFn: getSessionToday,
    staleTime: Infinity,
  })

  const { data: profile, isLoading: profileLoading } = useQuery({
    queryKey: ['profile', 'me'],
    queryFn: getProfileMe,
    staleTime: Infinity,
  })

  // On iOS PWA kill+reopen, Zustand state is wiped — freeRideDurationMins becomes null.
  // Fall back to the value persisted in localStorage so free-ride sessions can restore.
  const persistedSession = loadSession()
  const freeRideDurationMins =
    freeRideDurationMinsFromStore ??
    persistedSession?.freeRideDurationMins ??
    null

  // For free-ride sessions, steps are known immediately (no API needed).
  // For structured sessions, wait for session + profile before mounting SessionRunner
  // so it never mounts with stale/empty steps and immediately remounts with real data.
  const isFreeRide = freeRideDurationMins != null
  const isDataReady = isFreeRide || (!sessionLoading && !profileLoading)

  if (!isDataReady) {
    return (
      <div style={{
        minHeight: '100dvh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--color-surface)',
      }}>
        <div
          className="animate-spin"
          style={{
            width: 32, height: 32, borderRadius: '50%',
            border: '2px solid var(--color-blue-6)',
            borderTopColor: 'transparent',
          }}
        />
      </div>
    )
  }

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

  return <SessionRunner steps={steps} ftp={ftp} freeRideDurationMins={freeRideDurationMins} sessionId={session?.id ?? null} />
}
