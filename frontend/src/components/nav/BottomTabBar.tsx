import { NavLink } from 'react-router'
import { Home, Calendar, TrendingUp, MessageCircle } from 'lucide-react'

const TABS = [
  { to: '/', label: 'Today', Icon: Home },
  { to: '/agenda', label: 'Agenda', Icon: Calendar },
  { to: '/progress', label: 'Progress', Icon: TrendingUp },
  { to: '/chat', label: 'Coach', Icon: MessageCircle },
] as const

export function BottomTabBar() {
  return (
    <nav
      className="shrink-0 w-full md:hidden z-40 flex"
      style={{
        height: 'calc(56px + env(safe-area-inset-bottom))',
        backgroundColor: 'var(--color-surface)',
        borderTop: '1px solid var(--color-line)',
        paddingBottom: 'env(safe-area-inset-bottom)',
      }}
    >
      {TABS.map(({ to, label, Icon }) => (
        <NavLink
          key={to}
          to={to}
          end={to === '/'}
          className="flex-1 flex flex-col items-center justify-center gap-0.5"
          style={({ isActive }) => ({
            color: isActive ? 'var(--color-brand)' : 'var(--color-ink-3)',
          })}
        >
          {({ isActive }) => (
            <>
              <Icon size={24} />
              {isActive && (
                <span
                  className="absolute rounded-full"
                  style={{
                    width: 4,
                    height: 4,
                    backgroundColor: 'var(--color-brand)',
                    marginTop: '-2px',
                  }}
                />
              )}
              <span style={{ fontSize: 10, fontWeight: 500, lineHeight: 1.4 }}>
                {label}
              </span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  )
}
