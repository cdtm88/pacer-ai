import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router'
import { TooltipProvider } from '@/components/ui/tooltip'
import { SettingsScreen } from '@/screens/SettingsScreen'

// ---------------------------------------------------------------------------
// Mocks -- hoisted before imports by Vitest
// ---------------------------------------------------------------------------

vi.mock('@/lib/api', () => ({
  getProfileMe: vi.fn().mockResolvedValue({
    ftp: 200,
    lthr: 160,
    weight_kg: 75,
  }),
}))

vi.mock('@/lib/supabase', () => ({
  supabase: {
    auth: {
      getSession: vi.fn().mockResolvedValue({
        data: {
          session: {
            user: {
              email: 'rider@example.com',
              user_metadata: { display_name: 'Test Rider' },
            },
          },
        },
      }),
      signOut: vi.fn().mockResolvedValue({ error: null }),
      signInWithOtp: vi.fn().mockResolvedValue({ error: null }),
    },
  },
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

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('SettingsScreen', () => {
  it('renders without throwing and exposes a Sign out button', async () => {
    render(
      <Wrapper>
        <SettingsScreen />
      </Wrapper>
    )

    const signOutBtn = await screen.findByRole('button', { name: /sign out/i })
    expect(signOutBtn).toBeInTheDocument()
  })
})
