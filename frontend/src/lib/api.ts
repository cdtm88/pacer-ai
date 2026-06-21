import { supabase } from './supabase'

const BASE = import.meta.env.VITE_API_URL

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

// WR-006 KNOWN LIMITATION: The JWT is embedded as a query parameter because
// the browser's EventSource API does not support custom request headers. This
// causes the full access token to appear in Uvicorn/Nginx/CDN access logs.
// TODO: Mitigate by implementing a short-lived token exchange endpoint:
//   POST /chat/token (with Authorization header) -> returns an opaque 60s token.
//   The SSE URL uses only the ephemeral token, limiting the log-exposure window.
export async function sseUrl(path: string): Promise<string> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token ?? ''
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
  file_name: string
  ride_date: string
  duration_seconds: number | null
  distance_m: number | null
  np_watts: number | null
  tss: number | null
  avg_power_watts: number | null
  compliance_pct?: number | null
  created_at: string
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

export interface CalendarSettings {
  connected: boolean
}

// GET /profiles/me — returns null on 404 (no profile yet, triggers first-run gate)
// Throws an auth error (status 401/403) so callers can redirect to /login.
// Throws a non-auth error for 500/network so callers can show an error state
// instead of silently bouncing the user to /login.
export class AuthError extends Error { status: number; constructor(s: number) { super(`auth error ${s}`); this.status = s } }
export async function getProfileMe(): Promise<Profile | null> {
  const res = await apiFetch('/profiles/me')
  if (res.status === 404) return null
  if (res.status === 401 || res.status === 403) throw new AuthError(res.status)
  if (!res.ok) throw new Error(`getProfileMe failed: ${res.status}`)
  return res.json() as Promise<Profile>
}

// GET /sessions/today
export async function getSessionToday(): Promise<Session | null> {
  const res = await apiFetch('/sessions/today')
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`getSessionToday failed: ${res.status}`)
  return res.json() as Promise<Session>
}

// GET /sessions/upcoming
export async function getUpcomingSessions(): Promise<Session[]> {
  const res = await apiFetch('/sessions/upcoming')
  if (!res.ok) throw new Error(`getUpcomingSessions failed: ${res.status}`)
  const data = await res.json() as { sessions: Session[] }
  return data.sessions ?? []
}

// GET /rides/
export async function getRides(): Promise<Ride[]> {
  const res = await apiFetch('/rides/')
  if (!res.ok) throw new Error(`getRides failed: ${res.status}`)
  const data = await res.json() as { rides: Ride[] }
  return data.rides ?? []
}

// GET /pmc_history/latest
export async function getLatestPmc(): Promise<PmcEntry | null> {
  const res = await apiFetch('/pmc_history/latest')
  if (res.status === 404) return null
  if (!res.ok) throw new Error(`getLatestPmc failed: ${res.status}`)
  const data = await res.json() as Record<string, unknown>
  // Empty dict returned when no PMC data exists yet
  if (!data || !data.date) return null
  return data as unknown as PmcEntry
}

// GET /pmc_history/ — up to 30 rows (ascending) for CTL sparkline
export async function getPmcHistory(): Promise<PmcEntry[]> {
  const res = await apiFetch('/pmc_history/')
  if (!res.ok) throw new Error(`getPmcHistory failed: ${res.status}`)
  const data = await res.json() as { history: PmcEntry[] }
  return data.history ?? []
}

// GET /adaptations/
export async function getAdaptations(): Promise<Adaptation[]> {
  const res = await apiFetch('/adaptations/')
  if (!res.ok) throw new Error(`getAdaptations failed: ${res.status}`)
  return res.json() as Promise<Adaptation[]>
}

// POST /conversations/
// The backend returns {conversation_id: string}; map it onto the id field so
// callers reading conversation.id work with the Conversation interface.
export async function createConversation(title?: string): Promise<Conversation> {
  const res = await apiFetch('/conversations/', {
    method: 'POST',
    body: JSON.stringify({ title: title ?? null }),
  })
  if (!res.ok) throw new Error(`createConversation failed: ${res.status}`)
  const data = await res.json() as { conversation_id?: string; id?: string } & Record<string, unknown>
  return { ...data, id: data.conversation_id ?? data.id ?? '' } as unknown as Conversation
}

// POST /adaptations/sessions/{id}/missed
export async function markSessionMissed(sessionId: string): Promise<void> {
  const res = await apiFetch(`/adaptations/sessions/${sessionId}/missed`, {
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
  const res = await apiFetch(`/sessions/${sessionId}`, {
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
// Uses a hidden anchor + object URL (not window.open) to avoid popup blockers (T-05-13).
export async function exportSessionZwo(sessionId: string): Promise<void> {
  const res = await apiFetch(`/sessions/${sessionId}/export.zwo`, {
    headers: { Accept: 'application/xml' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { error?: string }
    throw new Error(err?.error ?? `export failed ${res.status}`)
  }
  const disposition = res.headers.get('Content-Disposition') ?? ''
  const filenameMatch = disposition.match(/filename="?([^";\s]+)"?/)
  const filename = filenameMatch?.[1] ?? 'workout.zwo'

  const blob = new Blob([await res.blob()], { type: 'application/octet-stream' })
  const url = URL.createObjectURL(blob)

  // iOS Safari ignores <a download> for blob URLs — open in new tab so user
  // can Share → "Open in Zwift" from the iOS share sheet.
  const isIOS = /iP(hone|ad|od)/.test(navigator.userAgent)
  if (isIOS) {
    window.open(url, '_blank')
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
}

// Shape returned by POST /rides/upload (not a full Ride object)
export interface UploadRideResponse {
  ride_id: string
  status: string
}

// POST /rides/upload — multipart upload; do NOT set Content-Type (browser sets multipart boundary)
export async function uploadRide(file: File): Promise<UploadRideResponse> {
  const { data } = await supabase.auth.getSession()
  const token = data.session?.access_token ?? ''

  const formData = new FormData()
  formData.append('file', file)

  // Deliberately omit Content-Type header so the browser sets the multipart boundary.
  // Do not append user_id — server infers it from the JWT.
  const res = await fetch(`${BASE}/rides/upload`, {
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

// GET /calendar/settings
export async function getCalendarSettings(): Promise<CalendarSettings> {
  const res = await apiFetch('/calendar/settings')
  if (!res.ok) throw new Error(`getCalendarSettings failed: ${res.status}`)
  return res.json() as Promise<CalendarSettings>
}

// POST /calendar/disconnect
export async function disconnectCalendar(): Promise<void> {
  const res = await apiFetch('/calendar/disconnect', {
    method: 'POST',
    body: JSON.stringify({}),
  })
  if (!res.ok) throw new Error(`disconnectCalendar failed: ${res.status}`)
}
