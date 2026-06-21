import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useWakeLock } from '@/hooks/useWakeLock'

// ---------------------------------------------------------------------------
// Mock nosleep.js module
// ---------------------------------------------------------------------------

const mockEnable = vi.fn()
const mockDisable = vi.fn()

vi.mock('nosleep.js', () => {
  return {
    default: class MockNoSleep {
      enable = mockEnable
      disable = mockDisable
    },
  }
})

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function tick() {
  return new Promise<void>((resolve) => setTimeout(resolve, 0))
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('useWakeLock (IOS-01)', () => {
  const originalWakeLock = (navigator as Record<string, unknown>).wakeLock

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    // Restore navigator.wakeLock
    if (originalWakeLock !== undefined) {
      Object.defineProperty(navigator, 'wakeLock', {
        value: originalWakeLock,
        configurable: true,
        writable: true,
      })
    } else {
      // Remove the property if it wasn't originally there
      try {
        Object.defineProperty(navigator, 'wakeLock', {
          value: undefined,
          configurable: true,
          writable: true,
        })
      } catch {
        // ignore
      }
    }
  })

  it('requests native wake lock when available', async () => {
    const mockRelease = vi.fn().mockResolvedValue(undefined)
    const mockRequest = vi.fn().mockResolvedValue({ release: mockRelease })

    Object.defineProperty(navigator, 'wakeLock', {
      value: { request: mockRequest },
      configurable: true,
      writable: true,
    })

    renderHook(() => useWakeLock())
    await tick()

    expect(mockRequest).toHaveBeenCalledWith('screen')
    expect(mockEnable).not.toHaveBeenCalled()
  })

  it('falls back to NoSleep when wakeLock absent', async () => {
    Object.defineProperty(navigator, 'wakeLock', {
      value: undefined,
      configurable: true,
      writable: true,
    })

    expect(() => {
      renderHook(() => useWakeLock())
    }).not.toThrow()

    await tick()

    expect(mockEnable).toHaveBeenCalled()
  })

  it('falls back to NoSleep when request rejects', async () => {
    const mockRequest = vi.fn().mockRejectedValue(new Error('denied'))

    Object.defineProperty(navigator, 'wakeLock', {
      value: { request: mockRequest },
      configurable: true,
      writable: true,
    })

    renderHook(() => useWakeLock())
    await tick()

    expect(mockEnable).toHaveBeenCalled()
  })

  it('releases sentinel and disables NoSleep on unmount', async () => {
    const mockRelease = vi.fn().mockResolvedValue(undefined)
    const mockRequest = vi.fn().mockResolvedValue({ release: mockRelease })

    Object.defineProperty(navigator, 'wakeLock', {
      value: { request: mockRequest },
      configurable: true,
      writable: true,
    })

    const { unmount } = renderHook(() => useWakeLock())
    await tick()

    unmount()

    expect(mockRelease).toHaveBeenCalled()
  })
})
