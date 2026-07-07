// RouteErrorFallback: minimal per-route error boundary fallback (item 12, D-09/D-10).
// Rendered via React Router's ErrorBoundary route-config property on each of the
// 5 AppLayout leaf routes. Fills the content pane only; AppLayout's nav shell
// (bottom tab bar / desktop sidebar / header) stays mounted around it.
//
// Per D-09: no error detail, no report action, no error ID — useRouteError() is
// read (so it's available if a future debugging need arises) but never rendered.

import { useRouteError } from 'react-router'

export function RouteErrorFallback() {
  // Read but intentionally never displayed (D-09).
  useRouteError()

  return (
    <div
      className="h-full flex flex-col items-center justify-center"
      style={{ textAlign: 'center', padding: '24px', backgroundColor: 'var(--color-bg)' }}
    >
      <h2 style={{ fontSize: '18px', fontWeight: 600, color: 'var(--color-ink)', margin: '0 0 8px' }}>
        Something went wrong
      </h2>
      <p style={{ fontSize: '15px', fontWeight: 400, color: 'var(--color-ink-2)', margin: '0 0 16px' }}>
        This page ran into a problem.
      </p>
      <button
        onClick={() => window.location.reload()}
        style={{
          padding: '6px 12px',
          borderRadius: '6px',
          border: 'none',
          backgroundColor: 'var(--color-blue-6)',
          color: 'var(--color-surface)',
          fontSize: '14px',
          fontWeight: 600,
        }}
      >
        Reload
      </button>
    </div>
  )
}
