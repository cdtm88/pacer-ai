import { Outlet, useNavigate } from 'react-router'
import { Settings } from 'lucide-react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { BottomTabBar } from './nav/BottomTabBar'
import { DesktopSidebar } from './nav/DesktopSidebar'
import { IOSInstallBanner } from './pwa/IOSInstallBanner'

export function AppLayout() {
  const navigate = useNavigate()

  return (
    <TooltipProvider>
      <div
        className="min-h-screen"
        style={{ backgroundColor: 'var(--color-bg)' }}
      >
        {/* Desktop sidebar */}
        <DesktopSidebar />

        {/* Main content: offset by sidebar on desktop */}
        <div className="md:ml-60 flex flex-col min-h-screen">
          {/* Screen header with Settings gear (mobile: shows gear; desktop: gear also available) */}
          <header
            className="flex items-center justify-end px-4 py-3 shrink-0"
            style={{
              backgroundColor: 'var(--color-surface)',
              borderBottom: '1px solid var(--color-line)',
            }}
          >
            <button
              onClick={() => navigate('/settings')}
              className="p-2 rounded-md transition-colors"
              style={{ color: 'var(--color-ink-2)' }}
              aria-label="Settings"
            >
              <Settings size={22} />
            </button>
          </header>

          {/* Outlet — add pb for bottom tab bar on mobile */}
          <main
            className="flex-1 pb-16 md:pb-0"
            style={{ minHeight: 0 }}
          >
            <Outlet />
          </main>
        </div>

        {/* Mobile bottom tab bar */}
        <BottomTabBar />

        {/* iOS PWA install banner (appears above tab bar on iOS Safari first visit) */}
        <IOSInstallBanner />
      </div>
    </TooltipProvider>
  )
}
