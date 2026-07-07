/**
 * Gate decision tests for AuthGate and FirstRunGate.
 * Tests routing decisions without making Supabase network calls.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { AuthGate, FirstRunGate, RootProvider } from '../router'
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
import { supabase } from '../lib/supabase'

const mockGetProfileMe = vi.mocked(getProfileMe)
const mockOnAuthStateChange = vi.mocked(supabase.auth.onAuthStateChange)

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

describe('RootProvider query cache clear on auth transitions (item 10, ASVS V3)', () => {
  beforeEach(() => {
    useAuthStore.setState({ session: null, user: null, isLoading: false })
    vi.clearAllMocks()
    vi.mocked(supabase.auth.getSession).mockResolvedValue({ data: { session: null } } as never)
    mockOnAuthStateChange.mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    } as never)
  })

  function makeQueryClient() {
    return new QueryClient({
      defaultOptions: { queries: { retry: false, gcTime: 0 } },
    })
  }

  function renderRootProvider(queryClient: QueryClient) {
    const routes = createMemoryRouter(
      [
        {
          element: <RootProvider />,
          children: [{ index: true, element: <div>root content</div> }],
        },
      ],
      { initialEntries: ['/'] },
    )
    render(
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={routes} />
      </QueryClientProvider>,
    )
  }

  // RootProvider's own onAuthStateChange listener takes a single `event` arg;
  // useAuth's listener (also registered via the same mocked function) takes
  // `(event, newSession)`. Distinguish by arity rather than call order so the
  // test doesn't depend on hook-registration ordering.
  function getCacheClearCallback(): (event: string) => void {
    const call = mockOnAuthStateChange.mock.calls.find(
      (c) => (c[0] as (...args: unknown[]) => void).length === 1,
    )
    if (!call) throw new Error('RootProvider onAuthStateChange callback was not registered')
    return call[0] as (event: string) => void
  }

  it('clears the query cache on SIGNED_IN', async () => {
    const queryClient = makeQueryClient()
    const clearSpy = vi.spyOn(queryClient, 'clear')
    renderRootProvider(queryClient)

    await waitFor(() => expect(mockOnAuthStateChange).toHaveBeenCalled())
    getCacheClearCallback()('SIGNED_IN')

    expect(clearSpy).toHaveBeenCalledTimes(1)
  })

  it('does NOT clear the query cache on TOKEN_REFRESHED (Pitfall 5)', async () => {
    const queryClient = makeQueryClient()
    const clearSpy = vi.spyOn(queryClient, 'clear')
    renderRootProvider(queryClient)

    await waitFor(() => expect(mockOnAuthStateChange).toHaveBeenCalled())
    getCacheClearCallback()('TOKEN_REFRESHED')

    expect(clearSpy).not.toHaveBeenCalled()
  })

  it('still clears the query cache on SIGNED_OUT and USER_UPDATED', async () => {
    const queryClient = makeQueryClient()
    const clearSpy = vi.spyOn(queryClient, 'clear')
    renderRootProvider(queryClient)

    await waitFor(() => expect(mockOnAuthStateChange).toHaveBeenCalled())
    const callback = getCacheClearCallback()

    callback('SIGNED_OUT')
    expect(clearSpy).toHaveBeenCalledTimes(1)

    callback('USER_UPDATED')
    expect(clearSpy).toHaveBeenCalledTimes(2)
  })
})

// Prevent TS "no exports" error
export {}
