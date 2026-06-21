import { useEffect, useState } from 'react'

// Epoch-based timer. secondsLeft is derived entirely from wall-clock math:
//   secondsLeft = stepDuration - floor((Date.now() - stepStartEpoch) / 1000)
//
// This means the timer is self-correcting: background time counts as elapsed,
// no separate "paused elapsed" tracking is needed, and a page kill + reload
// recovers correctly as long as stepStartEpoch is persisted.
export function useSessionTimer(stepDuration: number, stepStartEpoch: number) {
  const [secondsLeft, setSecondsLeft] = useState(() =>
    Math.max(0, stepDuration - Math.floor((Date.now() - stepStartEpoch) / 1000))
  )

  useEffect(() => {
    const tick = () => {
      setSecondsLeft(
        Math.max(0, stepDuration - Math.floor((Date.now() - stepStartEpoch) / 1000))
      )
    }
    const id = setInterval(tick, 250)
    return () => clearInterval(id)
  }, [stepDuration, stepStartEpoch])

  return { secondsLeft }
}
