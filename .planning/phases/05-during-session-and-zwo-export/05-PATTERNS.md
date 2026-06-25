# Phase 5: During-Session and ZWO Export - Pattern Map

**Mapped:** 2026-06-21
**Files analyzed:** 10 new/modified files
**Analogs found:** 9 / 10

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `frontend/src/screens/DuringSessionScreen.tsx` | screen (rewrite) | event-driven | `frontend/src/screens/DuringSessionScreen.tsx` (Phase 4 stub) | self-rewrite |
| `frontend/src/hooks/useSessionTimer.ts` | hook | event-driven | `frontend/src/hooks/useSSEStream.ts` | role-match |
| `frontend/src/hooks/useWakeLock.ts` | hook | event-driven | `frontend/src/hooks/useCalendarStatus.ts` | role-match |
| `frontend/src/components/session/ZwoExportModal.tsx` | component | request-response | `frontend/src/components/settings/CalendarStatus.tsx` | exact (async action + toast + dialog) |
| `frontend/src/components/session/DurationPickerModal.tsx` | component | event-driven | `frontend/src/components/ui/alert-dialog.tsx` (primitive) | role-match |
| `frontend/src/stores/uiStore.ts` | store (modify) | - | `frontend/src/stores/uiStore.ts` (self) | self-modify |
| `frontend/src/lib/api.ts` | api client (modify) | request-response | `frontend/src/lib/api.ts` (self) | self-modify |
| `frontend/src/types/nosleep.d.ts` | type declaration | - | `frontend/src/vite-env.d.ts` | role-match |
| `api/sports_science/zwo.py` | service (pure) | transform | `api/sports_science/zones.py` | role-match |
| `api/routes/sessions.py` | route (modify) | request-response | `api/routes/sessions.py` (self — PATCH handler) | self-modify |

## Pattern Assignments

### `frontend/src/screens/DuringSessionScreen.tsx` (screen, event-driven rewrite)

**Analog:** Phase 4 stub (self) + `TodayScreen.tsx` for query pattern

**Imports pattern** — copy from `frontend/src/screens/TodayScreen.tsx` lines 1-6 and `DuringSessionScreen.tsx` lines 4-7:
```typescript
import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router'
import { useQuery } from '@tanstack/react-query'
import { Button } from '@/components/ui/button'
import { SessionStepList } from '@/components/session/SessionStepList'
import type { SessionStep } from '@/components/session/SessionStepList'
import { getSessionToday } from '@/lib/api'
import { useSessionTimer } from '@/hooks/useSessionTimer'
import { useWakeLock } from '@/hooks/useWakeLock'
import { useUiStore } from '@/stores/uiStore'
```

**TanStack Query pattern** — copy from `frontend/src/screens/TodayScreen.tsx` lines 33-40:
```typescript
const { data: session } = useQuery({
  queryKey: ['session', 'today'],
  queryFn: getSessionToday,
})
```

**Layout shell pattern** — copy from `frontend/src/screens/DuringSessionScreen.tsx` lines 19-64 (existing shell; replace static content):
```tsx
<div
  className="min-h-screen flex flex-col"
  style={{ backgroundColor: 'var(--color-bg-2)' }}
>
  <div className="flex-1 flex flex-col justify-center px-6 pt-12 pb-6">
    {/* step list and timer go here */}
  </div>
  <div className="flex justify-end px-6 pb-8">
    <Button variant="outline" ...>End session</Button>
  </div>
</div>
```

**Timer display pattern** — copy typography tokens from `DuringSessionScreen.tsx` lines 31-48:
```tsx
<p style={{
  fontSize: 32,
  fontWeight: 700,
  color: 'var(--color-ink)',
  fontVariantNumeric: 'tabular-nums',
  letterSpacing: '0.05em',
}}>
  {formatTimer(secondsLeft)}
</p>
```

**Session complete overlay:** Inline conditional — when `currentIndex >= steps.length`, replace step list with a full-screen overlay using the same `min-h-screen` container background and `var(--color-ink)` / `var(--color-ink-2)` typography tokens. Add a "Done" `Button` variant="default" that calls `navigate('/')`.

---

### `frontend/src/hooks/useSessionTimer.ts` (hook, event-driven)

**Analog:** `frontend/src/hooks/useSSEStream.ts` (useEffect + cleanup pattern)

**Core hook pattern** — from RESEARCH.md Pattern 1 (confirmed via MDN; no codebase analog exists):
```typescript
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

    const id = setInterval(tick, 250)   // 250ms — avoids second-boundary drift

    const handleVisibility = () => {
      if (document.hidden) {
        pausedElapsedRef.current += Math.floor((Date.now() - startRef.current) / 1000)
      } else {
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
```

**Anti-pattern:** Never accumulate tick counts. Always use `Date.now()` delta so iOS tab-switch does not drift or skip seconds.

---

### `frontend/src/hooks/useWakeLock.ts` (hook, event-driven)

**Analog:** `frontend/src/hooks/useCalendarStatus.ts` (hook file structure, single export)

**Core hook pattern** — from RESEARCH.md Pattern 2 (no codebase analog; novel DOM API):
```typescript
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
          // Battery saver or denied — fall through to nosleep.js
        }
      }
      // Always try nosleep.js if sentinel not acquired (covers iOS < 18.4 PWA bug)
      if (!sentinel) {
        const NoSleep = (await import('nosleep.js')).default as {
          new(): { enable(): void; disable(): void }
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
```

**Pitfall:** On iOS < 18.4 installed PWA, `'wakeLock' in navigator` may return true but the request fails silently. Run `nosleep.js` fallback inside the catch **and** when `sentinel` is null after the try block.

---

### `frontend/src/components/session/ZwoExportModal.tsx` (component, request-response)

**Analog:** `frontend/src/components/settings/CalendarStatus.tsx` — exact pattern for async action + sonner toast + AlertDialog.

**Imports pattern** — copy from `CalendarStatus.tsx` lines 1-17:
```typescript
import { useState } from 'react'
import { toast } from 'sonner'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { Button } from '@/components/ui/button'
import { exportSessionZwo } from '@/lib/api'
import type { SessionData } from './SessionCard'
```

**Async action + loading + toast pattern** — copy from `CalendarStatus.tsx` lines 36-47:
```typescript
const [downloading, setDownloading] = useState(false)

async function handleDownload() {
  setDownloading(true)
  try {
    await exportSessionZwo(session.id)
    toast.success('Workout file downloaded.')
    setOpen(false)
  } catch (err) {
    toast.error('Export failed. Please try again.')
    // Modal stays open for retry (D-07)
  } finally {
    setDownloading(false)
  }
}
```

**Modal stays open on error:** Do NOT call `setOpen(false)` inside the catch block (D-07).

**Preview content:** Show `session.type + scheduled_date` as workout name, FTP value from profile query or "assumed 100W (no FTP estimate yet)", and 3-step duration summary. All read from cached TanStack Query data — no extra API call on modal open (D-04).

---

### `frontend/src/components/session/DurationPickerModal.tsx` (component, event-driven)

**Analog:** `frontend/src/components/settings/CalendarStatus.tsx` (AlertDialog structure) + `SessionCard.tsx` lines 1-17 (AlertDialog import pattern).

**Imports pattern** — copy AlertDialog imports from `SessionCard.tsx` lines 8-17 (same primitive set).

**State pattern:**
```typescript
const [open, setOpen] = useState(false)
const [custom, setCustom] = useState('')
const PRESETS = [30, 45, 60]
```

**On confirm:** Call `useUiStore.setState({ freeRideDurationMins: chosen })` then `navigate('/session')`. Chosen value is either a preset integer or `parseInt(custom, 10)` validated as >= 1.

---

### `frontend/src/stores/uiStore.ts` (store, modify)

**Analog:** Self (existing file — lines 1-29).

**Add one slice** — follow the existing pattern exactly (`frontend/src/stores/uiStore.ts` lines 5-9 for interface, lines 20-28 for `create` body):
```typescript
// Add to UiState interface:
freeRideDurationMins: number | null
setFreeRideDurationMins: (mins: number | null) => void

// Add to create() body:
freeRideDurationMins: null,
setFreeRideDurationMins: (mins) => useUiStore.setState({ freeRideDurationMins: mins }),
```

---

### `frontend/src/lib/api.ts` (api client, modify)

**Analog:** Self (existing file). Two additions follow existing function patterns.

**Extend Session interface** — add structure field after `notes` (around line 63):
```typescript
export interface SessionStructureSegment {
  duration_minutes: number
  description: string
}
export interface SessionStructure {
  warmup?: SessionStructureSegment
  main_set?: SessionStructureSegment
  cooldown?: SessionStructureSegment
}

// In Session interface, replace `notes: string | null`:
structure: SessionStructure | null
scheduled_date: string
```

**New export function** — copy blob-download pattern from RESEARCH.md Pattern 5; place after `markSessionDone` (line 198):
```typescript
export async function exportSessionZwo(sessionId: string): Promise<void> {
  const res = await apiFetch(`/sessions/${sessionId}/export.zwo`, {
    headers: { Accept: 'application/xml' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { error?: string }
    throw new Error(err?.error ?? `export failed ${res.status}`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = ''    // browser uses Content-Disposition filename from backend
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
```

---

### `frontend/src/types/nosleep.d.ts` (type declaration)

**Analog:** `frontend/src/vite-env.d.ts` (ambient module declaration file structure).

**Full file content:**
```typescript
declare module 'nosleep.js' {
  export default class NoSleep {
    enable(): void
    disable(): void
  }
}
```

---

### `api/sports_science/zwo.py` (service, transform)

**Analog:** `api/sports_science/zones.py` (pure computation, no DB, returns typed value; same sports_science module).

**Module header pattern** — copy docstring style from `api/sports_science/plan.py` lines 1-12:
```python
# sports_science/zwo.py
"""
ZWO workout file generator (ZWO-01 through ZWO-04).

Pure computation -- no DB calls, no imports of other sports_science tools.
Generates a conformant .zwo XML file from session structure and FTP.

Power fractions are FTP decimals (0.0-2.0 per ZWO-02). When ftp_watts is None,
uses 100W assumed FTP and FreeRide segments with textevent RPE cues (D-08/D-09).
"""
import xml.etree.ElementTree as ET
```

**Core generation function** — from RESEARCH.md Pattern 3:
```python
def generate_zwo(session: dict, ftp_watts: int | None) -> bytes:
    effective_ftp = ftp_watts if ftp_watts else 100
    use_free_ride = ftp_watts is None
    structure = session.get("structure") or {}

    root = ET.Element("workout_file")
    ET.SubElement(root, "name").text = (
        f"{(session.get('type') or 'workout').title()}: "
        f"{session.get('scheduled_date', '')}"
    )
    ET.SubElement(root, "author").text = "PacerAI"
    ET.SubElement(root, "description").text = session.get("objective") or ""
    ET.SubElement(root, "sportType").text = "bike"   # ZWO-04: must be "bike"

    workout = ET.SubElement(root, "workout")

    POWER_BY_SEGMENT = {
        "warmup":   0.50,
        "main_set": 0.65,
        "cooldown": 0.50,
    }

    for segment_key in ("warmup", "main_set", "cooldown"):
        seg = structure.get(segment_key) or {}
        duration_secs = int(seg.get("duration_minutes", 5) * 60)
        description = seg.get("description", "")

        if use_free_ride:
            block = ET.SubElement(
                workout, "FreeRide",
                Duration=str(duration_secs),
                FlatRoad="0",
            )
            ET.SubElement(block, "textevent",
                          timeoffset="0",
                          message=description,
                          duration="10")
        else:
            # Clamp to 0.0-2.0 (ZWO-02) and format as decimal string (Pitfall 4)
            power = round(max(0.0, min(2.0, POWER_BY_SEGMENT[segment_key])), 4)
            ET.SubElement(workout, "SteadyState",
                          Duration=str(duration_secs),
                          Power=str(power))
            # ZWO-04: Cadence attribute omitted entirely (not set to 0)

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
```

---

### `api/routes/sessions.py` — add `GET /sessions/{id}/export.zwo` (route, modify)

**Analog:** Self — `PATCH /sessions/{session_id}` handler (lines 221-260). Exact same auth, validate_uuid, and dual-filter query pattern.

**New route pattern** — copy auth + validate_uuid + dual-filter from PATCH handler (lines 239-260), then add profile FTP fetch and ZWO generation:
```python
from fastapi.responses import Response

@router.get("/sessions/{session_id}/export.zwo")
async def export_session_zwo(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> Response:
    user_id = current_user["user_id"]
    validate_uuid(session_id, "session_id")
    supabase = await _get_async_supabase()

    # Auth pattern: filter by BOTH session_id AND user_id (T-04-03)
    result = await (
        supabase.table("sessions")
        .select(_SESSION_COLUMNS)
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(
            status_code=404,
            detail={"error": "session_not_found",
                    "detail": "No session found for this user with the given id"},
        )

    session = result.data[0]

    profile_result = await (
        supabase.table("profiles")
        .select("ftp")
        .eq("user_id", user_id)
        .execute()
    )
    ftp = profile_result.data[0]["ftp"] if profile_result.data else None

    from api.sports_science.zwo import generate_zwo
    xml_bytes = generate_zwo(session, ftp)

    scheduled_date = session.get("scheduled_date", "")
    session_type = (session.get("type") or "workout").lower()
    filename = f"{scheduled_date}-{session_type}.zwo"

    return Response(
        content=xml_bytes,
        media_type="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

**Security:** `validate_uuid` on line 2 of the handler (before any DB call) per V5 ASVS. Dual filter (`.eq("id"...).eq("user_id"...)`) is the existing IDOR mitigation pattern from PATCH.

---

## Shared Patterns

### Auth (all route handlers)
**Source:** `api/routes/sessions.py` lines 48-51, 221-241
**Apply to:** `GET /sessions/{id}/export.zwo`
```python
current_user: dict = Depends(get_current_user),
# then:
user_id = current_user["user_id"]
validate_uuid(session_id, "session_id")  # before any DB call
```

### Dual-filter IDOR guard (session routes)
**Source:** `api/routes/sessions.py` lines 248-250 (PATCH handler)
**Apply to:** ZWO export route
```python
.eq("id", session_id)
.eq("user_id", user_id)
```

### Sonner error toast + stay-open pattern (modal components)
**Source:** `frontend/src/components/settings/CalendarStatus.tsx` lines 36-47
**Apply to:** `ZwoExportModal.tsx`
```typescript
} catch {
  toast.error('Export failed. Please try again.')
  // Do NOT call setOpen(false) here — modal stays open for retry
} finally {
  setDownloading(false)
}
```

### AlertDialog primitive import block (all modal components)
**Source:** `frontend/src/components/session/SessionCard.tsx` lines 8-17
**Apply to:** `ZwoExportModal.tsx`, `DurationPickerModal.tsx`
```typescript
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel,
  AlertDialogContent, AlertDialogDescription, AlertDialogFooter,
  AlertDialogHeader, AlertDialogTitle, AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
```

### Design tokens (all Phase 5 components)
**Source:** `frontend/src/screens/DuringSessionScreen.tsx` lines 22-65
**Apply to:** All new/modified screens and components
- Background: `var(--color-bg-2)`
- Primary text: `var(--color-ink)`
- Secondary text: `var(--color-ink-2)`, `var(--color-ink-3)`
- Borders/lines: `var(--color-line)`
- No pure blacks; no em dashes in any copy string

### Python sports_science module conventions
**Source:** `api/sports_science/plan.py` lines 1-13
**Apply to:** `api/sports_science/zwo.py`
- Module-level docstring: pure computation, no DB calls
- No imports from other sports_science tools (trust model)

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `frontend/src/types/nosleep.d.ts` | type declaration | - | No existing ambient module declarations in codebase; uses same `.d.ts` convention as `vite-env.d.ts` |

---

## Key Anti-Patterns to Avoid

1. **ZWO Power as integer:** Always `str(round(fraction, 4))` not `str(int_value)` — Zwift interprets integer `1` as 1W not 100% FTP.
2. **Cadence="0":** Omit the Cadence attribute entirely (ZWO-04). Do not set to 0.
3. **sportType not "bike":** Use lowercase `"bike"` exactly — not `"cycling"` or `"ride"`.
4. **textevent outside FreeRide:** `<textevent>` must be a child element of `<FreeRide>`, not a sibling in `<workout>`.
5. **setInterval count accumulation:** Always use `Date.now()` delta, never count ticks.
6. **Wake lock without feature detect:** Check `'wakeLock' in navigator` before calling `.request()`.
7. **Extra API call on modal open:** ZWO export modal reads cached `['session', 'today']` data — never fetches on open.

## Metadata

**Analog search scope:** `frontend/src/`, `api/routes/`, `api/sports_science/`, `api/hooks/`
**Files scanned:** 14
**Pattern extraction date:** 2026-06-21
