import { useEffect } from 'react'

export function useWakeLock() {
  useEffect(() => {
    let sentinel: WakeLockSentinel | null = null
    let noSleep: { enable(): void; disable(): void } | null = null

    async function acquire() {
      if ('wakeLock' in navigator) {
        try {
          sentinel = await navigator.wakeLock.request('screen')
        } catch {
          // Battery saver or denied -- fall through to nosleep.js
        }
      }
      // Always try nosleep.js if sentinel not acquired
      // Covers iOS < 18.4 PWA silent-fail (Pitfall 1) and denied requests
      if (!sentinel) {
        const NoSleep = (await import('nosleep.js')).default as {
          new (): { enable(): void; disable(): void }
        }
        noSleep = new NoSleep()
        noSleep.enable()
      }
    }

    const handleVisibility = () => {
      if (!document.hidden) acquire()
    }

    acquire()
    document.addEventListener('visibilitychange', handleVisibility)

    return () => {
      document.removeEventListener('visibilitychange', handleVisibility)
      sentinel?.release()
      noSleep?.disable()
    }
  }, [])
}
