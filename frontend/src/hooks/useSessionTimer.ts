import { useEffect, useRef, useState, useCallback } from 'react'

export function useSessionTimer(totalSeconds: number) {
  const startRef = useRef<number>(Date.now())
  const pausedElapsedRef = useRef<number>(0)
  const [secondsLeft, setSecondsLeft] = useState(totalSeconds)

  const advance = useCallback(() => {
    startRef.current = Date.now()
    pausedElapsedRef.current = 0
    setSecondsLeft(totalSeconds)
  }, [totalSeconds])

  useEffect(() => {
    startRef.current = Date.now()
    pausedElapsedRef.current = 0

    const tick = () => {
      const elapsed =
        pausedElapsedRef.current +
        Math.floor((Date.now() - startRef.current) / 1000)
      setSecondsLeft(Math.max(0, totalSeconds - elapsed))
    }

    const id = setInterval(tick, 250) // 250ms avoids second-boundary drift

    const handleVisibility = () => {
      if (document.hidden) {
        // Snapshot elapsed-so-far into pausedElapsedRef and reset startRef
        // so that ticks while hidden continue counting correctly against the new start
        pausedElapsedRef.current += Math.floor((Date.now() - startRef.current) / 1000)
        startRef.current = Date.now()
      } else {
        // Coming back visible: add background time into pausedElapsedRef, then reset start
        pausedElapsedRef.current += Math.floor((Date.now() - startRef.current) / 1000)
        startRef.current = Date.now()
      }
    }

    document.addEventListener('visibilitychange', handleVisibility)
    return () => {
      clearInterval(id)
      document.removeEventListener('visibilitychange', handleVisibility)
    }
  }, [totalSeconds])

  return { secondsLeft, advance }
}
