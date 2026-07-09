import { supabase } from './supabase'

// In production on Vercel the API is served at /api/* on the same origin —
// BASE is always an empty string (same-origin requests, no CORS).
// In dev the Vite proxy strips /api and forwards to localhost:8000.
const BASE = ''

// ---------------------------------------------------------------------------
// Core fetch wrapper: reads current Supabase session and injects JWT
// ---------------------------------------------------------------------------

export async function apiFetch(path: string, options: RequestInit = {}): Promise<Response> {
  const { data } = await supabase.auth.getSession()
  const session = data.session

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${session?.access_token ?? ''}`,
    ...(options.headers as Record<string, string> | undefined),
  }

  return fetch(`${BASE}${path}`, { ...options, headers })
}

// ---------------------------------------------------------------------------
// SSE URL helper: appends ?token= because EventSource cannot send headers
// ---------------------------------------------------------------------------

// WR-006 (item 5, D-04): The browser's EventSource API does not support
// custom request headers, so a credential must ride in the query string for
// SSE endpoints. This is mitigated by exchanging the real Supabase JWT for a
// short-lived (~60s) ephemeral token via POST /chat/token (sent via
// apiFetch's existing Authorization header) -- only that ephemeral token is
// ever carried in the SSE URL, limiting the log-exposure window to ~60s
// instead of the full session lifetime.
export async function sseUrl(path: string): Promise<string> {
  const res = await apiFetch('/api/chat/token', { method: 'POST' })
  if (!res.ok) throw new Error(`chat token exchange failed: ${res.status}`)
  const { token } = await res.json() as { token: string; expires_in: number }
  const sep = path.includes('?') ? '&' : '?'
  return `${BASE}${path}${sep}token=${encodeURIComponent(token)}`
}

// ---------------------------------------------------------------------------
// Typed endpoint helpers
// ---------------------------------------------------------------------------

export interface Profile {
  id: string
  user_id: string
  display_name: string | null
  ftp: number | null
  lthr: number | null
  weight_kg: number | null
  onboarding_complete: boolean
  created_at: string
  updated_at: string
}

export interface SessionStructureSegment {
  duration_minutes: number
  description: string
}

export interface SessionStructure {
  warmup?: SessionStructureSegment
  main_set?: SessionStructureSegment
  cooldown?: SessionStructureSegment
}

export interface Session {
  id: string
  user_id: string
  date: string
  type: string
  status: string
  planned_tss: number | null
  actual_tss: number | null
  notes: string | null
  structure: SessionStructure | null
  scheduled_date: string
}

export interface Ride {
  id: string
  user_id: string
  session_id: string | null
  ride_date: string
  duration_secs: number | null
  np_watts: number | null
  tss: number | null
  avg_power: number | null
  intensity_factor: number | null
  avg_hr: number | null
  avg_cadence: number | null
  ftp_used: number | null
  compliance_pct?: number | null
}

export interface RideStreamPoint {
  t: number
  power: number | null
  heart_rate: number | null
  cadence: number | null
  speed: number | null
  altitude: number | null
  distance: number | null
}

export interface RideZoneDistribution {
  zone: number
  name: string
  seconds: number
  pct: number
}

export interface RideStream {
  series: RideStreamPoint[]
  channels: Record<'power' | 'heart_rate' | 'cadence' | 'speed' | 'altitude' | 'distance', boolean>
  laps: number[]
  hr_zone_distribution: RideZoneDistribution[] | null
}

export interface PmcEntry {
  date: string
  ctl: number
  atl: number
  tsb: number
  tss_display_ready?: boolean
}

export interface Adaptation {
  id: string
  session_id: string
  adaptation_type: string
  description: string
  created_at: string
}

export interface Conversation {
  id: string
  user_id: string
  title: string | null
  created_at: string
  updated_at: string
}

// GET /profiles/me — returns null on 404 (no profile yet, triggers first-run gate)
// Throws an auth error (status 401/403) so callers can redirect to /login.
// Throws a non-auth error for 500/network so callers can show an error state
// instead of silently bouncing the user to /login.
export class AuthError extends Error { status: number; constructor(s: number) { super(`auth error ${s}`); this.status = s } }
export async function getProfileMe(): Promise<Profile | null> {
  const res = await apiFetch('/api/profiles/me')
  if (res.status === 404) return null
  if (res.status === 401 || res.status === 403) throw new AuthError(res.status)
  if (!res.ok) throw new Error(`getProfileMe failed: ${res.status}`)
  return res.json() as Promise<Profile>
}

// GET /sessions/today
export async function getSessionToday(): Promise<Session | null> {
  const res = await apiFetch('/api/sessions/today')
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`getSessionToday failed: ${res.status}`)
  return res.json() as Promise<Session>
}

// GET /sessions/upcoming
export async function getUpcomingSessions(): Promise<Session[]> {
  const res = await apiFetch('/api/sessions/upcoming')
  if (!res.ok) throw new Error(`getUpcomingSessions failed: ${res.status}`)
  const data = await res.json() as { sessions: Session[] }
  return data.sessions ?? []
}

// GET /rides/
export async function getRides(): Promise<Ride[]> {
  const res = await apiFetch('/api/rides/')
  if (!res.ok) throw new Error(`getRides failed: ${res.status}`)
  const data = await res.json() as { rides: Ride[] }
  return data.rides ?? []
}

// GET /rides/{id}/stream
export async function getRideStream(rideId: string): Promise<RideStream> {
  const res = await apiFetch(`/api/rides/${rideId}/stream`)
  if (!res.ok) throw new Error(`getRideStream failed: ${res.status}`)
  return res.json() as Promise<RideStream>
}

// GET /pmc_history/latest
export async function getLatestPmc(): Promise<PmcEntry | null> {
  const res = await apiFetch('/api/pmc_history/latest')
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`getLatestPmc failed: ${res.status}`)
  const data = await res.json() as Record<string, unknown>
  // Empty dict returned when no PMC data exists yet
  if (!data || !data.date) return null
  return data as unknown as PmcEntry
}

// GET /pmc_history/ — up to 30 rows (ascending) for CTL sparkline
export async function getPmcHistory(): Promise<PmcEntry[]> {
  const res = await apiFetch('/api/pmc_history/')
  if (!res.ok) throw new Error(`getPmcHistory failed: ${res.status}`)
  const data = await res.json() as { history: PmcEntry[] }
  return data.history ?? []
}

// GET /adaptations/
export async function getAdaptations(): Promise<Adaptation[]> {
  const res = await apiFetch('/api/adaptations/')
  if (!res.ok) throw new Error(`getAdaptations failed: ${res.status}`)
  return res.json() as Promise<Adaptation[]>
}

// POST /conversations/
// The backend returns {conversation_id: string}; map it onto the id field so
// callers reading conversation.id work with the Conversation interface.
export async function createConversation(title?: string): Promise<Conversation> {
  const res = await apiFetch('/api/conversations/', {
    method: 'POST',
    body: JSON.stringify({ title: title ?? null }),
  })
  if (!res.ok) throw new Error(`createConversation failed: ${res.status}`)
  const data = await res.json() as { conversation_id?: string; id?: string } & Record<string, unknown>
  const id = data.conversation_id ?? data.id
  if (!id) throw new Error('createConversation: backend returned no conversation id')
  return { ...data, id } as unknown as Conversation
}

// GET /conversations/{id}/messages
// Item 4 (D-04): backs the ChatScreen cache-miss reload -- when the client
// query cache is GC'd, the queryFn calls this instead of createConversation
// so prior conversation history is refetched rather than lost.
export async function getConversationMessages(
  conversationId: string
): Promise<{ role: string; content: string }[]> {
  const res = await apiFetch(`/api/conversations/${conversationId}/messages`)
  if (!res.ok) {
    // Surface backend structured error detail (shape: {detail: {error, detail}} or {detail: string})
    let reason = `getConversationMessages failed: ${res.status}`
    try {
      const body = await res.json()
      const d = body?.detail
      const detail = typeof d === 'object' ? d?.detail ?? d?.error : typeof d === 'string' ? d : null
      if (typeof detail === 'string' && detail.length > 0) reason = detail
    } catch { /* JSON parse failed — keep status-code fallback */ }
    throw new Error(reason)
  }
  const data = await res.json() as { messages?: { role: string; content: string }[] }
  return data.messages ?? []
}

// POST /adaptations/sessions/{id}/missed
export async function markSessionMissed(sessionId: string): Promise<void> {
  const res = await apiFetch(`/api/adaptations/sessions/${sessionId}/missed`, {
    method: 'POST',
    body: JSON.stringify({}),
  })
  if (!res.ok) {
    // Surface backend structured error detail (shape: {detail: {error, detail}} or {detail: string})
    let reason = `markSessionMissed failed: ${res.status}`
    try {
      const body = await res.json()
      const d = body?.detail
      const detail = typeof d === 'object' ? d?.detail ?? d?.error : typeof d === 'string' ? d : null
      if (typeof detail === 'string' && detail.length > 0) reason = detail
    } catch { /* JSON parse failed — keep status-code fallback */ }
    throw new Error(reason)
  }
}

// PATCH /sessions/{id} — set status to 'completed'
// Note: Mark Done updates session status to 'completed'; endpoint pattern mirrors missed/status.
export async function markSessionDone(sessionId: string): Promise<void> {
  const res = await apiFetch(`/api/sessions/${sessionId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status: 'completed' }),
  })
  if (!res.ok) {
    // Surface backend structured error detail (shape: {detail: {error, detail}} or {detail: string})
    let reason = `markSessionDone failed: ${res.status}`
    try {
      const body = await res.json()
      const d = body?.detail
      const detail = typeof d === 'object' ? d?.detail ?? d?.error : typeof d === 'string' ? d : null
      if (typeof detail === 'string' && detail.length > 0) reason = detail
    } catch { /* JSON parse failed — keep status-code fallback */ }
    throw new Error(reason)
  }
}

// GET /sessions/{id}/export.zwo — downloads the ZWO workout file as a blob
// Throws a structured Error (carrying the backend error code) on failure so the
// modal can branch on the code for the correct toast copy (D-07).
// Non-iOS uses a hidden anchor + object URL to avoid popup blockers (T-05-13).
// iOS: <a download> is ignored for blob URLs, so a new tab is opened instead
// (user can Share -> "Open in Zwift" from the iOS share sheet). The window
// handle MUST be acquired synchronously, as the very first statement, before
// any await — iOS Safari only treats window.open as user-initiated within the
// synchronous execution window of the click handler; opening it after the
// fetch/blob awaits below would get popup-blocked (item 7).
export async function exportSessionZwo(sessionId: string): Promise<void> {
  const isIOS = /iP(hone|ad|od)/.test(navigator.userAgent)
  const iosWindow = isIOS ? window.open('', '_blank') : null

  try {
    const res = await apiFetch(`/api/sessions/${sessionId}/export.zwo`, {
      headers: { Accept: 'application/xml' },
    })
    if (!res.ok) {
      // Surface backend structured error detail (shape: {detail: {error, detail}} or {detail: string}).
      // Error code is checked first (not detail-first like the other helpers below) so that
      // ZwoExportModal.tsx's `message.includes('session_not_found')` branch stays reachable.
      let reason = `export failed ${res.status}`
      try {
        const body = await res.json()
        const d = body?.detail
        const detail = typeof d === 'object' ? d?.error ?? d?.detail : typeof d === 'string' ? d : null
        if (typeof detail === 'string' && detail.length > 0) reason = detail
      } catch { /* JSON parse failed — keep status-code fallback */ }
      throw new Error(reason)
    }
    const disposition = res.headers.get('Content-Disposition') ?? ''
    const filenameMatch = disposition.match(/filename="?([^";\s]+)"?/)
    const filename = filenameMatch?.[1] ?? 'workout.zwo'

    const blob = new Blob([await res.blob()], { type: 'application/octet-stream' })
    const url = URL.createObjectURL(blob)

    if (iosWindow) {
      // Navigate the already-open (pre-gesture) window handle — do not call
      // window.open again here, that second call happens after the awaits
      // above and would be the exact popup-block bug this fix removes.
      iosWindow.location.href = url
      setTimeout(() => URL.revokeObjectURL(url), 60_000)
      return
    }

    const a = document.createElement('a')
    a.href = url
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  } catch (err) {
    // Don't leave a blank about:blank tab open on export failure.
    iosWindow?.close()
    throw err
  }
}

// Shape returned by POST /rides/upload (not a full Ride object)
export interface UploadRideResponse {
  ride_id: string
  status: string
  // True when the backend short-circuited a byte-identical re-upload
  duplicate?: boolean
}

// POST /rides/upload — multipart upload; do NOT set Content-Type (browser sets multipart boundary)
export async function uploadRide(file: File): Promise<UploadRideResponse> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token ?? ''

  const formData = new FormData()
  formData.append('file', file)

  // Deliberately omit Content-Type header so the browser sets the multipart boundary.
  // Do not append user_id — server infers it from the JWT.
  const res = await fetch(`${BASE}/api/rides/upload`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
    },
    body: formData,
  })
  if (!res.ok) {
    // Surface the backend's structured error detail to the user rather than a bare status code.
    // Backend error shape: {detail: {error: string, detail: string}}
    let reason = `uploadRide failed: ${res.status}`
    try {
      const body = await res.json()
      const backendDetail = body?.detail?.detail
      if (typeof backendDetail === 'string' && backendDetail.length > 0) {
        reason = backendDetail
      }
    } catch {
      // JSON parse failed — keep the status-code fallback
    }
    throw new Error(reason)
  }
  return res.json() as Promise<UploadRideResponse>
}
