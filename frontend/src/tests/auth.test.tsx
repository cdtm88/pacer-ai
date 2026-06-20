/**
 * Gate decision tests for AuthGate and FirstRunGate.
 * Tests routing decisions without making Supabase network calls.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthGate, FirstRunGate } from '../router'
import { useAuthStore } from '../stores/authStore'

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

// Mock the API module so getProfileMe never makes real HTTP calls
vi.mock('../lib/api', () => ({
  getProfileMe: vi.fn(),
}))

// Mock the supabase module so auth state calls are no-ops
vi.mock('../lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({ data: { session: null } }),
      onAuthStateChange: vi.fn().mockReturnValue({
        data: { subscription: { unsubscribe: vi.fn() } },
      }),
    },
  },
}))

import { getProfileMe } from '../lib/api'
import type { Profile } from '../lib/api'

const mockGetProfileMe = vi.mocked(getProfileMe)

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        gcTime: 0,
      },
    },
  })
}

function renderRouter(routes: Parameters<typeof createMemoryRouter>[0], initialPath = '/') {
  const queryClient = makeQueryClient()
  const router = createMemoryRouter(routes, { initialEntries: [initialPath] })
  return render(
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('AuthGate', () => {
  beforeEach(() => {
    // Reset authStore to initial state (no session, loading done)
    useAuthStore.setState({ session: null, user: null, isLoading: false })
  })

  it('(1) redirects to /login when there is no session', async () => {
    const routes = createMemoryRouter(
      [
        {
          path: '/',
          element: <AuthGate />,
          children: [{ index: true, element: <div>Protected content</div> }],
        },
        {
          path: '/login',
          element: <div>Login page</div>,
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

    await waitFor(() => {
      expect(screen.getByText('Login page')).toBeInTheDocument()
    })
    expect(screen.queryByText('Protected content')).not.toBeInTheDocument()
  })

  it('renders Outlet when session exists', async () => {
    // Set a session in the store
    useAuthStore.setState({
      session: { access_token: 'token123' } as never,
      user: { id: 'user-1' } as never,
      isLoading: false,
    })

    const routes = createMemoryRouter(
      [
        {
          path: '/',
          element: <AuthGate />,
          children: [{ index: true, element: <div>Protected content</div> }],
        },
        {
          path: '/login',
          element: <div>Login page</div>,
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

    await waitFor(() => {
      expect(screen.getByText('Protected content')).toBeInTheDocument()
    })
    expect(screen.queryByText('Login page')).not.toBeInTheDocument()
  })
})

describe('FirstRunGate', () => {
  beforeEach(() => {
    // Set a valid session so AuthGate passes (only testing FirstRunGate here)
    useAuthStore.setState({
      session: { access_token: 'token123' } as never,
      user: { id: 'user-1' } as never,
      isLoading: false,
    })
    vi.clearAllMocks()
  })

  it('(2) redirects to /onboarding when getProfileMe returns null (no profile)', async () => {
    mockGetProfileMe.mockResolvedValue(null)

    const routes = createMemoryRouter(
      [
        {
          path: '/',
          element: <FirstRunGate />,
          children: [{ index: true, element: <div>Today screen</div> }],
        },
        {
          path: '/onboarding',
          element: <div>Onboarding screen</div>,
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

    await waitFor(() => {
      expect(screen.getByText('Onboarding screen')).toBeInTheDocument()
    })
    expect(screen.queryByText('Today screen')).not.toBeInTheDocument()
  })

  it('(3) renders Outlet when session and profile both exist', async () => {
    const mockProfile: Profile = {
      id: 'profile-1',
      user_id: 'user-1',
      display_name: 'Test User',
      ftp: 200,
      lthr: null,
      weight_kg: 75,
      onboarding_complete: true,
      created_at: '2024-01-01T00:00:00Z',
      updated_at: '2024-01-01T00:00:00Z',
    }
    mockGetProfileMe.mockResolvedValue(mockProfile)

    const routes = createMemoryRouter(
      [
        {
          path: '/',
          element: <FirstRunGate />,
          children: [{ index: true, element: <div>Today screen</div> }],
        },
        {
          path: '/onboarding',
          element: <div>Onboarding screen</div>,
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

    await waitFor(() => {
      expect(screen.getByText('Today screen')).toBeInTheDocument()
    })
    expect(screen.queryByText('Onboarding screen')).not.toBeInTheDocument()
  })
})

// Prevent TS "no exports" error
export {}
