import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import React from 'react'

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
}))

vi.mock('@/hooks/useWakeLock', () => ({
  useWakeLock: vi.fn(),
}))

// Timer mock: each call advances a counter so secondsLeft decrements predictably
const mockAdvanceFn = vi.fn()
// We'll control the return value per test by setting this ref
let timerCallCount = 0
let mockTimerSecondsLeft = 60

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
  return (
    <QueryClientProvider client={makeQueryClient()}>
      <MemoryRouter>
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  )
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

// Use the free-ride path to bypass the useQuery for deterministic step data
// Steps become: Warm-up (3min), Free ride (24min), Cool-down (3min) for 30min ride
function setupFreeRide() {
  useUiStore.setState({ freeRideDurationMins: 30 })
}

describe('DuringSessionScreen', () => {
  beforeEach(() => {
    useUiStore.setState({ freeRideDurationMins: null })
    mockAdvanceFn.mockClear()
    timerCallCount = 0
  })

  afterEach(() => {
    vi.clearAllMocks()
    useUiStore.setState({ freeRideDurationMins: null })
  })

  it('renders the first step label and a MM:SS timer', async () => {
    setupFreeRide()
    // Timer is mid-step
    vi.mocked(useSessionTimer).mockReturnValue({ secondsLeft: 180, advance: mockAdvanceFn })

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
    vi.mocked(useSessionTimer).mockReturnValue({ secondsLeft: 180, advance: mockAdvanceFn })

    const { DuringSessionScreen } = await import('@/screens/DuringSessionScreen')
    render(
      <Wrapper>
        <DuringSessionScreen />
      </Wrapper>
    )

    await resolveQuery()

    expect(screen.getByText('Warm-up')).toBeInTheDocument()

    // Mock next step timer
    vi.mocked(useSessionTimer).mockReturnValue({ secondsLeft: 1440, advance: mockAdvanceFn })

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
    vi.mocked(useSessionTimer).mockImplementation((_totalSeconds) => {
      if (!hasAdvanced) {
        // Will return 0 on the first step (Warm-up), causing goNext()
        return {
          secondsLeft: 0,
          advance: () => { hasAdvanced = true },
        }
      }
      return { secondsLeft: 1440, advance: mockAdvanceFn }
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
    vi.mocked(useSessionTimer).mockReturnValue({ secondsLeft: 180, advance: mockAdvanceFn })

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
})
