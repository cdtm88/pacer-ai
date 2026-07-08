import { Outlet, useNavigate, useLocation } from 'react-router'
import { Settings } from 'lucide-react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { BottomTabBar } from './nav/BottomTabBar'
import { DesktopSidebar } from './nav/DesktopSidebar'
import { IOSInstallBanner } from './pwa/IOSInstallBanner'

const ROUTE_TITLES: Record<string, string> = {
  '/': 'Today',
  '/agenda': 'Agenda',
  '/history': 'History',
  '/chat': 'Coach',
  '/settings': 'Settings',
}

function todayLabel(): string {
  return new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
}

export function AppLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const title = ROUTE_TITLES[pathname] ?? 'PacerAI'
  const isToday = pathname === '/'

  return (
    <TooltipProvider>
      <div
        className="h-dvh"
        style={{ backgroundColor: 'var(--color-bg)' }}
      >
        {/* Desktop sidebar */}
        <DesktopSidebar />

        {/* Main content: offset by sidebar on desktop */}
        <div className="md:ml-60 flex flex-col h-dvh">
          {/* Contextual screen header: page title (+ date on Today) and Settings gear */}
          <header
            className="flex items-center justify-between gap-3 px-5 shrink-0"
            style={{
              minHeight: 60,
              backgroundColor: 'var(--color-surface)',
              borderBottom: '1px solid var(--color-line)',
            }}
          >
            <div className="min-w-0">
              <h1
                className="truncate"
                style={{ fontSize: 20, fontWeight: 700, color: 'var(--color-ink)', letterSpacing: '-0.01em', lineHeight: 1.1 }}
              >
                {title}
              </h1>
              {isToday && (
                <p style={{ fontSize: 13, fontWeight: 500, color: 'var(--color-ink-3)', marginTop: 2 }}>
                  {todayLabel()}
                </p>
              )}
            </div>
            <button
              onClick={() => navigate('/settings')}
              className="p-2 -mr-2 rounded-lg transition-colors shrink-0 hover:bg-[var(--color-bg-2)]"
              style={{ color: 'var(--color-ink-2)' }}
              aria-label="Settings"
            >
              <Settings size={22} />
            </button>
          </header>

          {/* Outlet — scrolls within the dynamic viewport, above the in-flow tab bar */}
          <main
            className="flex-1 overflow-y-auto"
            style={{ minHeight: 0 }}
          >
            <Outlet />
          </main>

          {/* Mobile bottom tab bar — in-flow (not fixed) so it stays inside the
              dynamic viewport, above Safari's floating toolbar, never behind it */}
          <BottomTabBar />
        </div>

        {/* iOS PWA install banner (appears above tab bar on iOS Safari first visit) */}
        <IOSInstallBanner />
      </div>
    </TooltipProvider>
  )
}
