import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'

// ---------------------------------------------------------------------------
// Mocks — set up before imports that use them (analog: session.test.tsx)
// ---------------------------------------------------------------------------

const mockUploadRide = vi.fn()

vi.mock('@/lib/api', () => ({
  uploadRide: (...args: unknown[]) => mockUploadRide(...args),
}))

const mockToastError = vi.fn()
const mockToastSuccess = vi.fn()
const mockToastInfo = vi.fn()

vi.mock('sonner', () => ({
  toast: {
    error: (...args: unknown[]) => mockToastError(...args),
    success: (...args: unknown[]) => mockToastSuccess(...args),
    info: (...args: unknown[]) => mockToastInfo(...args),
  },
}))

import { FitUploadZone } from '@/components/history/FitUploadZone'

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
      {children}
    </QueryClientProvider>
  )
}

function renderZone() {
  const client = makeQueryClient()
  const invalidateSpy = vi.spyOn(client, 'invalidateQueries')
  render(
    <QueryClientProvider client={client}>
      <FitUploadZone />
    </QueryClientProvider>
  )
  return { client, invalidateSpy }
}

function makeDropEvent(file: File | null) {
  return {
    preventDefault: () => {},
    dataTransfer: { files: file ? [file] : [] },
  } as unknown as React.DragEvent<HTMLDivElement>
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('FitUploadZone', () => {
  beforeEach(() => {
    mockUploadRide.mockReset()
    mockToastError.mockReset()
    mockToastSuccess.mockReset()
    mockToastInfo.mockReset()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders an indeterminate progress bar while uploading, and unmounts it on completion', async () => {
    let resolveUpload: (value: { duplicate: boolean }) => void = () => {}
    mockUploadRide.mockReturnValue(
      new Promise((resolve) => {
        resolveUpload = resolve
      })
    )

    render(
      <Wrapper>
        <FitUploadZone />
      </Wrapper>
    )

    const zone = screen.getByTestId('fit-upload-zone')
    const file = new File(['data'], 'ride.fit', { type: 'application/octet-stream' })

    await act(async () => {
      fireEvent.drop(zone, {
        dataTransfer: { files: [file] },
      })
    })

    // Progress bar should be present while isUploading is true
    expect(screen.getByTestId('upload-progress-track')).toBeInTheDocument()
    expect(screen.getByTestId('upload-progress-fill')).toBeInTheDocument()
    // Existing spinner + text remain (additive, not replaced)
    expect(screen.getByText('Uploading ride...')).toBeInTheDocument()

    await act(async () => {
      resolveUpload({ duplicate: false })
      await Promise.resolve()
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(screen.queryByTestId('upload-progress-track')).not.toBeInTheDocument()
    })
  })

  it('rejects a non-.fit file on drop with a toast and never calls uploadRide', async () => {
    render(
      <Wrapper>
        <FitUploadZone />
      </Wrapper>
    )

    const zone = screen.getByTestId('fit-upload-zone')
    const badFile = new File(['data'], 'ride.gpx', { type: 'application/octet-stream' })

    await act(async () => {
      fireEvent.drop(zone, makeDropEvent(badFile))
    })

    expect(mockToastError).toHaveBeenCalledWith('Only .fit files are supported.')
    expect(mockUploadRide).not.toHaveBeenCalled()
  })

  it('calls uploadRide when a .fit file is dropped', async () => {
    mockUploadRide.mockResolvedValue({ duplicate: false })

    render(
      <Wrapper>
        <FitUploadZone />
      </Wrapper>
    )

    const zone = screen.getByTestId('fit-upload-zone')
    const goodFile = new File(['data'], 'ride.fit', { type: 'application/octet-stream' })

    await act(async () => {
      fireEvent.drop(zone, makeDropEvent(goodFile))
      await Promise.resolve()
      await Promise.resolve()
    })

    expect(mockUploadRide).toHaveBeenCalledWith(goodFile)
  })

  it('invalidates every affected query key on successful upload', async () => {
    mockUploadRide.mockResolvedValue({ duplicate: false })

    const { invalidateSpy } = renderZone()

    // renderZone renders into its own QueryClientProvider; grab the zone
    // rendered by that call.
    const zone = screen.getByTestId('fit-upload-zone')
    const file = new File(['data'], 'ride.fit', { type: 'application/octet-stream' })

    await act(async () => {
      fireEvent.drop(zone, makeDropEvent(file))
      await Promise.resolve()
      await Promise.resolve()
      await Promise.resolve()
    })

    const calledKeys = invalidateSpy.mock.calls.map(
      (call) => (call[0] as { queryKey: unknown[] }).queryKey
    )

    expect(calledKeys).toContainEqual(['rides'])
    expect(calledKeys).toContainEqual(['pmc', 'latest'])
    expect(calledKeys).toContainEqual(['pmc-history'])
    expect(calledKeys).toContainEqual(['session', 'today'])
    expect(calledKeys).toContainEqual(['sessions', 'upcoming'])
  })
})
