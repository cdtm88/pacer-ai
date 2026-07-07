# Phase 9: Frontend Resilience - Pattern Map

**Mapped:** 2026-07-07
**Files analyzed:** 16 existing files (14 bug-fix items) + 4 new test files
**Analogs found:** All files are self-analogous (bug-fix phase, mostly-existing files) — this document captures exact current code so the planner/executor works from verified state, not assumptions.

**Bug-fix phase note:** Every source file below already exists and is itself the "analog" — the pattern to copy is the file's own existing conventions (styling approach, error-handling shape, query-key usage) applied consistently to the fix. Where a sibling function in the *same* file already does the fix correctly (e.g., `markSessionMissed`'s error parsing vs `exportSessionZwo`'s), that sibling is the analog.

## File Classification

| File | Role | Data Flow | Item(s) | Analog / Self-Reference |
|------|------|-----------|---------|--------------------------|
| `frontend/src/hooks/useSSEStream.ts` | hook | streaming (SSE) | 2 | self — add retry loop inside existing `useEffect` |
| `frontend/src/screens/ChatScreen.tsx` | component/screen | streaming + request-response | 2, 3, 4 | self; `StreamErrorBanner` is new per `09-UI-SPEC.md` |
| `frontend/src/screens/OnboardingScreen.tsx` | component/screen | streaming (fetch+ReadableStream) | 13 | self — mirrors `useSSEStream.ts`'s retry *policy* (not transport) |
| `frontend/src/lib/sessionPersistence.ts` | utility (localStorage) | CRUD (local) | 1 | self — extend `PersistedSession` interface |
| `frontend/src/screens/TodayScreen.tsx` | component/screen | request-response | 1 | consumer of `sessionPersistence.ts`'s new `sessionId`/`date` guard |
| `frontend/src/screens/DuringSessionScreen.tsx` | component/screen | event-driven (timer) | 1, 8 | self — `computeRestoredState` (lines 100-119) is the analog for the live-resume fast-forward fix (lines 219-221) |
| `frontend/src/hooks/useSessionTimer.ts` | hook | event-driven (timer) | 8 | referenced, not modified (epoch math is already correct; overshoot bug is in the consumer effect) |
| `frontend/src/router.tsx` | route config | request-response | 10, 12 | self — `RootProvider`'s `onAuthStateChange` (lines 30-37) is the analog for item 10; React Router `ErrorBoundary` property is new for item 12 |
| `frontend/src/components/AppLayout.tsx` | component (layout) | — (CSS) | 9 | self — `DuringSessionScreen.tsx` (`100dvh` usage, lines 233/282/472/504) is the cross-file analog for the correct height unit |
| `frontend/src/lib/api.ts` | service (fetch wrapper) | request-response + file-I/O | 5, 6, 7, 14 | self — `markSessionMissed`/`markSessionDone`/`uploadRide` (lines 204-320) are the analog for item 6's error-shape parsing |
| `frontend/src/screens/AuthCallbackScreen.tsx` | component/screen | request-response (auth) | 11 | self — `useAuth.ts` is the analog for the "watch the store" pattern to adopt |
| `frontend/src/lib/supabase.ts` | config | — | 11 | referenced, not modified (`detectSessionInUrl: true` already correct) |
| `frontend/src/hooks/useAuth.ts` | hook | event-driven (auth) | 11 | analog source — already implements the correct `/auth/callback` guard + `onAuthStateChange` pattern that `AuthCallbackScreen.tsx` should lean on |
| `frontend/src/components/history/FitUploadZone.tsx` | component | file-I/O | 14 | self — existing `handleUpload`/drag-drop handlers are the analog for adding progress + extension validation |
| `frontend/src/components/history/RideRow.tsx` | component | display/transform | 5 | self — consumer of `Ride` interface fixed in `api.ts` |
| `backend/routes/rides.py` | route (FastAPI) | CRUD | 5 | source of truth — `list_rides` SELECT (lines 628-657) defines the real field contract |
| `frontend/src/tests/history.test.tsx` (NEW) | test | — | 5 | analog: `frontend/src/tests/session.test.tsx` (mock shape, `QueryClientProvider`+`MemoryRouter` wrapper) |
| `frontend/src/components/history/FitUploadZone.test.tsx` (NEW) | test | — | 14 | analog: `frontend/src/tests/session.test.tsx` (vi.mock pattern) + component under test's own `data-testid="fit-upload-zone"` |
| new coverage for item 6 (ZWO error-shape) | test | — | 6 | analog: `frontend/src/tests/chat.test.tsx`'s `vi.mock('@/lib/api', ...)` pattern |
| new coverage for item 12 (router error boundary) | test | — | 12 | analog: `frontend/src/tests/session.test.tsx`'s `MemoryRouter` + `QueryClientProvider` wrapper pattern |

## Pattern Assignments

### `frontend/src/hooks/useSSEStream.ts` (hook, streaming) — Item 2, D-02

**Current code** (lines 23-95, full file, no re-read needed — 95 lines):

Current buggy `error` listener (lines 74-87):
```typescript
es.addEventListener('error', (e: Event) => {
  if (streamCompleted) return // EventSource fires error on normal server close after done
  try {
    const data = JSON.parse((e as MessageEvent).data) as {
      code?: string
      message?: string
    }
    setError(data.message ?? 'Stream error')
  } catch {
    setError('Stream error')
  }
  setIsThinking(false)
  es.close()
})
```

**Fix shape** (from RESEARCH.md Pattern 1, verified against current code): move `EventSource` construction into an `openStream()` function declared inside the `useEffect`, add `retryCount`/`MAX_RETRIES=2`/`BACKOFF_MS=[500,1500]` closure variables, and only call `setError` after retries are exhausted. `streamCompleted` guard (line 75) and the `done` handler (lines 66-71) are unchanged. The backend error payload shape `{"code": "...", "message": "..."}` (already parsed correctly at lines 77-80) needs no change — verified against `backend/routes/_sse.py:131-132`.

**Reset-on-new-url block to preserve** (lines 32-36):
```typescript
setContent('')
setIsDone(false)
setIsThinking(false)
setError(null)
```
`retryCount` must also be reset here (declare it inside the effect body, not as external state, so it naturally resets per new `url`).

---

### `frontend/src/screens/ChatScreen.tsx` (screen, streaming + request-response) — Items 2, 3, 4

**Current imports** (lines 1-6):
```typescript
import { useState, useRef, useEffect, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createConversation, sseUrl } from '../lib/api'
import { useSSEStream } from '../hooks/useSSEStream'
import { ChatBubble, type BubbleRole } from '../components/chat/ChatBubble'
import { ChatInput } from '../components/chat/ChatInput'
```

**Item 3 fix location** — current buggy effect (lines 86-106):
```typescript
useEffect(() => {
  if (isDone && content) {
    setMessages((prev) => [
      ...prev,
      { id: `coach-${Date.now()}`, role: 'coach', content, bubbleRole: detectBubbleRole(content), timestamp: formatTime(new Date()) },
    ])
    setActiveStreamUrl(null)
    setPendingUserMessage(null)
    // WR-008: do NOT invalidate active-conversation here...
  }
}, [isDone, content, queryClient])
```
Exact replacement is given verbatim in RESEARCH.md Pattern 2 — split into "always clear on `isDone`" + "only push message if `content`".

**Item 4 fix location** — `useQuery` conversation cache (lines 62-70):
```typescript
const { data: conversation } = useQuery({
  queryKey: ['active-conversation'],
  queryFn: async () => {
    const conv = await createConversation('Coaching session')
    return conv
  },
  staleTime: Infinity, // Keep the same conversation for the session
})
```
D-04 requires: on cache-miss refetch (after 5min `gcTime`), refetch the *existing* conversation instead of calling `createConversation` again. **Blocking dependency (RESEARCH.md note):** verify a `GET /conversations/{id}` read endpoint exists in the backend before scoping this task — not confirmed in this research pass. If it exists, persist the conversation id (e.g., localStorage) so the `queryFn` can branch: `if (persistedId) return getConversation(persistedId); else return createConversation(...)`.

**Item 2 consumer side** — `error` from `useSSEStream` (line 77) currently only renders a static banner (lines 206-223):
```typescript
{error && (
  <div style={{ padding: '8px 16px', backgroundColor: 'var(--color-warm-soft)', borderTop: '1px solid var(--color-amber)' }}>
    <span style={{ fontSize: '13px', color: 'var(--color-warn)' }}>
      Connection lost. Reconnecting...
    </span>
  </div>
)}
```
Per D-02 and Pitfall 3, this must become the new `StreamErrorBanner` component (per `09-UI-SPEC.md`) with a manual **Retry** button that re-derives `activeStreamUrl` from `sseUrl(...)` using the last sent message (track via existing `_pendingUserMessage`/`setPendingUserMessage` state, lines 74/100/121, already present but currently underused — the `_` prefix signals it's presently unread outside the setter).

**`isStreaming` derivation to preserve** (line 132): `const isStreaming = activeStreamUrl !== null && !isDone` — item 3's fix must still make this resolve to `false` once `activeStreamUrl` is nulled.

**`handleSend` guard to preserve** (line 110): `if (!conversation?.id || activeStreamUrl) return` — this is exactly the guard that item 3 unbricks by ensuring `activeStreamUrl` always clears on `isDone`.

---

### `frontend/src/screens/OnboardingScreen.tsx` (screen, streaming via fetch+ReadableStream) — Item 13, D-05

**Current stream-error handling in `runStream`** (lines 154-158, 217-221, 230-234):
```typescript
if (!res.ok || !res.body) {
  setStreamError('Could not connect to coach. Try again.')
  setIsStreaming(false)
  return
}
...
} else if (event.type === 'error') {
  const msg = (event.data.message as string) ?? 'Stream error'
  setStreamError(msg)
  setIsStreaming(false)
}
...
} catch (err) {
  if ((err as Error).name === 'AbortError') return
  setStreamError('Connection lost. Please try again.')
  setIsStreaming(false)
}
```
**No retry currently exists at all** — every failure path sets `streamError` immediately (spinner sticks per D-05's problem description... actually here it's the opposite: `isStreaming` clears, but `streamError` never offers a Retry action, and the confirm-stream path (`handleConfirm`, lines 274-366) has the *same* three failure shapes duplicated with **no** `setStreamError` call at all on its `!res.ok` branch (line 317-321) — it silently falls through to `pollForProfile()`, which is the "sticks forever" bug D-05 describes for the confirm step specifically).

**Fix shape (per RESEARCH.md Pitfall 1 + Open Question 1):** duplicate the same `retryCount`/`MAX_RETRIES`/`BACKOFF_MS` loop structure from `useSSEStream.ts` inside `runStream`'s catch/error branches (both the initial-message path and `handleConfirm`'s confirm-stream path), with a cross-reference comment `// Mirrors the retry policy in useSSEStream.ts — keep behavior in sync`. Render the same new `StreamErrorBanner` component in place of the current static error block (lines 528-547):
```typescript
{streamError && (
  <div style={{ padding: '8px 12px', marginTop: '8px', backgroundColor: 'var(--color-warm-soft)', border: '1px solid var(--color-amber)', borderRadius: '8px' }}>
    <span style={{ fontSize: '13px', color: 'var(--color-warn)' }}>
      Connection lost. Reconnecting...
    </span>
  </div>
)}
```

**Do not import `useSSEStream` here** — `EventSource` cannot do POST + `Authorization` headers (see `parseSSELine`/manual reader at lines 160-229, which exists specifically because of this constraint, cross-referenced at lines 42-44).

---

### `frontend/src/lib/sessionPersistence.ts` (utility, CRUD-local) — Item 1, D-06

**Current full interface** (lines 14-20):
```typescript
export interface PersistedSession {
  stepIndex: number
  completedDurationSecs: number
  stepStartEpoch: number // absolute ms epoch when current step started
  sessionStartTimestamp: number // absolute ms epoch when the whole session started
  freeRideDurationMins?: number // set for free-ride sessions; undefined for structured
}
```
**Fix:** add `sessionId: string` and `date: string` (today's date, `YYYY-MM-DD`) fields. `loadSession()`/`saveSession()`/`clearSession()`/`hasActiveSession()` (lines 22-47) are pure read/write/remove wrappers — no logic change needed inside this file itself; the mismatch-check (compare `sessionId`+`date` against today's actual session) belongs in the **consumer** (`TodayScreen.tsx`'s `hasActiveSession()` call, line 40, and `DuringSessionScreen.tsx`'s `loadSession()` call, line 457/computeRestoredState line 150) — silently call `clearSession()` there on mismatch, no dialog/toast per D-06.

**`saveSession` callers to update with new fields** — `DuringSessionScreen.tsx` lines 183-189 (`goNext`) and line 194 (`buildPayload`, lines 167-173) both construct the persisted payload; both call sites must include `sessionId`/`date` going forward.

---

### `frontend/src/screens/TodayScreen.tsx` (screen, request-response) — Item 1 consumer

**Current stale-session-hijack code** (lines 39-43):
```typescript
useEffect(() => {
  if (hasActiveSession()) {
    navigate('/session', { replace: true })
  }
}, [navigate])
```
This unconditionally redirects on *any* persisted session, regardless of whether it matches today's real session. Fix: after `session` (from `useQuery(['session','today'])`, lines 45-53) loads, compare `loadSession()?.sessionId`/`.date` against `session.id`/today's date; if mismatched, `clearSession()` silently and do not redirect.

---

### `frontend/src/screens/DuringSessionScreen.tsx` (screen, event-driven timer) — Items 1, 8

**Reload-path fast-forward (already correct, the analog)** — `computeRestoredState` (lines 100-119):
```typescript
function computeRestoredState(saved: PersistedSession | null, steps: SessionStep[]): RestoredState {
  const now = Date.now()
  if (!saved || saved.stepIndex >= steps.length) {
    return { stepIndex: 0, completedDurationSecs: 0, stepStartEpoch: now, sessionStartTimestamp: now }
  }
  let stepIndex = saved.stepIndex
  let completedDurationSecs = saved.completedDurationSecs
  let elapsedInStepMs = now - saved.stepStartEpoch
  while (stepIndex < steps.length) {
    const stepTotalMs = steps[stepIndex].duration * 60 * 1000
    if (elapsedInStepMs < stepTotalMs) break
    completedDurationSecs += steps[stepIndex].duration * 60
    elapsedInStepMs -= stepTotalMs
    stepIndex++
  }
  const sessionStartTimestamp = saved.sessionStartTimestamp ?? now - (completedDurationSecs * 1000) - elapsedInStepMs
  return { stepIndex, completedDurationSecs, stepStartEpoch: now - elapsedInStepMs, sessionStartTimestamp }
}
```

**Live-path bug (item 8)** — the effect that fires exactly one `goNext()` (lines 219-221):
```typescript
useEffect(() => {
  if (!isDone && secondsLeft === 0 && stepDuration > 0) goNext()
}, [secondsLeft, isDone, stepDuration, goNext])
```
and `goNext` itself (lines 175-190) always advances exactly one step with a fresh full-duration `stepStartEpoch = Date.now()`, with no fast-forward awareness.

**Fix (per RESEARCH.md Pattern 5):** extract the `while` loop body from `computeRestoredState` (lines 108-114) into a shared helper `fastForwardSteps(stepIndex, completedDurationSecs, stepStartEpoch, steps, now)`; `computeRestoredState` calls it once on mount with `saved.stepStartEpoch`; the `secondsLeft === 0` effect calls it with the *current* `stepStartEpoch` state instead of calling bare `goNext()`, then applies the result via the same `setState` + `saveSession(...)` pattern already used in `goNext` (lines 180-189).

**Item 1 consumer side** — `restoredRef.current = computeRestoredState(loadSession(), steps)` (line 150) and `loadSession()` at line 457 in the outer `DuringSessionScreen` component — both need the sessionId/date staleness check applied before trusting `loadSession()`'s output (see `sessionPersistence.ts` entry above).

---

### `frontend/src/router.tsx` (route config) — Items 10, 12

**Item 10 current code** (lines 30-37, exact fix location per Pitfall 5 — add only `'SIGNED_IN'`, not `'TOKEN_REFRESHED'`/`'INITIAL_SESSION'`):
```typescript
useEffect(() => {
  const { data: { subscription } } = supabase.auth.onAuthStateChange((event) => {
    if (event === 'SIGNED_OUT' || event === 'USER_UPDATED') {
      queryClient.clear()
    }
  })
  return () => subscription.unsubscribe()
}, [queryClient])
```
Fix: `if (event === 'SIGNED_OUT' || event === 'USER_UPDATED' || event === 'SIGNED_IN')`.

**Item 12 — current route tree leaves needing `ErrorBoundary`** (lines 172-193, the `AppLayout` children):
```typescript
element: <AppLayout />,
children: [
  { index: true, element: <TodayScreen /> },
  { path: 'agenda', element: <AgendaScreen /> },
  { path: 'history', element: <HistoryScreen /> },
  { path: 'chat', element: <ChatScreen /> },
  { path: 'settings', element: <SettingsScreen /> },
],
```
Fix: add `ErrorBoundary: RouteErrorFallback` to each of the 5 leaf route objects (exact pattern given in RESEARCH.md Pattern 3). `RouteErrorFallback` and `ErrorBoundaryFallback.tsx` are new files (`frontend/src/components/ErrorBoundaryFallback.tsx` per the RESEARCH.md project-structure section) — no existing analog in-repo; build per D-09 spec (minimal "Something went wrong" + reload button, `useRouteError()` imported but unused for display).

---

### `frontend/src/components/AppLayout.tsx` (layout, CSS) — Item 9

**Current buggy height chain** (lines 13-16, 21):
```typescript
<div
  className="min-h-screen"
  style={{ backgroundColor: 'var(--color-bg)' }}
>
  ...
  <div className="md:ml-60 flex flex-col min-h-screen">
```
**Fix:** `min-h-screen` → `h-dvh` on both divs (line 14 and line 21), per Pitfall 4. Cross-file analog for the `dvh` convention already established in this codebase: `frontend/src/screens/DuringSessionScreen.tsx` lines 233, 282, 472, 504 (`minHeight: '100dvh'`).

**`<main>` element to leave largely as-is** (lines 41-46, `style={{ minHeight: 0 }}` + `flex-1` — this is already correct flex-scroll-pane setup; the outer `min-h-screen`→`h-dvh` swap is what unlocks it):
```typescript
<main className="flex-1 pb-16 md:pb-0" style={{ minHeight: 0 }}>
  <Outlet />
</main>
```

---

### `frontend/src/lib/api.ts` (service, fetch wrapper) — Items 5, 6, 7, 14

**Item 5 — `Ride` interface** (lines 82-95) and its correct backend source (`backend/routes/rides.py` `list_rides`, verified SELECT list, lines 645-649):
```python
.select(
    "id, user_id, tss, np_watts, intensity_factor, duration_secs, "
    "ride_date, avg_power, avg_hr, avg_cadence, ftp_used, "
    "session_id, compliance_pct"
)
```
Exact before/after interface diff is given verbatim in RESEARCH.md's "Ride interface field-name alignment" code example — copy that directly.

**Item 6 — analog pattern already correct elsewhere in this same file** (`markSessionMissed`, lines 204-220):
```typescript
export async function markSessionMissed(sessionId: string): Promise<void> {
  const res = await apiFetch(`/api/adaptations/sessions/${sessionId}/missed`, { method: 'POST', body: JSON.stringify({}) })
  if (!res.ok) {
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
```
**Item 6's actual buggy code** (`exportSessionZwo`, lines 250-253 — the outlier that never got this treatment):
```typescript
if (!res.ok) {
  const err = await res.json().catch(() => ({})) as { error?: string }
  throw new Error(err?.error ?? `export failed ${res.status}`)
}
```
Apply the same `body?.detail?.error`/`body?.detail?.detail` shape as `markSessionMissed`/`markSessionDone`/`uploadRide`.

**Item 7 — current `exportSessionZwo` full body** (lines 246-277), including the `isIOS` `window.open()` branch (lines 263-268) vs the non-iOS hidden-anchor path (lines 270-276) already in the same function:
```typescript
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
```
Per RESEARCH.md Open Question 2, verify empirically whether `<a download>` works for blob URLs on current iOS Safari before deciding: either drop the `isIOS` branch (use anchor-click path unconditionally) or restructure to call `window.open()` synchronously inside `onClick` before any `await`. The anchor-click path (already the non-iOS default in this same function) is the preferred analog if verification succeeds.

**Item 14 invalidation list to extend beyond `['rides']`** — currently only `FitUploadZone.tsx` calls `queryClient.invalidateQueries({ queryKey: ['rides'] })` (line 31 of that file, not `api.ts`); per Pitfall 2, the full list must be `['rides']`, `['pmc', 'latest']`, `['pmc-history']`, `['session', 'today']`, `['sessions', 'upcoming']` — verified against `TodayScreen.tsx` (`['pmc', 'latest']` line 58, `['session', 'today']` line 51, `['sessions', 'upcoming']` line 65) and `HistoryScreen.tsx:40` (`['pmc-history']`, not read in this pass but cited by RESEARCH.md — confirm exact key before finalizing).

---

### `frontend/src/screens/AuthCallbackScreen.tsx` + `frontend/src/hooks/useAuth.ts` — Item 11, D-11(discretion)

**Current double-exchange code to delete** (`AuthCallbackScreen.tsx` lines 27-48):
```typescript
const code = new URLSearchParams(search).get('code')
if (code) {
  supabase.auth
    .exchangeCodeForSession(code)
    .then(({ data, error }) => {
      if (error) {
        navigate('/login', { replace: true })
      } else {
        useAuthStore.getState().setAuth({ session: data.session, user: data.session.user, isLoading: false })
        navigate('/', { replace: true })
      }
    })
  return
}
```
**Analog to lean on instead** — `useAuth.ts`'s existing `/auth/callback` guard (lines 16-32) and global `onAuthStateChange` subscription (lines 45-54):
```typescript
const onAuthCallback = window.location.pathname === '/auth/callback'
supabase.auth.getSession().then(({ data: { session: initialSession } }) => {
  if (!active) return
  if (onAuthCallback && initialSession === null) return
  setAuth({ session: initialSession, user: initialSession?.user ?? null, isLoading: false })
})
const { data: { subscription } } = supabase.auth.onAuthStateChange((event, newSession) => {
  if (newSession === null && event === 'INITIAL_SESSION') return
  setAuth({ session: newSession, user: newSession?.user ?? null, isLoading: false })
})
```
**Fix:** delete the manual `exchangeCodeForSession` branch entirely; `AuthCallbackScreen.tsx` should instead watch `useAuthStore` (poll or subscribe) for a session to appear (populated automatically by `useAuth.ts`'s existing `onAuthStateChange` once `detectSessionInUrl` resolves the code in the background), then `navigate('/', { replace: true })`; add a ~5-8s timeout fallback to `/login`. The implicit-flow branch (lines 50-71, `hasImplicitTokens`) is not part of this bug and can be left as-is or simplified for consistency (not required).

**`supabase.ts` — confirmed correct, no change** (lines 5-15): `detectSessionInUrl: true` is already set; this is the config that makes the fix work.

---

### `frontend/src/components/history/FitUploadZone.tsx` (component, file-I/O) — Item 14

**Current `handleUpload`** (lines 20-39):
```typescript
async function handleUpload(file: File) {
  if (isUploading) return
  setIsUploading(true)
  try {
    const result = await uploadRide(file)
    if (result.duplicate) {
      toast.info('This ride is already uploaded. No duplicate was created.')
      return
    }
    toast.success('Ride uploaded. History updated.')
    await queryClient.invalidateQueries({ queryKey: ['rides'] })
  } catch (err) {
    const message = err instanceof Error ? err.message : 'Unknown error'
    toast.error(`Upload failed. ${message}. Try again.`)
  } finally {
    setIsUploading(false)
  }
}
```
Fix: extend the invalidation list per Pitfall 2 (see `api.ts` section above); `isUploading` boolean already exists and drives a spinner (lines 121-136) — extend to a numeric progress value if using `XMLHttpRequest.upload.onprogress` (native `fetch` in `uploadRide` — `api.ts` lines 288-320 — does not support progress events; may need to switch `uploadRide`'s transport to `XMLHttpRequest` for real progress, or use an indeterminate progress bar as a lower-risk alternative).

**Current drag-drop handler — missing `.fit` extension validation** (lines 51-58):
```typescript
function handleDrop(e: DragEvent<HTMLDivElement>) {
  e.preventDefault()
  setIsDragOver(false)
  const file = e.dataTransfer.files[0]
  if (file) {
    void handleUpload(file)
  }
}
```
Compare to the file-picker path which is validated via the `<input accept=".fit">` attribute (line 86) — browsers do not enforce `accept` on drag-drop. Fix: add a `file.name.toLowerCase().endsWith('.fit')` check in `handleDrop` before calling `handleUpload`, with a `toast.error(...)` (matching the existing `toast` import, line 3) on rejection — mirrors the existing `toast.error` shape in the `catch` block (line 35).

---

### `frontend/src/components/history/RideRow.tsx` (component, display) — Item 5 consumer

**Call sites requiring the field rename** (verified current line numbers):
- Line 103: `formatDate(ride.ride_date ?? ride.created_at)` → `formatDate(ride.ride_date)` (per RESEARCH.md, `ride_date` is always populated, `created_at` is not selected by the backend)
- Line 126: `formatDuration(ride.duration_seconds ?? null)` → `formatDuration(ride.duration_secs ?? null)`
- Line 167: `ride.avg_power_watts != null` → `ride.avg_power != null`
- Line 184: `Math.round(ride.avg_power_watts)` → `Math.round(ride.avg_power)`
- Line 209: `ride.duration_seconds != null` → `ride.duration_secs != null`
- Line 226: `formatDuration(ride.duration_seconds)` → `formatDuration(ride.duration_secs)`
- Lines 305-315: delete the `{ride.file_name && (...)}` block entirely (dead code — `file_name` is never returned by the backend):
```typescript
{ride.file_name && (
  <p style={{ margin: 0, fontSize: '12px', color: 'var(--color-ink-3)' }}>
    Source: {ride.file_name}
  </p>
)}
```

---

## Shared Patterns

### SSE retry-then-terminal-error state machine (Items 2, 13)
**Source:** `frontend/src/hooks/useSSEStream.ts` (canonical implementation, `EventSource` transport)
**Applied in parallel (not shared code) to:** `frontend/src/screens/OnboardingScreen.tsx`'s `runStream`/`handleConfirm` (fetch+ReadableStream transport)
**Do not literally import/share the hook** — see RESEARCH.md Pitfall 1. Both implement: 1-2 silent retries with `[500, 1500]`ms backoff → terminal error state → clear stream-open state + re-enable input → render `StreamErrorBanner` with manual Retry.

### Backend structured error-detail parsing (`{detail: {error, detail}}`)
**Source:** `frontend/src/lib/api.ts` — `markSessionMissed` (lines 204-220), `markSessionDone` (lines 224-240), `uploadRide` (lines 304-318)
**Apply to:** `exportSessionZwo` (item 6) — the one function in this file that still uses the wrong `err.error` shape.
```typescript
let reason = `<fn> failed: ${res.status}`
try {
  const body = await res.json()
  const d = body?.detail
  const detail = typeof d === 'object' ? d?.detail ?? d?.error : typeof d === 'string' ? d : null
  if (typeof detail === 'string' && detail.length > 0) reason = detail
} catch { /* JSON parse failed — keep status-code fallback */ }
throw new Error(reason)
```

### `100dvh` viewport-height unit (iOS Safari safe)
**Source:** `frontend/src/screens/DuringSessionScreen.tsx` lines 233, 282, 472, 504 (`minHeight: '100dvh'`)
**Apply to:** `frontend/src/components/AppLayout.tsx` lines 14, 21 (`min-h-screen` → `h-dvh` Tailwind utility — same unit, different syntax since AppLayout uses Tailwind classes not inline styles).

### `onAuthStateChange` event-taxonomy awareness
**Source:** `frontend/src/hooks/useAuth.ts` line 48 — `if (newSession === null && event === 'INITIAL_SESSION') return`
**Apply to:** `frontend/src/router.tsx` lines 30-37 — add `'SIGNED_IN'` to the OR-chain, explicitly excluding `'TOKEN_REFRESHED'`/`'INITIAL_SESSION'` (Pitfall 5).

### Absolute-epoch persistence (`Date.now()`, not relative counters)
**Source:** `frontend/src/lib/sessionPersistence.ts` (whole-file pattern, already Phase 5-proven) + `frontend/src/hooks/useSessionTimer.ts` (epoch-derived `secondsLeft`)
**Apply to:** the `sessionId`/`date` fields added for item 1 — store as plain values compared against `Date.now()`-derived "today" string, consistent with existing `stepStartEpoch`/`sessionStartTimestamp` epoch fields.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/components/chat/StreamErrorBanner.tsx` (NEW) | component | — | No existing shared error-banner component in the codebase; both `ChatScreen.tsx` and `OnboardingScreen.tsx` currently inline their own static banner markup (shown above) — build per `09-UI-SPEC.md` spec, using the existing inline banners' color tokens (`--color-warm-soft`, `--color-amber`, `--color-warn`) as the visual analog |
| `frontend/src/components/ErrorBoundaryFallback.tsx` (NEW) | component | — | No existing error-boundary component anywhere in this codebase (first use of React Router's `ErrorBoundary` route property in this project) — build per D-09 spec (minimal message + reload button) |
| `frontend/src/tests/FitUploadZone.test.tsx` (NEW) | test | — | No test file exists for `FitUploadZone.tsx` yet — use `frontend/src/tests/session.test.tsx`'s `vi.mock('@/lib/api', ...)` + `QueryClientProvider` wrapper pattern (lines 1-49 shown above) as the structural analog, adapted for `uploadRide`/`toast` mocks |
| `frontend/src/tests/history.test.tsx` (NEW) | test | — | No test file exists for `RideRow.tsx`/history list — same `session.test.tsx` wrapper pattern applies; mock `getRides` returning the corrected `Ride` shape (post item-5 fix) |
| new test coverage for router `ErrorBoundary` (item 12) | test | — | No existing router-tree render test in this codebase — closest structural analog is `frontend/src/tests/chat.test.tsx`'s `MemoryRouter` wrapper (line 4) combined with a throwing test component rendered at a route leaf |

## Metadata

**Analog search scope:** `frontend/src/hooks/`, `frontend/src/screens/`, `frontend/src/lib/`, `frontend/src/components/`, `frontend/src/router.tsx`, `frontend/src/tests/`, `backend/routes/rides.py`
**Files scanned:** 16 source files fully read (all ≤ 562 lines, single-pass reads, no re-reads), plus targeted greps of `backend/routes/rides.py` (SELECT clause) and `frontend/src/tests/{chat,session}.test.tsx` (mock/wrapper structure)
**Pattern extraction date:** 2026-07-07
