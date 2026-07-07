/**
 * Router error boundary tests (item 12, D-09/D-10).
 *
 * Renders a real data router with AppLayout as the parent route and a
 * deliberately-throwing screen mounted at a leaf route with
 * ErrorBoundary: RouteErrorFallback, mirroring the real router.tsx wiring.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AppLayout } from '../components/AppLayout'
import { RouteErrorFallback } from '../components/ErrorBoundaryFallback'

// AppLayout renders IOSInstallBanner, which reads window.matchMedia — not
// mocked globally in setup.ts and irrelevant to the error-boundary behavior
// under test here, so stub it out.
vi.mock('../components/pwa/IOSInstallBanner', () => ({
  IOSInstallBanner: () => null,
}))

function ThrowingScreen(): never {
  throw new Error('boom: simulated render crash')
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
}

function renderCrashedRoute() {
  const routes = createMemoryRouter(
    [
      {
        element: <AppLayout />,
        children: [
          {
            index: true,
            element: <ThrowingScreen />,
            ErrorBoundary: RouteErrorFallback,
          },
        ],
      },
    ],
    { initialEntries: ['/'] },
  )

  const queryClient = makeQueryClient()
  render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={routes} />
    </QueryClientProvider>,
  )
}

describe('Router error boundary (item 12)', () => {
  it('renders the minimal fallback instead of white-screening when a leaf route throws', () => {
    renderCrashedRoute()

    expect(screen.getByText('Something went wrong')).toBeInTheDocument()
    expect(screen.getByText('This page ran into a problem.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument()
  })

  it('keeps the AppLayout nav shell mounted when a child route crashes (D-10)', () => {
    renderCrashedRoute()

    // The Settings gear button lives in AppLayout's own header, not in the
    // crashed child route — its presence proves the parent stayed mounted.
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument()
  })

  it('renders no error message/stack detail (D-09)', () => {
    renderCrashedRoute()

    expect(screen.queryByText(/boom: simulated render crash/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Error:/)).not.toBeInTheDocument()
  })
})
