// Shared session persistence for iOS PWA page-kill survival.
// Key strategy: store the absolute epoch when each step started.
// On restore, derive elapsed purely from Date.now() - stepStartEpoch.
// This is immune to how long iOS kept the page dead.
//
// sessionStartTimestamp: absolute epoch when the session first started.
// Used to compute total elapsed time across all steps on restore.
//
// freeRideDurationMins: persisted so free-ride sessions survive iOS kill+reopen,
// because freeRideDurationMins in Zustand is ephemeral (wiped on page kill).

export const SESSION_PERSIST_KEY = 'pacer-active-session'

export interface PersistedSession {
  stepIndex: number
  completedDurationSecs: number
  stepStartEpoch: number // absolute ms epoch when current step started
  sessionStartTimestamp: number // absolute ms epoch when the whole session started
  freeRideDurationMins?: number // set for free-ride sessions; undefined for structured
}

export function loadSession(): PersistedSession | null {
  try {
    const raw = localStorage.getItem(SESSION_PERSIST_KEY)
    return raw ? (JSON.parse(raw) as PersistedSession) : null
  } catch {
    return null
  }
}

export function saveSession(s: PersistedSession): void {
  try {
    localStorage.setItem(SESSION_PERSIST_KEY, JSON.stringify(s))
  } catch {
    // QuotaExceededError — nothing we can do
  }
}

export function clearSession(): void {
  try {
    localStorage.removeItem(SESSION_PERSIST_KEY)
  } catch { /* ignore */ }
}

export function hasActiveSession(): boolean {
  return localStorage.getItem(SESSION_PERSIST_KEY) !== null
}
