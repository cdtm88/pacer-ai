# Phase 13: Close gap ADAPT-04/TRANSP-03 - Pattern Map

**Mapped:** 2026-07-10
**Files analyzed:** 8 (2 edited existing + 1 fixed interface, 2 new source files, 3 test files)
**Analogs found:** 8 / 8 (all in-repo, frontend-only phase)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `frontend/src/lib/api.ts` (fix `Adaptation` interface + add `checkAdaptations()`) | service (API client) | request-response | Same file: `createConversation()` (POST wrapper) + `getRides()` (GET wrapper) | exact (same file, same conventions) |
| `frontend/src/hooks/useAdaptationCheck.ts` (new) | hook | event-driven (mount-once, fire-and-forget) | `frontend/src/lib/sessionPersistence.ts` (localStorage safety wrapper) + `frontend/src/router.tsx`'s `RootProvider` (mount-once useEffect) | role-match (no existing "hooks/" dir precedent, but exact pattern precedent exists) |
| `frontend/src/components/AppLayout.tsx` (edit: call `useAdaptationCheck()`) | component (layout) | event-driven | Same file, existing structure | exact (editing in place) |
| `frontend/src/screens/ProgressScreen.tsx` (edit: add Adaptations section) | component (screen section) | CRUD (read-only list) | Same file's existing "4. Ride log" section | exact (same file, same pattern to replicate) |
| `frontend/src/lib/format.ts` (add `formatDate` export + trigger-humanization map) | utility | transform | Same file's `ZONE_LABELS`/`sessionTypeLabel` pattern; `RideRow.tsx`'s private `formatDate` | exact (extraction of existing pattern) |
| `frontend/src/tests/progress.test.tsx` (new) | test | request-response (rendering) | `frontend/src/tests/history.test.tsx` (`vi.mock('../lib/api')` + `QueryClientProvider` wrapper pattern) | exact |
| `frontend/src/tests/useAdaptationCheck.test.ts` (new) | test | event-driven | `frontend/src/tests/AppLayout.test.tsx` (render + `MemoryRouter` pattern); needs `vi.useFakeTimers`/localStorage mocking not yet precedented | role-match |
| `frontend/src/tests/AppLayout.test.tsx` (optionally extended) | test | event-driven | itself (existing file) | exact |

## Pattern Assignments

### `frontend/src/lib/api.ts` (service, request-response)

**Analog:** same file, `createConversation()` (lines ~219-230) and `getRides()`/`getAdaptations()` (existing, lines ~193-217)

**Current (buggy) interface to replace** (`frontend/src/lib/api.ts` lines 133-139):
```typescript
export interface Adaptation {
  id: string
  session_id: string
  adaptation_type: string
  description: string
  created_at: string
}
```

**Corrected interface** (must match real `adaptations` table — confirmed via migrations 0002/0005 and `log_adaptation()` call sites):
```typescript
export interface Adaptation {
  id: string
  trigger: 'missed' | 'underperformance' | 'overreaching'
  signal_count?: number | null
  scope: 'micro' | 'macro'
  explanation_text: string
  status?: 'applied' | 'proposed' | 'superseded' | null
  trigger_session_ids?: string[] | null
  created_at: string
}
```

**Existing GET wrapper to leave as-is** (`api.ts`, already correct):
```typescript
// GET /adaptations/
export async function getAdaptations(): Promise<Adaptation[]> {
  const res = await apiFetch('/api/adaptations/')
  if (!res.ok) throw new Error(`getAdaptations failed: ${res.status}`)
  return res.json() as Promise<Adaptation[]>
}
```

**POST wrapper pattern to copy** (`createConversation`, lines ~219-230 — new `checkAdaptations()` is simpler, no body):
```typescript
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
```
New function to add, following the same file's error-throw convention (`if (!res.ok) throw new Error(...)`):
```typescript
export async function checkAdaptations(): Promise<unknown> {
  const res = await apiFetch('/api/adaptations/check', { method: 'POST' })
  if (!res.ok) throw new Error(`checkAdaptations failed: ${res.status}`)
  return res.json()
}
```

**apiFetch (auth injection, already correct, no changes)** — `api.ts` lines 1-22:
```typescript
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
```

---

### `frontend/src/hooks/useAdaptationCheck.ts` (new hook, event-driven)

**Analog 1 (localStorage safety wrapper):** `frontend/src/lib/sessionPersistence.ts` lines 29-44
```typescript
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
```
For the throttle timestamp, mirror this try/catch shape but store a raw ISO string (no `JSON.stringify`/`JSON.parse`).

**Analog 2 (mount-once useEffect on a layout-level component):** `frontend/src/router.tsx` `RootProvider` (referenced in RESEARCH.md lines 170-183) — empty/stable deps array, fire-and-forget side effect, no loading state tied to render.

**Concrete implementation** (already validated in RESEARCH.md's Code Examples section, safe to copy verbatim):
```typescript
import { useEffect } from 'react'
import { checkAdaptations } from '../lib/api'

const THROTTLE_KEY = 'pacerai_adaptation_checked_at'
const THROTTLE_MS = 7 * 24 * 60 * 60 * 1000 // 7 days (D-03)

function getLastChecked(): number | null {
  try {
    const raw = localStorage.getItem(THROTTLE_KEY)
    return raw ? new Date(raw).getTime() : null
  } catch {
    return null
  }
}

function setLastChecked(iso: string): void {
  try {
    localStorage.setItem(THROTTLE_KEY, iso)
  } catch {
    // QuotaExceededError — nothing we can do, mirrors sessionPersistence.ts
  }
}

export function useAdaptationCheck(): void {
  useEffect(() => {
    const lastChecked = getLastChecked()
    const now = Date.now()
    if (lastChecked !== null && now - lastChecked < THROTTLE_MS) return

    checkAdaptations()
      .then(() => {
        setLastChecked(new Date().toISOString()) // D-05: only on success
      })
      .catch(() => {
        // D-05: fail silently, do not update timestamp, no retry loop
      })
  }, [])
}
```

**Critical correctness constraint (D-05):** timestamp write must be inside the `.then()` success branch only — never in a `.finally()` or unconditional path. This is the highest-risk logic in the phase per RESEARCH.md Pitfall 3.

---

### `frontend/src/components/AppLayout.tsx` (edit, event-driven)

**Current file** (full, 92 lines) — no existing `useEffect`, single insertion point at top of function body before `return`:
```typescript
import { Outlet, useNavigate, useLocation } from 'react-router'
import { Settings } from 'lucide-react'
import { TooltipProvider } from '@/components/ui/tooltip'
import { BottomTabBar } from './nav/BottomTabBar'
import { DesktopSidebar } from './nav/DesktopSidebar'
import { IOSInstallBanner } from './pwa/IOSInstallBanner'
// ADD: import { useAdaptationCheck } from '../hooks/useAdaptationCheck'

export function AppLayout() {
  const navigate = useNavigate()
  const { pathname } = useLocation()
  const title = pathname.startsWith('/rides/') ? 'Analysis' : (ROUTE_TITLES[pathname] ?? 'PacerAI')
  const isToday = pathname === '/'
  const showSettingsGear = pathname !== '/settings'
  // ADD HERE: useAdaptationCheck()

  return ( /* unchanged JSX */ )
}
```
Only change: add the import and call `useAdaptationCheck()` as a bare statement in the function body. No JSX changes (D-04: no loading UI).

---

### `frontend/src/screens/ProgressScreen.tsx` (edit, CRUD read-only list)

**Analog:** same file's existing "4. Ride log" section (lines 189-269), which already demonstrates the full loading/error/empty/data state machine to replicate for "5. Adaptations".

**Imports pattern to extend** (line 3):
```typescript
import { getRides, getPmcHistory, getLatestPmc } from '../lib/api'
// becomes:
import { getRides, getPmcHistory, getLatestPmc, getAdaptations } from '../lib/api'
```

**useQuery pattern to copy** (lines 96-98, same shape for the new query):
```typescript
const ridesQuery = useQuery({ queryKey: ['rides'], queryFn: getRides })
const pmcQuery = useQuery({ queryKey: ['pmc-history'], queryFn: getPmcHistory })
const latestQuery = useQuery({ queryKey: ['pmc', 'latest'], queryFn: getLatestPmc })
// ADD:
const adaptationsQuery = useQuery({ queryKey: ['adaptations'], queryFn: getAdaptations })
const adaptations = adaptationsQuery.data ?? []
```

**Section skeleton to copy (`SkeletonRow`, `SectionLabel` — already defined locally in this file, lines 24-53), reuse unchanged.** Per UI-SPEC, render exactly 2 `SkeletonRow`s (not 3 like Ride log).

**Error state pattern to copy** (lines 206-223, same button styling, different copy):
```typescript
{ridesQuery.isError && (
  <button
    onClick={() => ridesQuery.refetch()}
    style={{
      display: 'block', width: '100%', padding: '12px', textAlign: 'center',
      background: 'none', border: 'none', cursor: 'pointer',
      color: 'var(--color-bad)', fontSize: '14px',
    }}
  >
    Could not load history. Tap to retry.
  </button>
)}
```
New copy per UI-SPEC: `"Could not load adaptations. Tap to retry."`

**Empty state pattern to copy** (lines 225-248, simplified per D-11/UI-SPEC to a single `<p>`, no heading):
```typescript
{!adaptationsQuery.isLoading && !adaptationsQuery.isError && adaptations.length === 0 && (
  <p style={{ fontSize: 15, color: 'var(--color-ink-2)', textAlign: 'center', lineHeight: 1.5, paddingTop: 24, margin: 0 }}>
    No adaptations yet. Your plan hasn't needed adjustment.
  </p>
)}
```

**Row-render pattern** — new, styled to match `RideRow`'s collapsed-row rhythm (12px 0 padding, borderBottom var(--color-line)), but NOT a `<button>` (rows are static, no expand/tap per UI-SPEC):
```typescript
{!adaptationsQuery.isLoading && !adaptationsQuery.isError &&
  adaptations.map((a) => (
    <div key={a.id} style={{ borderBottom: '1px solid var(--color-line)', padding: '12px 0' }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--color-ink)' }}>
        {triggerLabel(a.trigger)}
      </div>
      <p style={{ fontSize: 13, color: 'var(--color-ink-2)', margin: '2px 0', lineHeight: 1.5 }}>
        {a.explanation_text}
      </p>
      <span style={{ fontSize: 12, color: 'var(--color-ink-3)' }}>
        {formatDate(a.created_at)}
      </span>
    </div>
  ))}
```
Section placement: insert as a new top-level `<div>` directly after the existing "4. Ride log" `<div>` block (line 269, before the closing `</div>` of the max-width column), using `<SectionLabel>Adaptations</SectionLabel>`.

---

### `frontend/src/lib/format.ts` (utility, transform)

**Analog:** same file's existing `ZONE_LABELS` + `sessionTypeLabel` pattern (lines 12-25):
```typescript
const ZONE_LABELS: Record<string, string> = {
  recovery: 'Recovery',
  endurance: 'Endurance',
  tempo: 'Tempo',
  threshold: 'Threshold',
  vo2: 'VO2 Max',
}

export function sessionTypeLabel(type: string | null | undefined): string {
  if (!type) return 'Session'
  return ZONE_LABELS[type] ?? titleCase(type)
}
```
New addition, same shape (per RESEARCH.md's trigger humanization map, UI-SPEC lines 113-121):
```typescript
const TRIGGER_LABELS: Record<string, string> = {
  missed: 'Missed session',
  underperformance: 'Underperformance',
  overreaching: 'Overreaching',
}

export function triggerLabel(trigger: string | null | undefined): string {
  if (!trigger) return 'Adaptation'
  return TRIGGER_LABELS[trigger] ?? titleCase(trigger)
}
```

**Date formatter to extract** — currently private in `frontend/src/components/history/RideRow.tsx` lines 56-66:
```typescript
function formatDate(isoDate: string): string {
  try {
    return new Date(isoDate).toLocaleDateString(undefined, {
      weekday: 'short',
      month: 'short',
      day: 'numeric',
    })
  } catch {
    return isoDate
  }
}
```
Recommended (per RESEARCH.md A2, discretion): move this into `lib/format.ts` as `export function formatDate(...)`, then update `RideRow.tsx` to `import { formatDate } from '../../lib/format'` and delete its private copy. UI-SPEC requires the Adaptations section's date output to visually match this exact format (e.g. "Mon, Jul 6").

---

### `frontend/src/tests/progress.test.tsx` (new test, request-response rendering)

**Analog:** `frontend/src/tests/history.test.tsx` — full file read; copy its mock/wrapper scaffolding:
```typescript
vi.mock('../lib/api', () => ({
  getRides: vi.fn(),
  getPmcHistory: vi.fn(),
  getLatestPmc: vi.fn(),
  getAdaptations: vi.fn(),
}))

function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } })
}

function renderWithQuery(ui: React.ReactElement) {
  const client = makeQueryClient()
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>)
}
```
Then mirror `describe('HistoryScreen empty state', ...)` (lines 79-100) for the new Adaptations section: mock `getAdaptations` to resolve `[]`, assert the exact D-11/UI-SPEC empty sentence renders; mock a realistic row (using corrected `Adaptation` fields — `trigger`, `explanation_text`, `created_at`) and assert humanized label + explanation text + formatted date all render.

**Fixture shape to use (real schema, not the old buggy interface):**
```typescript
function makeAdaptation(overrides: Partial<Adaptation> = {}): Adaptation {
  return {
    id: 'adapt-1',
    trigger: 'missed',
    scope: 'micro',
    explanation_text: 'Micro-adjustment triggered by missed session abc123. Next 3 sessions reduced to 80% intensity to ease back in.',
    created_at: '2026-07-06T12:00:00Z',
    ...overrides,
  }
}
```

---

### `frontend/src/tests/useAdaptationCheck.test.ts` (new test, event-driven)

**Analog:** `frontend/src/tests/AppLayout.test.tsx` for the `render` + `MemoryRouter` harness shape (full file, 37 lines, copy the render-in-router pattern if testing via `AppLayout` mount rather than the hook directly).

No existing localStorage-mock or fake-timer precedent in this test suite — new pattern needed:
```typescript
// New pattern (no direct in-repo precedent — write fresh, following Vitest conventions):
beforeEach(() => {
  localStorage.clear()
  vi.mocked(api.checkAdaptations).mockReset()
})

it('does not call checkAdaptations when last check was < 7 days ago', () => {
  localStorage.setItem('pacerai_adaptation_checked_at', new Date().toISOString())
  renderHook(() => useAdaptationCheck())
  expect(api.checkAdaptations).not.toHaveBeenCalled()
})

it('does not update localStorage timestamp on checkAdaptations failure (D-05)', async () => {
  vi.mocked(api.checkAdaptations).mockRejectedValue(new Error('network'))
  renderHook(() => useAdaptationCheck())
  await waitFor(() => expect(api.checkAdaptations).toHaveBeenCalled())
  expect(localStorage.getItem('pacerai_adaptation_checked_at')).toBeNull()
})
```
Use `@testing-library/react`'s `renderHook` (already a transitive dependency of RTL in this project's stack) or wrap in a throwaway component if `renderHook` isn't imported elsewhere in the repo — verify during implementation.

---

## Shared Patterns

### Authenticated fetch wrapper
**Source:** `frontend/src/lib/api.ts` lines 12-22 (`apiFetch`)
**Apply to:** `checkAdaptations()` (new) — reuses this unchanged; no new auth code needed anywhere in this phase.

### localStorage safety wrapper (try/catch every call)
**Source:** `frontend/src/lib/sessionPersistence.ts` lines 29-50
**Apply to:** `useAdaptationCheck.ts`'s `getLastChecked`/`setLastChecked`.

### useQuery + loading/error/empty/data state machine
**Source:** `frontend/src/screens/ProgressScreen.tsx` lines 96-98, 190-269 (Ride log section)
**Apply to:** New Adaptations section in the same file — identical shape, different copy per UI-SPEC.

### Record<string,string> lookup + titleCase fallback
**Source:** `frontend/src/lib/format.ts` lines 12-25 (`ZONE_LABELS`/`sessionTypeLabel`)
**Apply to:** New `triggerLabel()` in the same file.

### Test scaffolding: mock api module + QueryClientProvider wrapper
**Source:** `frontend/src/tests/history.test.tsx` lines 15-42
**Apply to:** `frontend/src/tests/progress.test.tsx`.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/tests/useAdaptationCheck.test.ts` (fake-timer/localStorage-mock harness specifics) | test | event-driven | No existing test in this repo mocks localStorage timestamps or tests a throttle window; harness must be written fresh (Vitest's own `localStorage` is globally available in jsdom, no special mock library needed) |

## Metadata

**Analog search scope:** `frontend/src/lib/`, `frontend/src/components/`, `frontend/src/screens/`, `frontend/src/tests/`, `frontend/src/hooks/` (does not yet exist), `backend/routes/adaptations.py` (read-only, no changes)
**Files scanned:** `api.ts`, `AppLayout.tsx`, `sessionPersistence.ts`, `format.ts`, `ProgressScreen.tsx`, `RideRow.tsx`, `AppLayout.test.tsx`, `history.test.tsx`, `router.tsx` (referenced via RESEARCH.md excerpts)
**Pattern extraction date:** 2026-07-10
