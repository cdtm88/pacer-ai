import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { getSessionToday, getProfileMe, markSessionDone } from '@/lib/api'
import { useSessionTimer } from '@/hooks/useSessionTimer'
import { useWakeLock } from '@/hooks/useWakeLock'
import { useUiStore } from '@/stores/uiStore'
import {
  saveSession,
  clearSession,
  todayDateString,
  loadMatchingSession,
  peekMatchingSession,
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

// Whole-session clock: MM:SS, or H:MM:SS once past an hour. Used for the
// overall elapsed/remaining readouts beside the session progress bar.
function formatClock(secs: number): string {
  const s = Math.max(0, Math.floor(secs))
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = s % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
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

export interface FastForwardResult {
  stepIndex: number
  completedDurationSecs: number
  stepStartEpoch: number
}

// Walks forward through however many steps' worth of wall-clock time have fully elapsed
// since stepStartEpoch, landing on the correct in-progress step with the correct remaining
// time. Pure function of (stepIndex, completedDurationSecs, stepStartEpoch, steps, now) —
// used both by computeRestoredState (reload path) and the live-resume secondsLeft===0
// effect (item 8), so both paths fast-forward through multiple elapsed steps identically
// instead of the live path silently absorbing overshoot with a single goNext().
export function fastForwardSteps(
  stepIndex: number,
  completedDurationSecs: number,
  stepStartEpoch: number,
  steps: SessionStep[],
  now: number
): FastForwardResult {
  let idx = stepIndex
  let completed = completedDurationSecs
  let elapsedInStepMs = now - stepStartEpoch
  while (idx < steps.length) {
    const stepTotalMs = steps[idx].duration * 60 * 1000
    if (elapsedInStepMs < stepTotalMs) break
    completed += steps[idx].duration * 60
    elapsedInStepMs -= stepTotalMs
    idx++
  }
  return { stepIndex: idx, completedDurationSecs: completed, stepStartEpoch: now - elapsedInStepMs }
}

export function computeRestoredState(saved: PersistedSession | null, steps: SessionStep[]): RestoredState {
  const now = Date.now()
  if (!saved || saved.stepIndex >= steps.length) {
    return { stepIndex: 0, completedDurationSecs: 0, stepStartEpoch: now, sessionStartTimestamp: now }
  }
  const { stepIndex, completedDurationSecs, stepStartEpoch } = fastForwardSteps(
    saved.stepIndex,
    saved.completedDurationSecs,
    saved.stepStartEpoch,
    steps,
    now
  )
  // Preserve the original sessionStartTimestamp so total elapsed is always
  // computed from Date.now() - sessionStartTimestamp, not re-anchored on restore.
  const sessionStartTimestamp = saved.sessionStartTimestamp ?? now - (completedDurationSecs * 1000) - (now - stepStartEpoch)
  return { stepIndex, completedDurationSecs, stepStartEpoch, sessionStartTimestamp }
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
    // Item 1, D-06: only trust a persisted record that actually matches this session
    // (sessionId + today's date). A stale/mismatched record is silently discarded and
    // restore falls back to a fresh state.
    restoredRef.current = computeRestoredState(loadMatchingSession(sessionId), steps)
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

  // ── Pause / Resume ─────────────────────────────────────────────────────────
  // Pause without touching useSessionTimer: freeze the displayed value, and on
  // resume shift stepStartEpoch forward by the elapsed paused duration so the
  // countdown continues from exactly where it stopped. The auto-advance effect
  // also short-circuits while isPaused (see its guard below). Known limitation:
  // the 1s/visibility saves keep persisting the un-shifted epoch while paused, so
  // an iOS kill mid-pause would count paused wall-clock as elapsed on restore —
  // an acceptable edge case that avoids rewriting the persistence effects.
  const [isPaused, setIsPaused] = useState(false)
  const pauseStartRef = useRef(0)
  const [frozenSecs, setFrozenSecs] = useState(0)

  const togglePause = useCallback(() => {
    setIsPaused(prev => {
      if (prev) {
        const pausedMs = Date.now() - pauseStartRef.current
        setStepStartEpoch(e => e + pausedMs)
        return false
      }
      pauseStartRef.current = Date.now()
      setFrozenSecs(secondsLeft)
      return true
    })
  }, [secondsLeft])

  // Value shown on the hero timer + used for progress math (frozen while paused).
  const displaySecs = isPaused ? frozenSecs : secondsLeft

  // Build the persisted payload from current state.
  // freeRideDurationMins is included so iOS kill+reopen can reconstruct free-ride steps.
  // sessionId + date identify which real session this record belongs to (item 1, D-06) —
  // every saveSession call site must include both so a stale/mismatched record can be
  // detected and silently discarded by the consumers that read it back.
  const buildPayload = useCallback(() => ({
    sessionId,
    date: todayDateString(),
    stepIndex: currentIndex,
    completedDurationSecs,
    stepStartEpoch,
    sessionStartTimestamp: sessionStartTimestampRef.current,
    ...(freeRideDurationMins != null ? { freeRideDurationMins } : {}),
  }), [sessionId, currentIndex, completedDurationSecs, stepStartEpoch, freeRideDurationMins])

  const goNext = useCallback(() => {
    if (currentIndex >= steps.length) return
    const nextIndex = currentIndex + 1
    const nextCompleted = completedDurationSecs + steps[currentIndex].duration * 60
    const nextEpoch = Date.now()
    setCurrentIndex(nextIndex)
    setCompletedDurationSecs(nextCompleted)
    setStepStartEpoch(nextEpoch)
    saveSession({
      sessionId,
      date: todayDateString(),
      stepIndex: nextIndex,
      completedDurationSecs: nextCompleted,
      stepStartEpoch: nextEpoch,
      sessionStartTimestamp: sessionStartTimestampRef.current,
      ...(freeRideDurationMins != null ? { freeRideDurationMins } : {}),
    })
  }, [sessionId, currentIndex, completedDurationSecs, steps, freeRideDurationMins])

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

  // Live-resume fast-forward (item 8): when the timer detects the current step has
  // elapsed, route through the same fastForwardSteps logic computeRestoredState uses on
  // reload, anchored on the CURRENT stepStartEpoch — not a bare goNext(). This correctly
  // fast-forwards through however many steps' worth of time actually elapsed (e.g. the
  // tab was backgrounded through 2+ steps), instead of goNext()'s single-step advance
  // with a reset full-duration timer silently absorbing the overshoot.
  useEffect(() => {
    if (isDone || secondsLeft !== 0 || stepDuration <= 0 || isPaused) return
    const now = Date.now()
    const result = fastForwardSteps(currentIndex, completedDurationSecs, stepStartEpoch, steps, now)
    if (result.stepIndex === currentIndex && result.stepStartEpoch === stepStartEpoch) return
    setCurrentIndex(result.stepIndex)
    setCompletedDurationSecs(result.completedDurationSecs)
    setStepStartEpoch(result.stepStartEpoch)
    saveSession({
      sessionId,
      date: todayDateString(),
      stepIndex: result.stepIndex,
      completedDurationSecs: result.completedDurationSecs,
      stepStartEpoch: result.stepStartEpoch,
      sessionStartTimestamp: sessionStartTimestampRef.current,
      ...(freeRideDurationMins != null ? { freeRideDurationMins } : {}),
    })
  }, [secondsLeft, isDone, stepDuration, currentIndex, completedDurationSecs, stepStartEpoch, steps, sessionId, freeRideDurationMins, isPaused])

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
        backgroundColor: 'var(--color-bg-2)',
        padding: '24px',
        paddingTop: 'env(safe-area-inset-top)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}>
        <p style={{ fontSize: 40, fontWeight: 700, color: 'var(--color-ink)', marginBottom: 16 }}>
          Session complete
        </p>
        <p style={{ fontSize: 56, fontWeight: 700, color: 'var(--color-ink)', letterSpacing: '-0.03em', lineHeight: 1, marginBottom: 8 }}>
          {timeStr}
        </p>
        <p style={{ fontSize: 15, color: 'var(--color-ink-3)', marginBottom: 48 }}>
          {steps.length} steps completed
        </p>
        <button
          onClick={() => { void finishSession() }}
          style={{
            backgroundColor: 'var(--color-blue-6)',
            color: '#fff',
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
  const nearEnd = !isPaused && displaySecs <= 3 && displaySecs > 0 && nextStep

  // Whole-session progress: totals derived from the steps array. Overall elapsed
  // is fully-completed steps plus how far into the current step we are.
  const totalSessionSecs = steps.reduce((acc, s) => acc + s.duration * 60, 0)
  const currentStepElapsed = Math.max(0, stepDuration - displaySecs)
  const overallElapsed = Math.min(totalSessionSecs, completedDurationSecs + currentStepElapsed)
  const overallRemaining = Math.max(0, totalSessionSecs - overallElapsed)
  const progressPct = totalSessionSecs > 0 ? (overallElapsed / totalSessionSecs) * 100 : 0

  return (
    <div className="ds-bg" style={{
      minHeight: '100dvh',
      display: 'flex',
      flexDirection: 'column',
      // Subtle zone-tinted wash so the current effort is glanceable at arm's length.
      // Tint transitions when the zone changes (motion, item 3); disabled under
      // prefers-reduced-motion via the .ds-bg rule in the injected style block.
      backgroundColor: `color-mix(in srgb, ${zoneColor} 7%, var(--color-surface))`,
      transition: 'background-color 250ms ease-out',
    }}>
      {/* Motion + reduced-motion rules (scoped to this screen) */}
      <style>{`
        @keyframes dsStepIn { from { opacity: 0; transform: scale(0.97); } to { opacity: 1; transform: none; } }
        .ds-step-in { animation: dsStepIn 200ms ease-out; }
        @media (prefers-reduced-motion: reduce) {
          .ds-step-in { animation: none; }
          .ds-bg { transition: none !important; }
          .ds-progress-fill { transition: none !important; }
        }
      `}</style>

      {/* Zone color strip */}
      <div style={{ height: 6, backgroundColor: zoneColor, width: '100%', flexShrink: 0 }} />

      {/* Whole-session progress bar */}
      <div style={{ padding: '12px 24px 0', flexShrink: 0 }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'baseline',
          marginBottom: 8,
        }}>
          <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: '0.07em', textTransform: 'uppercase', color: 'var(--color-ink-3)' }}>
            Block {Math.min(currentIndex + 1, steps.length)} / {steps.length}
          </span>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--color-ink-3)', fontVariantNumeric: 'tabular-nums' }}>
            <span style={{ color: 'var(--color-ink-2)' }}>{formatClock(overallElapsed)}</span>
            {' / '}{formatClock(overallRemaining)} left
          </span>
        </div>
        <div
          role="progressbar"
          aria-valuenow={Math.round(progressPct)}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label="Session progress"
          style={{
            height: 4,
            borderRadius: 999,
            backgroundColor: 'var(--color-line)',
            overflow: 'hidden',
          }}
        >
          <div
            className="ds-progress-fill"
            style={{
              height: '100%',
              width: `${progressPct}%`,
              backgroundColor: zoneColor,
              borderRadius: 999,
              transition: 'width 0.3s linear, background-color 250ms ease-out',
            }}
          />
        </div>
      </div>

      {/* Content — centred column */}
      <div style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        textAlign: 'center',
        paddingTop: 'max(20px, env(safe-area-inset-top))',
        paddingBottom: 'max(20px, env(safe-area-inset-bottom))',
        paddingLeft: 24,
        paddingRight: 24,
      }}>

        {/* Step counter */}
        <p style={{ fontSize: 12, fontWeight: 600, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--color-ink-3)', marginBottom: 16 }}>
          Step {currentIndex + 1} / {steps.length}
        </p>

        {/* Zone badge — re-keyed on step change to replay the scale/opacity-in */}
        <span
          key={`zone-${currentIndex}`}
          className="ds-step-in"
          style={{
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
          }}
        >
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
            marginBottom: 16,
            opacity: isPaused ? 0.5 : 1,
            transition: 'opacity 200ms ease-out',
          }}>
            {formatTimer(displaySecs)}
          </p>

          {/* Power target — filled zone lozenge; the key number to hold on the bike.
              Re-keyed on step change to replay the scale/opacity-in. */}
          <span
            key={`target-${currentIndex}`}
            className="ds-step-in"
            style={{
              fontSize: 30,
              fontWeight: 700,
              color: '#fff',
              backgroundColor: zoneColor,
              letterSpacing: '-0.01em',
              lineHeight: 1,
              borderRadius: 999,
              padding: '10px 24px',
              display: 'inline-block',
              fontVariantNumeric: 'tabular-nums',
              transition: 'background-color 250ms ease-out',
            }}
          >
            {target}
          </span>

          {/* Paused indicator */}
          {isPaused && (
            <p style={{ marginTop: 16, fontSize: 12, fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--color-ink-3)' }}>
              Paused
            </p>
          )}
        </div>

        {/* Next step */}
        {nextStep && (
          <div style={{ marginBottom: 24 }}>
            <p style={nearEnd ? {
              fontSize: 14,
              fontWeight: 400,
              color: 'var(--color-warn)',
              marginBottom: 4,
              transition: 'color 0.3s',
            } : {
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: '0.07em',
              textTransform: 'uppercase',
              color: 'var(--color-ink-3)',
              marginBottom: 4,
              transition: 'color 0.3s',
            }}>
              {nearEnd ? `Starting ${nextStep.label} in ${secondsLeft}...` : 'Next'}
            </p>
            <p style={{ fontSize: 15, color: 'var(--color-ink-2)', fontWeight: 500, lineHeight: 1.4 }}>
              {nextStep.label}
            </p>
          </div>
        )}

        {/* Secondary actions: Pause/Resume + Skip step */}
        <div style={{ display: 'flex', gap: 12, width: '100%', marginBottom: 12 }}>
          <button
            onClick={togglePause}
            aria-pressed={isPaused}
            style={{
              flex: 1,
              padding: '14px',
              background: isPaused ? zoneColor : 'none',
              border: `1.5px solid ${isPaused ? zoneColor : 'var(--color-line)'}`,
              borderRadius: 12,
              fontSize: 14,
              fontWeight: 600,
              color: isPaused ? '#fff' : 'var(--color-ink-2)',
              cursor: 'pointer',
              minHeight: 48,
              transition: 'background-color 200ms ease-out, border-color 200ms ease-out, color 200ms ease-out',
            }}
          >
            {isPaused ? 'Resume' : 'Pause'}
          </button>
          <button
            onClick={goNext}
            style={{
              flex: 1,
              padding: '14px',
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
        </div>

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
  // Item 1, D-06: only trust the persisted record once we know today's real session id
  // (or that the query resolved to no session), so a stale/mismatched record can never
  // leak a wrong-day or wrong-session freeRideDurationMins into this restore.
  // Use the non-mutating peek here: this runs during render, and clearing storage as a
  // side effect races with SessionRunner's live saves. When the session query resolves,
  // a free ride mounted before it (with sessionId=null) would otherwise have its
  // just-saved record cleared here as a false mismatch. SessionRunner's own restore
  // (loadMatchingSession) remains the authoritative stale-record discard.
  const persistedSession = sessionLoading ? null : peekMatchingSession(session?.id ?? null)
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
