import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
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

  it('auto-advances when the timer hits 0', async () => {
    setupFreeRide()
    // First call returns 0 (triggers auto-advance effect);
    // all subsequent calls return non-zero so the effect doesn't loop.
    // Use a flag rather than callN to be robust against React double-renders.
    let hasAdvanced = false
    vi.mocked(useSessionTimer).mockImplementation((_stepDuration, _stepStartEpoch) => {
      if (!hasAdvanced) {
        // Will return 0 on the first step (Warm-up), causing goNext()
        hasAdvanced = true
        return { secondsLeft: 0 }
      }
      return { secondsLeft: 1440 }
    })

    const { DuringSessionScreen } = await import('@/screens/DuringSessionScreen')
    render(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )

    await resolveQuery()
    await act(async () => { await Promise.resolve() })

    // Should have advanced past warm-up to Free ride
    expect(screen.getByText('Free ride')).toBeInTheDocument()
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
    await resolveQuery()

    // No redirect — Today's real (empty) state renders instead.
    expect(screen.queryByText('SESSION SCREEN')).toBeNull()
    expect(screen.getByText('No session today')).toBeInTheDocument()
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
    await resolveQuery()

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
    await resolveQuery()

    expect(screen.getByText('SESSION SCREEN')).toBeInTheDocument()
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
