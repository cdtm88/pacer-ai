import { createBrowserRouter, Navigate, Outlet } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { useAuth } from './hooks/useAuth'
import { useAuthStore } from './stores/authStore'
import { getProfileMe } from './lib/api'
import { LoginScreen } from './screens/LoginScreen'

// ---------------------------------------------------------------------------
// RootProvider: activate auth listener at the app root.
// Rendered as the root element so onAuthStateChange is always active.
// ---------------------------------------------------------------------------

export function RootProvider() {
  useAuth()
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
  const { data: profile, isLoading } = useQuery({
    queryKey: ['profile'],
    queryFn: getProfileMe,
  })

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

  if (profile === null) {
    return <Navigate to="/onboarding" replace />
  }

  return <Outlet />
}

// ---------------------------------------------------------------------------
// AppLayout placeholder (replaced in later plan by full tab bar implementation)
// ---------------------------------------------------------------------------

export function AppLayout() {
  return <Outlet />
}

// ---------------------------------------------------------------------------
// Placeholder screen components (replaced in later plans by src/screens/)
// ---------------------------------------------------------------------------

export function OnboardingScreen() {
  return <div>Onboarding</div>
}

export function TodayScreen() {
  return <div>Today</div>
}

export function AgendaScreen() {
  return <div>Agenda</div>
}

export function HistoryScreen() {
  return <div>History</div>
}

export function ChatScreen() {
  return <div>Chat</div>
}

export function DuringSessionScreen() {
  return <div>During Session</div>
}

export function SettingsScreen() {
  return <div>Settings</div>
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
