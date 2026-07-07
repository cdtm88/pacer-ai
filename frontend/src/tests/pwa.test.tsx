// @vitest-environment jsdom
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { IOSInstallBanner } from '@/components/pwa/IOSInstallBanner'

// Helper: define navigator.userAgent
function setUserAgent(ua: string) {
  Object.defineProperty(navigator, 'userAgent', {
    value: ua,
    configurable: true,
    writable: true,
  })
}

// Helper: mock matchMedia
function setStandalone(standalone: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    value: vi.fn().mockImplementation((query: string) => ({
      matches: query === '(display-mode: standalone)' ? standalone : false,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
    configurable: true,
    writable: true,
  })
}

// Minimal in-memory localStorage mock for environments where jsdom's implementation is incomplete
function makeLocalStorageMock() {
  const store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] ?? null,
    setItem: (key: string, val: string) => { store[key] = val },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { Object.keys(store).forEach(k => delete store[k]) },
  }
}

beforeEach(() => {
  vi.restoreAllMocks()
  // Stub localStorage with a reliable in-memory mock (after restoreAllMocks to avoid being wiped)
  vi.stubGlobal('localStorage', makeLocalStorageMock())
  // Reset ontouchstart
  if ('ontouchstart' in window) {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    delete (window as any).ontouchstart
  }
})

afterEach(() => {
  // Restore the real jsdom localStorage so this file's stub doesn't leak into
  // whichever test file runs next in the same worker (was breaking session.test.tsx).
  vi.unstubAllGlobals()
})

describe('IOSInstallBanner', () => {
  it('does NOT render on a desktop user agent', () => {
    setUserAgent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/120')
    setStandalone(false)
    // No ontouchstart defined

    render(<IOSInstallBanner />)

    expect(screen.queryByText(/Install PacerAI/)).toBeNull()
  })

  it('renders the install copy when iOS conditions are met', () => {
    setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15')
    setStandalone(false)
    // Define ontouchstart to pass Mac Safari exclusion check
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(window as any).ontouchstart = null

    render(<IOSInstallBanner />)

    expect(screen.getByText(/Install PacerAI/)).toBeTruthy()
    expect(screen.getByText('Got it')).toBeTruthy()
  })

  it('clicking "Got it" sets localStorage and hides the banner', () => {
    setUserAgent('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15')
    setStandalone(false)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(window as any).ontouchstart = null

    render(<IOSInstallBanner />)

    const gotIt = screen.getByText('Got it')
    fireEvent.click(gotIt)

    // uiStore's setIOSBannerDismissed writes String(true) = 'true'
    expect(localStorage.getItem('ios-banner-dismissed')).toBe('true')
    expect(screen.queryByText(/Install PacerAI/)).toBeNull()
  })
})
