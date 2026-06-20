// IOSInstallBanner: shows an install instructional banner on iOS Safari only.
// Conditions: iOS UA + ontouchstart (excludes Mac Safari) + not standalone + not dismissed.
// Dismiss persists to localStorage 'ios-banner-dismissed'.

import { useState } from 'react'
import { useUiStore } from '@/stores/uiStore'

const BANNER_KEY = 'ios-banner-dismissed'

function isIOS(): boolean {
  return /iphone|ipad|ipod/i.test(navigator.userAgent)
}

function isStandalone(): boolean {
  return window.matchMedia('(display-mode: standalone)').matches
}

function isBannerDismissed(): boolean {
  return localStorage.getItem(BANNER_KEY) !== null
}

export function IOSInstallBanner() {
  const setIOSBannerDismissed = useUiStore((s) => s.setIOSBannerDismissed)

  // Gate: iOS UA + ontouchstart (Pitfall 5: excludes Mac Safari) + not standalone + not dismissed
  const shouldShow =
    isIOS() &&
    'ontouchstart' in window &&
    !isStandalone() &&
    !isBannerDismissed()

  const [visible, setVisible] = useState(shouldShow)

  if (!visible) return null

  function handleDismiss() {
    localStorage.setItem(BANNER_KEY, '1')
    setIOSBannerDismissed(true)
    setVisible(false)
  }

  return (
    <div
      role="status"
      aria-live="polite"
      style={{
        position: 'fixed',
        bottom: 'calc(56px + env(safe-area-inset-bottom))',
        left: '1rem',
        right: '1rem',
        backgroundColor: 'var(--color-surface)',
        border: '1px solid var(--color-line)',
        borderRadius: 12,
        padding: '1rem',
        boxShadow: '0 4px 16px rgba(26, 34, 48, 0.12)',
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        gap: '0.75rem',
      }}
    >
      <p
        style={{
          fontSize: 14,
          color: 'var(--color-ink)',
          lineHeight: 1.4,
          flex: 1,
        }}
      >
        Install PacerAI: tap the Share button, then &apos;Add to Home Screen&apos;.
      </p>
      <button
        onClick={handleDismiss}
        style={{
          fontSize: 14,
          fontWeight: 600,
          color: 'var(--color-blue-7)',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '0.25rem 0',
          flexShrink: 0,
        }}
      >
        Got it
      </button>
    </div>
  )
}
