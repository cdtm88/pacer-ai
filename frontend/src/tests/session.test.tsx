import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router'
import React, { useState } from 'react'

// ---------------------------------------------------------------------------
// Mocks — set up before imports that use them
// ---------------------------------------------------------------------------

vi.mock('@/lib/api', () => ({
  getSessionToday: vi.fn().mockResolvedValue({
    id: 'session-1',
    user_id: 'user-1',
    date: '2026-06-21',
    type: 'endurance',
    status: 'planned',
    planned_tss: 50,
    actual_tss: null,
    notes: null,
    structure: {
      warmup: { duration_minutes: 1, description: 'Warm-up' },
      main_set: { duration_minutes: 2, description: 'Main set' },
      cooldown: { duration_minutes: 1, description: 'Cool-down' },
    },
  }),
  getProfileMe: vi.fn().mockResolvedValue(null),
  markSessionDone: vi.fn().mockResolvedValue(undefined),
  getUpcomingSessions: vi.fn().mockResolvedValue([]),
  getLatestPmc: vi.fn().mockResolvedValue(null),
  markSessionMissed: vi.fn().mockResolvedValue(undefined),
  exportSessionZwo: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('@/hooks/useWakeLock', () => ({
  useWakeLock: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}))

// Timer mock: controls the return value per test by setting this ref
const mockAdvanceFn = vi.fn()

vi.mock('@/hooks/useSessionTimer', () => ({
  useSessionTimer: vi.fn(),
}))

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
}

function Wrapper({ children }: { children: React.ReactNode }) {
  // Lazy-init the client once so a `rerender()` on the same root (used by the
  // live-resume fast-forward tests) does not reset the React Query cache.
  const [client] = useState(() => makeQueryClient())
  return (
    <QueryClientProvider client={client}>
      <MemoryRouter>
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// Minimal in-memory localStorage mock — jsdom's built-in localStorage is incomplete in this
// environment (missing .clear()); same pattern as pwa.test.tsx.
function makeLocalStorageMock() {
  const store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, val: string) => { store[key] = val },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { Object.keys(store).forEach(k => delete store[k]) },
  }
}

async function resolveQuery() {
  // Two microtask rounds to let React Query resolve
  await act(async () => { await Promise.resolve() })
  await act(async () => { await Promise.resolve() })
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

import { useSessionTimer } from '@/hooks/useSessionTimer'
import { useUiStore } from '@/stores/uiStore'
import { getSessionToday } from '@/lib/api'
import { saveSession, todayDateString, SESSION_PERSIST_KEY } from '@/lib/sessionPersistence'

// Use the free-ride path to bypass the useQuery for deterministic step data
// Steps become: Warm-up (3min), Free ride (24min), Cool-down (3min) for 30min ride
function setupFreeRide() {
  useUiStore.setState({ freeRideDurationMins: 30 })
}

describe('DuringSessionScreen', () => {
  beforeEach(() => {
    useUiStore.setState({ freeRideDurationMins: null })
    mockAdvanceFn.mockClear()
    vi.stubGlobal('localStorage', makeLocalStorageMock())
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.useRealTimers()
    useUiStore.setState({ freeRideDurationMins: null })
    vi.unstubAllGlobals()
  })

  it('renders the first step label and a MM:SS timer', async () => {
    setupFreeRide()
    // Timer is mid-step
    vi.mocked(useSessionTimer).mockReturnValue({ secondsLeft: 180 })

    const { DuringSessionScreen } = await import('@/screens/DuringSessionScreen')
    render(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )

    await resolveQuery()

    expect(screen.getByText('Warm-up')).toBeInTheDocument()
    // Timer should show MM:SS format
    const timer = screen.getByText(/^\d{2}:\d{2}$/)
    expect(timer).toBeInTheDocument()
  })

  it('Skip step advances immediately without waiting for timer', async () => {
    setupFreeRide()
    vi.mocked(useSessionTimer).mockReturnValue({ secondsLeft: 180 })

    const { DuringSessionScreen } = await import('@/screens/DuringSessionScreen')
    render(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )

    await resolveQuery()

    expect(screen.getByText('Warm-up')).toBeInTheDocument()

    // Mock next step timer
    vi.mocked(useSessionTimer).mockReturnValue({ secondsLeft: 1440 })

    const skipBtn = screen.getByRole('button', { name: /skip step/i })
    await act(async () => {
      fireEvent.click(skipBtn)
    })

    expect(screen.getByText('Free ride')).toBeInTheDocument()
  })

  it('auto-advances exactly one step when only that step has fully elapsed (item 8, single-step parity)', async () => {
    vi.useFakeTimers()
    const start = new Date('2026-01-01T00:00:00.000Z')
    vi.setSystemTime(start)
    setupFreeRide()

    // Mirror the real useSessionTimer's epoch math so the live-resume fast-forward
    // effect (which reads Date.now() - stepStartEpoch) observes genuinely elapsed
    // time, instead of a secondsLeft===0 signal decoupled from the clock.
    vi.mocked(useSessionTimer).mockImplementation(
      (stepDuration: number, stepStartEpoch: number) => ({
        secondsLeft: Math.max(0, stepDuration - Math.floor((Date.now() - stepStartEpoch) / 1000)),
      })
    )

    const { DuringSessionScreen } = await import('@/screens/DuringSessionScreen')
    const { rerender } = render(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )
    await resolveQuery()
    expect(screen.getByText('Warm-up')).toBeInTheDocument()

    // Background for just past Warm-up's 180s (190s elapsed — 10s into Free ride).
    await act(async () => {
      vi.setSystemTime(new Date(start.getTime() + 190_000))
    })
    rerender(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )
    await act(async () => { await Promise.resolve() })

    // Advanced exactly one step — Free ride (step 2 of 3), not two steps to Cool-down.
    expect(screen.getByText('Step 2 / 3')).toBeInTheDocument()
    const stepLabels = screen.getAllByText('Free ride')
    expect(stepLabels.length).toBeGreaterThan(0)
  })

  it('fast-forwards through multiple elapsed steps on live resume (item 8)', async () => {
    vi.useFakeTimers()
    const start = new Date('2026-01-01T00:00:00.000Z')
    vi.setSystemTime(start)
    setupFreeRide()

    vi.mocked(useSessionTimer).mockImplementation(
      (stepDuration: number, stepStartEpoch: number) => ({
        secondsLeft: Math.max(0, stepDuration - Math.floor((Date.now() - stepStartEpoch) / 1000)),
      })
    )

    const { DuringSessionScreen } = await import('@/screens/DuringSessionScreen')
    const { rerender } = render(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )
    await resolveQuery()
    expect(screen.getByText('Warm-up')).toBeInTheDocument()

    // Background through Warm-up (180s) + all of Free ride (1440s) + 60s into Cool-down.
    await act(async () => {
      vi.setSystemTime(new Date(start.getTime() + 180_000 + 1_440_000 + 60_000))
    })
    rerender(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )
    await act(async () => { await Promise.resolve() })

    // Landed on the correct step in one hop — step 3 of 3 (Cool-down), not step 2.
    expect(screen.getByText('Step 3 / 3')).toBeInTheDocument()
    // Correct remaining time in the new step: 180s - 60s = 120s = 02:00.
    expect(screen.getByText('02:00')).toBeInTheDocument()
  })

  it('shows Session complete overlay after the last step', async () => {
    setupFreeRide()
    // Skip through all 3 steps manually
    vi.mocked(useSessionTimer).mockReturnValue({ secondsLeft: 180 })

    const { DuringSessionScreen } = await import('@/screens/DuringSessionScreen')
    render(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )

    await resolveQuery()
    expect(screen.getByText('Warm-up')).toBeInTheDocument()

    // Skip step 1 (Warm-up)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /skip step/i }))
    })
    expect(screen.getByText('Free ride')).toBeInTheDocument()

    // Skip step 2 (Free ride)
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /skip step/i }))
    })
    expect(screen.getByText('Cool-down')).toBeInTheDocument()

    // Skip step 3 (Cool-down) - triggers Session complete
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /skip step/i }))
    })

    expect(screen.getByText('Session complete')).toBeInTheDocument()
    expect(screen.getByText('3 steps completed')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /back to today/i })).toBeInTheDocument()
  })

  it('persists sessionId and date alongside step state (item 1, D-06 foundation)', async () => {
    setupFreeRide()
    vi.mocked(useSessionTimer).mockReturnValue({ secondsLeft: 180 })

    const { DuringSessionScreen } = await import('@/screens/DuringSessionScreen')
    render(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )

    await resolveQuery()
    // Let the resolved session id flow into a re-render + a persistence save.
    await act(async () => { await Promise.resolve() })

    const raw = localStorage.getItem('pacer-active-session')
    expect(raw).toBeTruthy()
    const saved = JSON.parse(raw!)
    expect(saved).toHaveProperty('sessionId')
    expect(typeof saved.date).toBe('string')
    expect(saved.date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
  })
})

// ---------------------------------------------------------------------------
// Stale-session mismatch guard (item 1, D-06)
// ---------------------------------------------------------------------------

function renderTodayScreenAt(TodayScreen: React.ComponentType) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<TodayScreen />} />
          <Route path="/session" element={<div>SESSION SCREEN</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('TodayScreen stale-session mismatch guard (item 1, D-06)', () => {
  beforeEach(() => {
    vi.stubGlobal('localStorage', makeLocalStorageMock())
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it('mismatched sessionId is silently discarded — no redirect, no dialog/toast', async () => {
    saveSession({
      sessionId: 'stale-session-999',
      date: todayDateString(),
      stepIndex: 1,
      completedDurationSecs: 60,
      stepStartEpoch: Date.now(),
      sessionStartTimestamp: Date.now(),
    })
    vi.mocked(getSessionToday).mockResolvedValueOnce(null)

    const { TodayScreen } = await import('@/screens/TodayScreen')
    renderTodayScreenAt(TodayScreen)

    // No redirect — Today's real (empty) state renders instead.
    await waitFor(() => expect(screen.getByText('No session today')).toBeInTheDocument())
    expect(screen.queryByText('SESSION SCREEN')).toBeNull()
    // The stale record is gone.
    expect(localStorage.getItem(SESSION_PERSIST_KEY)).toBeNull()
    // D-06: fully silent — no dialog or toast/alert element for the discard.
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('mismatched date is silently discarded — no redirect, no dialog/toast', async () => {
    saveSession({
      sessionId: null,
      date: '2000-01-01',
      stepIndex: 0,
      completedDurationSecs: 0,
      stepStartEpoch: Date.now(),
      sessionStartTimestamp: Date.now(),
    })
    vi.mocked(getSessionToday).mockResolvedValueOnce(null)

    const { TodayScreen } = await import('@/screens/TodayScreen')
    renderTodayScreenAt(TodayScreen)

    await waitFor(() => expect(screen.getByText('No session today')).toBeInTheDocument())
    expect(screen.queryByText('SESSION SCREEN')).toBeNull()
    expect(localStorage.getItem(SESSION_PERSIST_KEY)).toBeNull()
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })

  it('matching sessionId + date resumes — redirects to /session, record left intact', async () => {
    saveSession({
      sessionId: null,
      date: todayDateString(),
      stepIndex: 1,
      completedDurationSecs: 60,
      stepStartEpoch: Date.now(),
      sessionStartTimestamp: Date.now(),
    })
    vi.mocked(getSessionToday).mockResolvedValueOnce(null)

    const { TodayScreen } = await import('@/screens/TodayScreen')
    renderTodayScreenAt(TodayScreen)

    await waitFor(() => expect(screen.getByText('SESSION SCREEN')).toBeInTheDocument())
    expect(localStorage.getItem(SESSION_PERSIST_KEY)).not.toBeNull()
  })
})

describe('DuringSessionScreen stale-session mismatch guard (item 1, D-06)', () => {
  beforeEach(() => {
    useUiStore.setState({ freeRideDurationMins: null })
    vi.stubGlobal('localStorage', makeLocalStorageMock())
  })

  afterEach(() => {
    vi.clearAllMocks()
    useUiStore.setState({ freeRideDurationMins: null })
    vi.unstubAllGlobals()
  })

  it('mismatched persisted session is discarded — live session starts fresh from step 0', async () => {
    saveSession({
      sessionId: 'some-other-session',
      date: todayDateString(),
      stepIndex: 2, // would be Cool-down if trusted
      completedDurationSecs: 1620,
      stepStartEpoch: Date.now(),
      sessionStartTimestamp: Date.now(),
    })
    setupFreeRide()
    vi.mocked(useSessionTimer).mockReturnValue({ secondsLeft: 180 })

    const { DuringSessionScreen } = await import('@/screens/DuringSessionScreen')
    render(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )
    await resolveQuery()

    // Discarded the mismatched record and rendered fresh state (step 0: Warm-up) —
    // not the stale record's step 2 (Cool-down).
    expect(screen.getByText('Warm-up')).toBeInTheDocument()
    expect(screen.queryByText('Cool-down')).toBeNull()

    const stored = JSON.parse(localStorage.getItem(SESSION_PERSIST_KEY)!)
    expect(stored.stepIndex).toBe(0)
    expect(stored.sessionId).not.toBe('some-other-session')
  })
})

// ---------------------------------------------------------------------------
// fastForwardSteps + computeRestoredState (item 8, live-resume overshoot fix)
// ---------------------------------------------------------------------------

describe('fastForwardSteps + computeRestoredState (item 8)', () => {
  const steps = [
    { label: 'Warm-up', duration: 3 },    // 180s
    { label: 'Free ride', duration: 24 }, // 1440s
    { label: 'Cool-down', duration: 3 },  // 180s
  ]

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('advances exactly one step when only that step has fully elapsed (single-step parity)', async () => {
    const { fastForwardSteps } = await import('@/screens/DuringSessionScreen')
    const start = 1_000_000
    const result = fastForwardSteps(0, 0, start, steps, start + 190_000) // 10s into Free ride

    expect(result.stepIndex).toBe(1)
    expect(result.completedDurationSecs).toBe(180)
    expect(result.stepStartEpoch).toBe(start + 180_000)
  })

  it('fast-forwards through multiple fully-elapsed steps in one call', async () => {
    const { fastForwardSteps } = await import('@/screens/DuringSessionScreen')
    const start = 1_000_000
    // Warm-up (180s) + Free ride (1440s) + 60s into Cool-down = 1680s elapsed
    const now = start + 1_680_000
    const result = fastForwardSteps(0, 0, start, steps, now)

    expect(result.stepIndex).toBe(2)
    expect(result.completedDurationSecs).toBe(180 + 1440)
    expect(result.stepStartEpoch).toBe(now - 60_000)
  })

  it('clamps at steps.length once every step has elapsed', async () => {
    const { fastForwardSteps } = await import('@/screens/DuringSessionScreen')
    const start = 1_000_000
    const now = start + 10_000_000 // way past all 3 steps
    const result = fastForwardSteps(0, 0, start, steps, now)

    expect(result.stepIndex).toBe(3) // steps.length — session is done
  })

  it('computeRestoredState (reload path) delegates to the same multi-step fast-forward logic', async () => {
    const { computeRestoredState } = await import('@/screens/DuringSessionScreen')
    const start = 1_000_000
    const saved = {
      sessionId: null,
      date: '2026-01-01',
      stepIndex: 0,
      completedDurationSecs: 0,
      stepStartEpoch: start,
      sessionStartTimestamp: start,
    }
    // Simulate Date.now() being 1680s after stepStartEpoch (page reload after
    // backgrounding through Warm-up + Free ride, 60s into Cool-down).
    vi.spyOn(Date, 'now').mockReturnValue(start + 1_680_000)

    const restored = computeRestoredState(saved, steps)

    expect(restored.stepIndex).toBe(2)
    expect(restored.completedDurationSecs).toBe(1620)
    expect(restored.sessionStartTimestamp).toBe(start)
  })
})
