import { createBrowserRouter, Outlet } from 'react-router'

// ---------------------------------------------------------------------------
// Placeholder gate components (replaced in plan 04-04 with real logic)
// ---------------------------------------------------------------------------

export function AuthGate() {
  return <Outlet />
}

export function FirstRunGate() {
  return <Outlet />
}

export function AppLayout() {
  return <Outlet />
}

// ---------------------------------------------------------------------------
// Placeholder screen components (replaced in later plans by src/screens/)
// ---------------------------------------------------------------------------

export function LoginScreen() {
  return <div>Login</div>
}

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
// Router: full route tree with placeholder gates and screens
// ---------------------------------------------------------------------------

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <LoginScreen />,
  },
  {
    path: '/onboarding',
    element: <OnboardingScreen />,
  },
  {
    // Root branch: AuthGate -> FirstRunGate -> AppLayout -> screen
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
])
