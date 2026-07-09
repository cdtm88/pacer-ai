import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { TooltipProvider } from '@/components/ui/tooltip'
import { SessionCard, type SessionData } from '@/components/session/SessionCard'
import { TsbChip, type PmcRow } from '@/components/session/TsbChip'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/lib/api', () => ({
  markSessionDone: vi.fn().mockResolvedValue(undefined),
  markSessionMissed: vi.fn().mockResolvedValue(undefined),
  exportSessionZwo: vi.fn().mockResolvedValue(undefined),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
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
        <TooltipProvider>
          {children}
        </TooltipProvider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

const MOCK_SESSION: SessionData = {
  id: 'session-1',
  scheduled_date: '2026-06-20',
  objective: 'Easy aerobic ride',
  structure: 'Warm up 10 min, Zone 2 for 40 min, cool down 10 min.',
  type: 'endurance',
  rpe_target: 4,
  duration_mins: 60,
  duration_minutes: null,
  tss_target: 55,
}

const PMC_NOT_READY: PmcRow = {
  tss_display_ready: false,
  ctl: 0,
  atl: 0,
  tsb: 0,
  date: '2026-06-20',
}

const PMC_READY_FRESH: PmcRow = {
  tss_display_ready: true,
  ctl: 40,
  atl: 30,
  tsb: 10, // > 5 = fresh
  date: '2026-06-20',
}

const PMC_READY_FATIGUED: PmcRow = {
  tss_display_ready: true,
  ctl: 50,
  atl: 70,
  tsb: -20, // < -10 = fatigued
  date: '2026-06-20',
}

const PMC_READY_BALANCED: PmcRow = {
  tss_display_ready: true,
  ctl: 40,
  atl: 38,
  tsb: 2, // between -10 and 5 = balanced
  date: '2026-06-20',
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('TsbChip gate (D-14)', () => {
  it('does NOT render when tss_display_ready is false', () => {
    const { container } = render(<TsbChip pmc={PMC_NOT_READY} />)
    expect(container.firstChild).toBeNull()
  })

  it('does NOT render when pmc is null', () => {
    const { container } = render(<TsbChip pmc={null} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders "Fresh" when tss_display_ready is true and tsb > 5', () => {
    render(<TsbChip pmc={PMC_READY_FRESH} />)
    expect(screen.getByText('Fresh')).toBeInTheDocument()
  })

  it('renders "Fatigued" when tss_display_ready is true and tsb < -10', () => {
    render(<TsbChip pmc={PMC_READY_FATIGUED} />)
    expect(screen.getByText('Fatigued')).toBeInTheDocument()
  })

  it('renders "Balanced" when tss_display_ready is true and tsb is between -10 and 5', () => {
    render(<TsbChip pmc={PMC_READY_BALANCED} />)
    expect(screen.getByText('Balanced')).toBeInTheDocument()
  })
})

describe('SessionCard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does NOT render TSB chip when tss_display_ready is false', () => {
    render(
      <Wrapper>
        <SessionCard session={MOCK_SESSION} pmc={PMC_NOT_READY} />
      </Wrapper>
    )
    // None of the three TSB states should appear
    expect(screen.queryByText('Fresh')).toBeNull()
    expect(screen.queryByText('Balanced')).toBeNull()
    expect(screen.queryByText('Fatigued')).toBeNull()
  })

  it('renders TSB chip when tss_display_ready is true', () => {
    render(
      <Wrapper>
        <SessionCard session={MOCK_SESSION} pmc={PMC_READY_FRESH} />
      </Wrapper>
    )
    expect(screen.getByText('Fresh')).toBeInTheDocument()
  })

  it('Export .zwo button is enabled and opens the modal', async () => {
    render(
      <Wrapper>
        <SessionCard session={MOCK_SESSION} pmc={PMC_NOT_READY} />
      </Wrapper>
    )
    const exportBtn = screen.getByRole('button', { name: /export \.zwo/i })
    expect(exportBtn).not.toBeDisabled()
    fireEvent.click(exportBtn)
    await waitFor(() => {
      // Modal heading "Export .zwo" appears alongside the button text
      const matches = screen.getAllByText('Export .zwo')
      expect(matches.length).toBeGreaterThan(1)
    })
  })

  it('renders the Duration / TSS / IF stat tile row', () => {
    render(
      <Wrapper>
        <SessionCard session={MOCK_SESSION} pmc={PMC_NOT_READY} />
      </Wrapper>
    )
    expect(screen.getByText('Duration')).toBeInTheDocument()
    expect(screen.getByText('TSS')).toBeInTheDocument()
    expect(screen.getByText('IF')).toBeInTheDocument()
  })

  it('clicking Mark missed opens the confirmation dialog with the correct title', async () => {
    render(
      <Wrapper>
        <SessionCard session={MOCK_SESSION} pmc={PMC_NOT_READY} />
      </Wrapper>
    )
    const missedBtn = screen.getByRole('button', { name: /mark missed/i })
    fireEvent.click(missedBtn)

    await waitFor(() => {
      expect(screen.getByText('Mark this session as missed?')).toBeInTheDocument()
    })
  })

  it('Mark missed dialog shows correct body copy', async () => {
    render(
      <Wrapper>
        <SessionCard session={MOCK_SESSION} pmc={PMC_NOT_READY} />
      </Wrapper>
    )
    fireEvent.click(screen.getByRole('button', { name: /mark missed/i }))

    await waitFor(() => {
      expect(
        screen.getByText('This will trigger a re-plan. Your coach will adjust upcoming sessions.')
      ).toBeInTheDocument()
    })
  })
})
