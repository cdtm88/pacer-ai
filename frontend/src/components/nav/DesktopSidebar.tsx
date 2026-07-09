import { NavLink } from 'react-router'
import { Home, Calendar, TrendingUp, Activity, MessageCircle, Settings } from 'lucide-react'
import { ZONE_SPECTRUM } from '@/lib/zones'

const NAV_ITEMS = [
  { to: '/', label: 'Today', Icon: Home },
  { to: '/agenda', label: 'Agenda', Icon: Calendar },
  { to: '/progress', label: 'Progress', Icon: TrendingUp },
  { to: '/analysis', label: 'Analysis', Icon: Activity },
  { to: '/chat', label: 'Coach', Icon: MessageCircle },
] as const

export function DesktopSidebar() {
  return (
    <aside
      className="hidden md:flex fixed inset-y-0 left-0 flex-col z-40"
      style={{
        width: 240,
        backgroundColor: 'var(--color-surface)',
        borderRight: '1px solid var(--color-line)',
      }}
    >
      {/* Brand mark: app-wide zone-spectrum wordmark, scaled for the sidebar */}
      <div className="px-6 py-6 shrink-0">
        <div
          className="leading-none"
          style={{ fontSize: 20, fontWeight: 700, color: 'var(--color-ink)', letterSpacing: '-0.03em' }}
        >
          Pace
        </div>
        <div
          className="mt-2 h-[3px] w-[52px] rounded-full"
          style={{ background: ZONE_SPECTRUM }}
        />
      </div>

      {/* Main nav */}
      <nav className="flex-1 flex flex-col gap-0.5 px-2">
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className="flex items-center gap-3 px-4 transition-colors"
            style={({ isActive }) => ({
              height: 44,
              borderRadius: 999,
              color: isActive ? 'var(--color-brand)' : 'var(--color-ink-2)',
              backgroundColor: isActive
                ? 'color-mix(in srgb, var(--color-brand) 12%, transparent)'
                : 'transparent',
              fontWeight: 500,
              fontSize: 14,
            })}
          >
            <Icon size={20} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Settings at bottom */}
      <div className="px-2 pb-4 shrink-0">
        <NavLink
          to="/settings"
          className="flex items-center gap-3 px-4 transition-colors"
          style={({ isActive }) => ({
            height: 44,
            borderRadius: 999,
            color: isActive ? 'var(--color-brand)' : 'var(--color-ink-2)',
            backgroundColor: isActive
              ? 'color-mix(in srgb, var(--color-brand) 12%, transparent)'
              : 'transparent',
            fontWeight: 500,
            fontSize: 14,
          })}
        >
          <Settings size={20} />
          Settings
        </NavLink>
      </div>
    </aside>
  )
}
