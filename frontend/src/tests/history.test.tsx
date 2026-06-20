import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { HistoryScreen } from '../screens/HistoryScreen'
import { CtlSparkline } from '../components/history/CtlSparkline'
import * as api from '../lib/api'
import type { Ride, PmcEntry } from '../lib/api'

// ---------------------------------------------------------------------------
// Mock dependencies
// ---------------------------------------------------------------------------

vi.mock('../lib/api', () => ({
  getRides: vi.fn(),
  getPmcHistory: vi.fn(),
  uploadRide: vi.fn(),
  getProfileMe: vi.fn(),
}))

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}))

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
}

function renderWithQuery(ui: React.ReactElement) {
  const client = makeQueryClient()
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>
  )
}

// ---------------------------------------------------------------------------
// Test: CtlSparkline gate (D-14)
// ---------------------------------------------------------------------------

describe('CtlSparkline (D-14 gate)', () => {
  it('does not render when tss_display_ready is false', () => {
    const history: PmcEntry[] = [
      { date: '2026-06-01', ctl: 30, atl: 35, tsb: -5, tss_display_ready: false },
    ]
    const { container } = render(<CtlSparkline history={history} />)
    expect(container.firstChild).toBeNull()
  })

  it('renders a chart when tss_display_ready is true', () => {
    const history: PmcEntry[] = [
      { date: '2026-05-01', ctl: 28, atl: 30, tsb: -2, tss_display_ready: false },
      { date: '2026-06-01', ctl: 40, atl: 38, tsb: 2, tss_display_ready: true },
    ]
    const { container } = render(<CtlSparkline history={history} />)
    // Container div rendered (not null)
    expect(container.firstChild).not.toBeNull()
    // The aria-label is present
    expect(container.querySelector('[aria-label="CTL fitness trend"]')).not.toBeNull()
  })

  it('does not render when history is empty', () => {
    const { container } = render(<CtlSparkline history={[]} />)
    expect(container.firstChild).toBeNull()
  })
})

// ---------------------------------------------------------------------------
// Test: HistoryScreen empty state
// ---------------------------------------------------------------------------

describe('HistoryScreen empty state', () => {
  beforeEach(() => {
    vi.mocked(api.getRides).mockResolvedValue([])
    vi.mocked(api.getPmcHistory).mockResolvedValue([])
  })

  it('shows "No rides yet" when getRides returns an empty list', async () => {
    renderWithQuery(<HistoryScreen />)
    await waitFor(() => {
      expect(screen.getByText('No rides yet')).toBeInTheDocument()
    })
  })

  it('shows the upload prompt in the empty state', async () => {
    renderWithQuery(<HistoryScreen />)
    await waitFor(() => {
      expect(
        screen.getByText(/Upload a .FIT file from Zwift/i)
      ).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// Test: FIT upload success path
// ---------------------------------------------------------------------------

describe('FitUploadZone upload', () => {
  beforeEach(() => {
    vi.mocked(api.getRides).mockResolvedValue([])
    vi.mocked(api.getPmcHistory).mockResolvedValue([])
  })

  it('calls uploadRide on file select and shows success toast', async () => {
    const mockRide: Ride = {
      id: 'ride-1',
      user_id: 'user-1',
      session_id: null,
      file_name: 'test.fit',
      ride_date: '2026-06-20',
      duration_seconds: 3600,
      distance_m: 30000,
      np_watts: 180,
      tss: 65,
      avg_power_watts: 165,
      created_at: '2026-06-20T10:00:00Z',
    }
    vi.mocked(api.uploadRide).mockResolvedValue(mockRide)
    const { toast } = await import('sonner')

    renderWithQuery(<HistoryScreen />)

    // Wait for screen to load
    await waitFor(() => {
      expect(screen.getByText('No rides yet')).toBeInTheDocument()
    })

    // Find the hidden file input and simulate a file selection
    const input = document.querySelector('input[type="file"]') as HTMLInputElement
    expect(input).not.toBeNull()

    const file = new File(['fit-data'], 'test.fit', { type: 'application/octet-stream' })
    Object.defineProperty(input, 'files', { value: [file], configurable: true })
    fireEvent.change(input)

    await waitFor(() => {
      expect(api.uploadRide).toHaveBeenCalledWith(file)
      expect(toast.success).toHaveBeenCalledWith('Ride uploaded. History updated.')
    })
  })
})
