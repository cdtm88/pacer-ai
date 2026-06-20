import { createBrowserRouter, Navigate, Outlet } from 'react-router'
import { DuringSessionScreen as DuringSessionScreenImpl } from './screens/DuringSessionScreen'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'
import { useAuth } from './hooks/useAuth'
import { useAuthStore } from './stores/authStore'
import { getProfileMe } from './lib/api'
import { supabase } from './lib/supabase'
import { LoginScreen } from './screens/LoginScreen'
import { AppLayout } from './components/AppLayout'
import { TodayScreen } from './screens/TodayScreen'
import { AgendaScreen } from './screens/AgendaScreen'
import { OnboardingScreen } from './screens/OnboardingScreen'
import { HistoryScreen } from './screens/HistoryScreen'
import { ChatScreen } from './screens/ChatScreen'
import { SettingsScreen } from './screens/SettingsScreen'

// ---------------------------------------------------------------------------
// RootProvider: activate auth listener at the app root.
// Rendered as the root element so onAuthStateChange is always active.
// ---------------------------------------------------------------------------

export function RootProvider() {
  useAuth()
  const queryClient = useQueryClient()

  // Clear all cached queries on sign-out to prevent cross-user data leakage.
  // Also fires on user-id change (e.g. switching accounts in the same browser).
  useEffect(() => {
    const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'SIGNED_OUT' || event === 'USER_UPDATED') {
        queryClient.clear()
      }
    })
    return () => subscription.unsubscribe()
  }, [queryClient])

  return <Outlet />
}

// ---------------------------------------------------------------------------
// AuthGate: redirect to /login when no session (D-01)
// ---------------------------------------------------------------------------

export function AuthGate() {
  const { session, isLoading } = useAuthStore()

  if (isLoading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ backgroundColor: 'var(--color-bg)' }}
      >
        <div
          className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
          style={{ borderColor: 'var(--color-blue-6)', borderTopColor: 'transparent' }}
          aria-label="Loading"
        />
      </div>
    )
  }

  if (!session) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}

// ---------------------------------------------------------------------------
// FirstRunGate: redirect to /onboarding when no profile exists (D-02)
// ---------------------------------------------------------------------------

export function FirstRunGate() {
  const { user } = useAuthStore()
  const userId = user?.id

  const { data: profile, isLoading, isError } = useQuery({
    queryKey: ['profile', userId],
    queryFn: getProfileMe,
    // Don't fetch if there's no authenticated user — gate should not be reached
    // without a session, but guard defensively.
    enabled: !!userId,
  })

  if (isLoading || !userId) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ backgroundColor: 'var(--color-bg)' }}
      >
        <div
          className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
          style={{ borderColor: 'var(--color-blue-6)', borderTopColor: 'transparent' }}
          aria-label="Loading"
        />
      </div>
    )
  }

  // 401 / network error: treat as session-invalid and redirect to login.
  if (isError) {
    return <Navigate to="/login" replace />
  }

  // Null profile means onboarding hasn't been completed.
  if (profile === null || profile === undefined) {
    return <Navigate to="/onboarding" replace />
  }

  return <Outlet />
}

// ---------------------------------------------------------------------------
// DuringSessionScreen: delegates to the real implementation
// ---------------------------------------------------------------------------

export function DuringSessionScreen() {
  return <DuringSessionScreenImpl />
}

// ---------------------------------------------------------------------------
// Router: full route tree with real gates
// ---------------------------------------------------------------------------

export const router = createBrowserRouter([
  {
    // RootProvider wraps all routes so useAuth() is active globally
    element: <RootProvider />,
    children: [
      {
        path: '/login',
        element: <LoginScreen />,
      },
      {
        // /onboarding: requires auth session but NOT a profile (so it's outside FirstRunGate)
        path: '/onboarding',
        element: <AuthGate />,
        children: [
          {
            index: true,
            element: <OnboardingScreen />,
          },
        ],
      },
      {
        // Root protected branch: AuthGate -> FirstRunGate -> AppLayout -> screen
        path: '/',
        element: <AuthGate />,
        children: [
          {
            element: <FirstRunGate />,
            children: [
              {
                element: <AppLayout />,
                children: [
                  {
                    index: true,
                    element: <TodayScreen />,
                  },
                  {
                    path: 'agenda',
                    element: <AgendaScreen />,
                  },
                  {
                    path: 'history',
                    element: <HistoryScreen />,
                  },
                  {
                    path: 'chat',
                    element: <ChatScreen />,
                  },
                  {
                    path: 'session',
                    element: <DuringSessionScreen />,
                  },
                  {
                    path: 'settings',
                    element: <SettingsScreen />,
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
])
