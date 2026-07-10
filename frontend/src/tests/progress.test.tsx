import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { ProgressScreen } from '../screens/ProgressScreen'
import * as api from '../lib/api'
import type { Adaptation } from '../lib/api'

// ---------------------------------------------------------------------------
// Mock dependencies
// ---------------------------------------------------------------------------

vi.mock('../lib/api', () => ({
  getRides: vi.fn(),
  getPmcHistory: vi.fn(),
  getLatestPmc: vi.fn(),
  getAdaptations: vi.fn(),
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
    <QueryClientProvider client={client}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  )
}

function makeAdaptation(overrides: Partial<Adaptation> = {}): Adaptation {
  return {
    id: 'adapt-1',
    trigger: 'missed',
    scope: 'micro',
    explanation_text:
      'Micro-adjustment triggered by missed session abc123. Next 3 sessions reduced to 80% intensity to ease back in.',
    created_at: '2026-07-06T12:00:00Z',
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// Test: Adaptations section (ProgressScreen, TRANSP-03)
// ---------------------------------------------------------------------------

describe('ProgressScreen Adaptations section', () => {
  beforeEach(() => {
    vi.mocked(api.getRides).mockResolvedValue([])
    vi.mocked(api.getPmcHistory).mockResolvedValue([])
    vi.mocked(api.getLatestPmc).mockResolvedValue(null)
  })

  it('shows the exact empty-state sentence when getAdaptations returns []', async () => {
    vi.mocked(api.getAdaptations).mockResolvedValue([])

    renderWithQuery(<ProgressScreen />)

    await waitFor(() => {
      expect(
        screen.getByText("No adaptations yet. Your plan hasn't needed adjustment.")
      ).toBeInTheDocument()
    })
  })

  it('renders humanized trigger, explanation_text, and a formatted date for a populated row', async () => {
    vi.mocked(api.getAdaptations).mockResolvedValue([makeAdaptation()])

    renderWithQuery(<ProgressScreen />)

    await waitFor(() => {
      expect(screen.getByText('Missed session')).toBeInTheDocument()
    })
    expect(
      screen.getByText(
        'Micro-adjustment triggered by missed session abc123. Next 3 sessions reduced to 80% intensity to ease back in.'
      )
    ).toBeInTheDocument()
    expect(screen.getByText(/Jul/)).toBeInTheDocument()
  })

  it('renders without throwing when a row is missing optional/nullable fields', async () => {
    const partial = makeAdaptation({
      signal_count: undefined,
      status: undefined,
      trigger_session_ids: undefined,
    })
    vi.mocked(api.getAdaptations).mockResolvedValue([partial])

    expect(() => renderWithQuery(<ProgressScreen />)).not.toThrow()

    await waitFor(() => {
      expect(screen.getByText('Missed session')).toBeInTheDocument()
    })
  })
})
