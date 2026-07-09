import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { ZwoExportModal } from '@/components/session/ZwoExportModal'
import type { SessionData } from '@/components/session/SessionCard'
import * as api from '@/lib/api'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock('@/lib/api', () => ({
  exportSessionZwo: vi.fn(),
  markSessionDone: vi.fn().mockResolvedValue(undefined),
  markSessionMissed: vi.fn().mockResolvedValue(undefined),
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
      <MemoryRouter>{children}</MemoryRouter>
    </QueryClientProvider>
  )
}

const MOCK_SESSION: SessionData = {
  id: 'session-1',
  scheduled_date: '2026-06-21',
  objective: 'Endurance ride',
  structure: {
    warmup: { duration_minutes: 10, description: 'Warm up easy' },
    main_set: { duration_minutes: 40, description: 'Zone 2 steady' },
    cooldown: { duration_minutes: 10, description: 'Cool down easy' },
  } as unknown as SessionData['structure'],
  type: 'Endurance',
  rpe_target: 4,
  duration_mins: 60,
  duration_minutes: null,
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('ZwoExportModal', () => {
  const onClose = vi.fn()

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('shows preview without fetching on open', () => {
    render(
      <Wrapper>
        <ZwoExportModal
          session={MOCK_SESSION}
          ftp={200}
          onClose={onClose}
        />
      </Wrapper>
    )

    // Session name line
    expect(screen.getByText('Endurance - 2026-06-21')).toBeInTheDocument()
    // FTP line
    expect(screen.getByText('FTP used: 200W')).toBeInTheDocument()
    // Workout summary lines
    expect(screen.getByText('Warmup - 10 min')).toBeInTheDocument()
    expect(screen.getByText('Main set - 40 min')).toBeInTheDocument()
    expect(screen.getByText('Cool-down - 10 min')).toBeInTheDocument()
    // No fetch on open
    expect(api.exportSessionZwo).not.toHaveBeenCalled()
  })

  it('triggers download on Download .zwo click', async () => {
    vi.mocked(api.exportSessionZwo).mockResolvedValue(undefined)
    const { toast } = await import('sonner')

    render(
      <Wrapper>
        <ZwoExportModal
          session={MOCK_SESSION}
          ftp={200}
          onClose={onClose}
        />
      </Wrapper>
    )

    fireEvent.click(screen.getByText('Download .zwo'))

    await waitFor(() => {
      expect(api.exportSessionZwo).toHaveBeenCalledWith('session-1')
      expect(toast.success).toHaveBeenCalledWith('Workout file downloaded.')
    })
    expect(onClose).toHaveBeenCalled()
  })

  it('stays open and toasts on error', async () => {
    vi.mocked(api.exportSessionZwo).mockRejectedValue(new Error('export failed 500'))
    const { toast } = await import('sonner')

    render(
      <Wrapper>
        <ZwoExportModal
          session={MOCK_SESSION}
          ftp={200}
          onClose={onClose}
        />
      </Wrapper>
    )

    fireEvent.click(screen.getByText('Download .zwo'))

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'Export failed. Try again or contact support if the problem continues.'
      )
    })
    // Modal must stay open (onClose not called in catch)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('shows no-FTP copy when ftp is null', () => {
    render(
      <Wrapper>
        <ZwoExportModal
          session={MOCK_SESSION}
          ftp={null}
          onClose={onClose}
        />
      </Wrapper>
    )

    expect(screen.getByText('FTP: not yet estimated. Free-ride format applies.')).toBeInTheDocument()
  })
})
