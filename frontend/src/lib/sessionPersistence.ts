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
//
// sessionId + date: identity fields (item 1, D-06). A persisted record only
// belongs to "today's active session" if both match today's real session; a
// stale record from a previous day or a different session must never hijack
// Today or resume the wrong session. See loadMatchingSession below.

export const SESSION_PERSIST_KEY = 'pacer-active-session'

export interface PersistedSession {
  sessionId: string | null // the linked session's id; null for a free ride with no scheduled session
  date: string // YYYY-MM-DD, the local date this record was persisted on
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

// Today's local date as YYYY-MM-DD, matching the format stored in PersistedSession.date.
export function todayDateString(): string {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Returns the persisted session only if it belongs to today's real session (same id + date).
// A mismatched (stale) record — a different session, or a different day — must never be
// trusted as the active session: it is silently discarded (clearSession; no dialog/toast
// per D-06) so the caller can render/resume real current state instead.
export function loadMatchingSession(currentSessionId: string | null): PersistedSession | null {
  const persisted = loadSession()
  if (!persisted) return null
  if (persisted.sessionId !== currentSessionId || persisted.date !== todayDateString()) {
    clearSession()
    return null
  }
  return persisted
}
