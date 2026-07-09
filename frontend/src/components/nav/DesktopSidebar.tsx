import { NavLink } from 'react-router'
import { Home, Calendar, TrendingUp, MessageCircle, Settings } from 'lucide-react'

const NAV_ITEMS = [
  { to: '/', label: 'Today', Icon: Home },
  { to: '/agenda', label: 'Agenda', Icon: Calendar },
  { to: '/progress', label: 'Progress', Icon: TrendingUp },
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
      {/* Logotype */}
      <div
        className="px-6 py-6 shrink-0"
        style={{ fontSize: 16, fontWeight: 600, color: 'var(--color-ink)' }}
      >
        PacerAI
      </div>

      {/* Main nav */}
      <nav className="flex-1 flex flex-col gap-0.5 px-2">
        {NAV_ITEMS.map(({ to, label, Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className="flex items-center gap-3 px-4 rounded-md transition-colors"
            style={({ isActive }) => ({
              height: 44,
              color: isActive ? 'var(--color-brand)' : 'var(--color-ink-2)',
              backgroundColor: isActive ? 'var(--color-blue-0)' : 'transparent',
              borderLeft: isActive ? '3px solid var(--color-brand)' : '3px solid transparent',
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
          className="flex items-center gap-3 px-4 rounded-md transition-colors"
          style={({ isActive }) => ({
            height: 44,
            color: isActive ? 'var(--color-brand)' : 'var(--color-ink-2)',
            backgroundColor: isActive ? 'var(--color-blue-0)' : 'transparent',
            borderLeft: isActive ? '3px solid var(--color-brand)' : '3px solid transparent',
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
