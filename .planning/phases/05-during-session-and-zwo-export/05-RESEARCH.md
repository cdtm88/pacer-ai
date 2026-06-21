# Phase 5: During-Session and ZWO Export - Research

**Researched:** 2026-06-21
**Domain:** React timer/wake-lock hooks, ZWO XML generation, FastAPI file download
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Timer auto-advances when it hits 0. A 3-second countdown warning is shown before advancing ("Starting [next step] in 3...").
- **D-02:** Users can manually tap "Skip" to advance before timer expires.
- **D-03:** Last step completion shows "Session complete" overlay: total elapsed time, steps completed, "Done" button to navigate to Today.
- **D-04:** "Export to Zwift" opens a two-step modal showing session name, FTP used (or "assumed 100W"), and step summary. "Download" button calls the backend endpoint.
- **D-05:** File naming: `{YYYY-MM-DD}-{type}.zwo` (e.g. `2026-06-21-endurance.zwo`).
- **D-06:** ZWO generation lives in FastAPI: `GET /sessions/{id}/export.zwo`. Python generates XML via stdlib `xml.etree.ElementTree`. Frontend does not generate XML.
- **D-07:** Export errors return structured JSON error; modal shows sonner error toast and stays open for retry.
- **D-08:** No FTP estimate: use 100W assumed FTP. Conservative; keeps all power fractions well within 0.0-2.0 bounds.
- **D-09:** Pre-FTP sessions use `<FreeRide>` segments with `<textevent>` RPE cues, not `<SteadyState>` power blocks.
- **D-10:** `DuringSessionScreen` calls `getSessionToday()` on mount independently. No session ID via URL param.
- **D-11:** Rest-day "Ride anyway" button opens a duration picker modal (30/45/60 min presets + custom). Duration stored in Zustand; navigates to `/session`.
- **D-12:** Session maps to exactly 3 steps: warmup -> main_set -> cooldown. Interval sub-structure deferred.

### Claude's Discretion

None specified.

### Deferred Ideas (OUT OF SCOPE)

- Interval sub-structure in plan generator
- ZWO export for historical/upcoming sessions (only today in Phase 5)
- Full PMC CTL/ATL/TSB chart
- Dark mode
- Web Bluetooth
- Telegram bot
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ZWO-01 | Planned structured session can be exported as valid .zwo that Zwift can import | ZWO XML format documented below; FastAPI Response pattern confirmed |
| ZWO-02 | Power targets as FTP fractions 0.0-2.0; validated before export | D-08 assumed 100W is conservative; validation in Python before building XML |
| ZWO-03 | Pre-FTP sessions use conservative assumed FTP with RPE text segments | `<FreeRide>` + `<textevent>` pattern per ZWO spec; D-08/D-09 |
| ZWO-04 | File includes `<sportType>bike</sportType>`; Cadence omitted when unspecified | Confirmed in ZWO spec; omit Cadence attribute entirely (not set to 0) |
| ZWO-05 | Generated .zwo validated against real Zwift import before production | Manual acceptance test; executor must import file in Zwift to verify |
| IOS-01 | Wake Lock API with NoSleep.js fallback for iOS < 18.4 | nosleep.js 0.12.0 confirmed OK on npm; re-acquire pattern on visibilitychange documented |
| IOS-02 | Timer uses `Date.now()` deltas; `visibilitychange` resyncs timer on tab return | useRef startTimestamp pattern; setInterval at 250ms polling for sub-second accuracy |
| IOS-03 | During-session view tested on iOS Safari (not only Chromium) | Physical device testing required; acceptance criterion is manual |
</phase_requirements>

---

## Summary

Phase 5 activates two Phase 4 stubs. The first is `DuringSessionScreen`: replace the static placeholder with a live countdown timer built on `Date.now()` deltas + a `useRef` start timestamp, auto-advance logic with a 3-second countdown warning, wake lock (native API with nosleep.js fallback for iOS < 18.4), and a "Session complete" overlay. The second is the ZWO export pipeline: a FastAPI endpoint that reads today's session structure, generates a conformant `.zwo` XML file via `xml.etree.ElementTree`, and returns it as an attachment download triggered from a two-step modal in `SessionCard`.

The technical domain is shallow but has two non-obvious pitfalls: (1) the Wake Lock API auto-releases on tab hide and must be explicitly re-requested on visibilitychange, which also affects the timer resync; (2) the ZWO file format has inconsistent casing in the community reference (`textevent` vs `TextEvent`, `SteadyState` vs `Cooldown`) and Zwift's importer is known to be lenient but `sportType` must be `"bike"` not `"ride"`.

All new packages are limited to `nosleep.js` (npm, verified OK). No new Python dependencies are needed; `xml.etree.ElementTree` is stdlib. The UI-SPEC is approved and prescribes every copy string, color token, and interaction contract — the planner should treat it as locked.

**Primary recommendation:** Build `useSessionTimer` and `useWakeLock` as isolated hooks, then compose them in `DuringSessionScreen`. The ZWO endpoint follows the existing `sessions_router` pattern with no new auth boilerplate.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Live countdown timer | Browser / Client | -- | Pure client-side `Date.now()` delta; no server call needed |
| Wake lock | Browser / Client | -- | navigator.wakeLock / nosleep.js are browser APIs |
| Step auto-advance + skip | Browser / Client | -- | UI state machine; no server involvement |
| "Session complete" overlay | Browser / Client | -- | Inline overlay driven by `currentIndex >= steps.length` |
| ZWO XML generation | API / Backend | -- | D-06: frontend must not generate XML; stdlib ElementTree |
| ZWO file download | API / Backend | Browser / Client | Backend returns Content-Disposition attachment; frontend triggers blob download |
| ZWO export modal | Browser / Client | -- | Modal reads cached TanStack Query data; one API call on download tap |
| Duration picker (rest day) | Browser / Client | -- | Pure UI state; duration stored in Zustand, no server call |
| Step data parsing (structure -> SessionStep[]) | Browser / Client | -- | Map `session.structure` JSONB to `SessionStep[]` array in component |

---

## Standard Stack

### Core (all pre-existing in this project)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React + hooks | 19.x (installed) | useRef, useState, useEffect for timer logic | Already in project; hooks are the correct pattern |
| Zustand | 5.x (installed) | `freeRideDurationMins` slice for rest-day handoff | Already in project; add one slice |
| TanStack Query | 5.x (installed) | `useQuery(['session', 'today'])` shared cache | Already in project; no extra fetch needed |
| sonner | 2.x (installed) | Error toasts on ZWO export failure | Already in project; same pattern as FIT upload |
| shadcn/ui Dialog | installed | ZWO export modal, duration picker modal | Already installed in Phase 4 |
| xml.etree.ElementTree | stdlib | Python XML generation for .zwo | No dependency needed; stdlib |
| FastAPI Response | 0.115.x (installed) | `Response(content=bytes, headers={Content-Disposition})` | Already in project; no StreamingResponse needed for small XML |

### New Dependency

| Library | Version | Purpose | Registry | Verdict |
|---------|---------|---------|----------|---------|
| nosleep.js | 0.12.0 | iOS PWA wake lock fallback | npm | OK |

**Installation:**
```bash
npm install nosleep.js
```

No TypeScript types package exists for nosleep.js on DefinitelyTyped as of this research. Use a local type declaration `declare module 'nosleep.js'` or inline the minimal API with `as unknown as NoSleep`.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| nosleep.js | Raw video trick (HTML5 video loop) | nosleep.js wraps the same trick; no benefit to hand-rolling |
| Response(bytes) | StreamingResponse + BytesIO | StreamingResponse is for large files; overkill for <10 KB ZWO XML |
| setInterval 1000ms | setInterval 250ms | 1000ms misses second boundaries if interval drifts; 250ms is cheap and accurate |

---

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| nosleep.js | npm | ~6 yrs (2020-12-16) | 332,035/wk | github.com/richtr/NoSleep.js | OK | Approved |

**Packages removed due to SLOP verdict:** none
**Packages flagged as suspicious (SUS):** none

---

## Architecture Patterns

### System Architecture Diagram

```
Today Screen (TodayScreen.tsx)
  |-- [no session] --> rest-day empty state --> "Ride anyway" button
  |                       --> DurationPickerModal (Zustand: freeRideDurationMins)
  |                           --> navigate('/session')
  |
  |-- [session exists] --> SessionCard
                            |-- "Start session" --> navigate('/session')
                            |-- "Export to Zwift" --> ZwoExportModal
                                   --> GET /sessions/{id}/export.zwo
                                       --> sessions.py: build XML
                                       <-- Response(bytes, Content-Disposition)
                                   --> blob URL download triggered in browser

/session route
  DuringSessionScreen.tsx
    |-- useQuery(['session','today']) or Zustand freeRideDuration
    |-- parse structure -> SessionStep[]
    |-- useSessionTimer(currentStepDurationSecs)
    |       |-- useRef(startTimestamp)
    |       |-- setInterval 250ms: elapsed = Date.now() - start
    |       |-- visibilitychange: resync start accounting for elapsed
    |       |-- returns { secondsLeft, isCountingDown, advance }
    |-- useWakeLock()
    |       |-- navigator.wakeLock.request('screen') on mount
    |       |-- nosleep.js fallback if wakeLock not in navigator
    |       |-- re-request on visibilitychange -> visible
    |       |-- release on unmount
    |-- [currentIndex < steps.length] --> SessionStepList + timer display + Skip button
    |-- [currentIndex >= steps.length] --> "Session complete" overlay
```

### Recommended Project Structure (new files only)

```
frontend/src/
├── hooks/
│   ├── useSessionTimer.ts     # Timer hook: Date.now() delta, countdown, advance
│   └── useWakeLock.ts         # Wake lock hook: native + nosleep.js fallback
├── components/session/
│   ├── ZwoExportModal.tsx     # Two-step modal: preview + download trigger
│   └── DurationPickerModal.tsx # Rest-day duration picker (30/45/60/custom)
└── screens/
    └── DuringSessionScreen.tsx # Rewrite: live timer + steps from session data

api/routes/
└── sessions.py                # Add GET /sessions/{id}/export.zwo route

api/sports_science/
└── zwo.py                     # ZWO XML builder: generate_zwo(session, ftp) -> bytes
```

### Pattern 1: Date.now() Delta Timer Hook

**What:** Track elapsed time using wall-clock deltas stored in a ref, not accumulated interval counts.
**When to use:** Any timer that must survive tab switches on iOS Safari (IOS-02).

```typescript
// Source: MDN visibilitychange + Date.now() pattern [ASSUMED]
import { useEffect, useRef, useState, useCallback } from 'react'

export function useSessionTimer(totalSeconds: number) {
  const startRef = useRef<number>(Date.now())
  const pausedElapsedRef = useRef<number>(0)
  const [secondsLeft, setSecondsLeft] = useState(totalSeconds)

  const advance = useCallback(() => {
    // Called on skip or auto-advance; caller resets totalSeconds
    startRef.current = Date.now()
    pausedElapsedRef.current = 0
    setSecondsLeft(totalSeconds)
  }, [totalSeconds])

  useEffect(() => {
    startRef.current = Date.now()
    pausedElapsedRef.current = 0

    const tick = () => {
      const elapsed = pausedElapsedRef.current + Math.floor((Date.now() - startRef.current) / 1000)
      setSecondsLeft(Math.max(0, totalSeconds - elapsed))
    }

    const id = setInterval(tick, 250)

    const handleVisibility = () => {
      if (document.hidden) {
        // Pause: store elapsed so far
        pausedElapsedRef.current += Math.floor((Date.now() - startRef.current) / 1000)
      } else {
        // Resume: reset wall-clock start
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

### Pattern 2: Wake Lock Hook with NoSleep.js Fallback

**What:** Request native wake lock; fall back to nosleep.js on iOS < 18.4.
**When to use:** Any screen that must stay lit during active use.

```typescript
// Source: MDN Screen Wake Lock API + nosleep.js docs [ASSUMED]
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
          // Wake lock denied (e.g., battery saver) — fall through to nosleep.js
        }
      }
      if (!sentinel) {
        // Fallback for iOS < 18.4 or denied wake lock
        const NoSleep = (await import('nosleep.js')).default
        noSleep = new NoSleep()
        noSleep.enable()
      }
    }

    const handleVisibility = () => {
      if (!document.hidden) {
        acquire()
      }
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

### Pattern 3: ZWO XML Generation (Python)

**What:** Build a conformant `.zwo` file from session structure.
**When to use:** `GET /sessions/{id}/export.zwo` endpoint handler.

```python
# Source: h4l/zwift-workout-file-reference (community reverse-engineered) [ASSUMED]
import xml.etree.ElementTree as ET

def generate_zwo(session: dict, ftp_watts: int | None) -> bytes:
    effective_ftp = ftp_watts if ftp_watts else 100
    structure = session.get("structure", {})

    root = ET.Element("workout_file")
    ET.SubElement(root, "name").text = f"{session['type'].title()} — {session['scheduled_date']}"
    ET.SubElement(root, "author").text = "PacerAI"
    ET.SubElement(root, "description").text = session.get("objective", "")
    ET.SubElement(root, "sportType").text = "bike"

    workout = ET.SubElement(root, "workout")

    use_free_ride = ftp_watts is None

    for segment_key in ("warmup", "main_set", "cooldown"):
        seg = structure.get(segment_key, {})
        duration_secs = int(seg.get("duration_minutes", 5) * 60)
        description = seg.get("description", "")

        if use_free_ride:
            block = ET.SubElement(workout, "FreeRide",
                                  Duration=str(duration_secs),
                                  FlatRoad="0")
            ET.SubElement(block, "textevent",
                          timeoffset="0",
                          message=description,
                          duration="10")
        else:
            # Determine power fraction by segment
            if segment_key == "warmup":
                power = round(0.50, 4)
            elif segment_key == "cooldown":
                power = round(0.50, 4)
            else:
                # main_set: use zone 2 (56-75% FTP midpoint ~0.65)
                power = round(0.65, 4)
            # Validate: must be 0.0-2.0
            power = max(0.0, min(2.0, power))
            ET.SubElement(workout, "SteadyState",
                          Duration=str(duration_secs),
                          Power=str(power))

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)
```

### Pattern 4: FastAPI File Download Endpoint

**What:** Return in-memory bytes as a downloadable file.

```python
# Source: FastAPI docs [ASSUMED]
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

@router.get("/sessions/{session_id}/export.zwo")
async def export_zwo(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> Response:
    user_id = current_user["user_id"]
    validate_uuid(session_id, "session_id")
    supabase = await _get_async_supabase()

    result = await (
        supabase.table("sessions")
        .select(_SESSION_COLUMNS)
        .eq("id", session_id)
        .eq("user_id", user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail={"error": "session_not_found"})

    session = result.data[0]
    # Fetch user profile for FTP
    profile_result = await (
        supabase.table("profiles").select("ftp").eq("user_id", user_id).execute()
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

### Pattern 5: Frontend Blob Download Trigger

**What:** Fetch binary response and trigger browser download without a new tab.

```typescript
// Source: MDN Blob URL pattern [ASSUMED]
// In api.ts:
export async function exportSessionZwo(sessionId: string): Promise<void> {
  const res = await apiFetch(`/sessions/${sessionId}/export.zwo`, {
    headers: { Accept: 'application/xml' },
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    throw new Error(err?.error ?? `export failed ${res.status}`)
  }
  const blob = await res.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = '' // browser uses Content-Disposition filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}
```

### Anti-Patterns to Avoid

- **setInterval count accumulation:** Counting ticks instead of `Date.now()` deltas means tab switches silently skip time or lose counts on iOS. Always use wall-clock delta.
- **WakeLock request without feature detect:** Calling `navigator.wakeLock.request()` without checking `'wakeLock' in navigator` throws on iOS < 16.4 and some Chromium builds in low-power mode.
- **Generating ZWO Power in watts instead of FTP fractions:** Zwift always interprets `Power` as a decimal FTP fraction (0.75 = 75% FTP). Never put raw watts.
- **Setting Cadence="0" when unspecified:** Per ZWO-04 requirement, omit the Cadence attribute entirely rather than setting it to 0. Setting to 0 may cause Zwift to try to hold 0 RPM.
- **Re-fetching session data to open modal:** The ZWO export modal must use the already-cached `['session', 'today']` TanStack Query data — no extra API call on modal open (D-04 and existing UI-SPEC interaction contract).
- **Putting TextEvent outside FreeRide block:** `<textevent>` elements must be children of the enclosing workout segment (e.g., `<FreeRide>`), not siblings at the `<workout>` level.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| iOS wake lock fallback | Custom video loop trick | `nosleep.js` | nosleep.js wraps the same video trick; already tested across iOS versions |
| XML serialization | String concatenation | `xml.etree.ElementTree.tostring()` | Handles encoding, escaping, and declaration automatically |
| FTP fraction validation | Manual range check every site | One guard in `generate_zwo` before building any element | Single place to enforce ZWO-02; easy to unit test |
| Blob download trigger | `window.open()` (new tab) | `URL.createObjectURL` + hidden `<a>` click | `window.open()` is blocked by popup blockers; blob URL is the standard pattern |

**Key insight:** The timer and wake lock are well-trodden DOM patterns; the only genuine complexity is iOS Safari behavior, which nosleep.js addresses and which requires a physical device to verify (iOS Simulator does not replicate PWA wake lock).

---

## Common Pitfalls

### Pitfall 1: Wake Lock Silently Drops on iOS < 18.4 in Installed PWA

**What goes wrong:** Wake Lock API appears in `navigator` on some iOS 17 builds but silently fails or releases immediately in installed PWA mode, not stand-alone Safari.
**Why it happens:** Apple shipped partial Wake Lock in iOS 16.4 for Safari but the installed PWA context had a separate bug fixed in iOS 18.4.
**How to avoid:** Always run the nosleep.js fallback path in the catch block even if `'wakeLock' in navigator` is true. Test IOS-03 on a physical iOS device in "Add to Home Screen" installed mode, not Safari browser mode.
**Warning signs:** Timer works in browser but screen dims within 30 seconds when app is installed to home screen.

### Pitfall 2: Timer Drift on Tab Return

**What goes wrong:** Timer shows stale elapsed time for a second or two after returning from background because `setInterval` was suspended.
**Why it happens:** Mobile browsers throttle or suspend timers for background tabs.
**How to avoid:** In `visibilitychange` listener, store elapsed before hiding and reset `startRef.current = Date.now()` on return. The 250ms `setInterval` then catches up on next tick.
**Warning signs:** After switching back from another app, the timer shows the same value for 1-2 seconds before jumping.

### Pitfall 3: ZWO sportType Value

**What goes wrong:** File fails to import or imports under wrong sport category.
**Why it happens:** The community reference lists `"bike"`, `"run"`, `"swim"` as valid values. Using `"cycling"` or `"ride"` causes silent import failure in some Zwift versions.
**How to avoid:** Always use `<sportType>bike</sportType>` (lowercase string "bike"). ZWO-04 requires this explicitly.
**Warning signs:** Zwift shows the file in the wrong sport category or silently ignores it.

### Pitfall 4: Power Fraction as Integer Instead of Decimal String

**What goes wrong:** ZWO imports but all intervals play at wrong intensity.
**Why it happens:** ElementTree renders `Power=1` as the integer 1 which some Zwift builds interpret as 1W not 100% FTP.
**How to avoid:** Always format as float string: `Power=str(round(fraction, 4))` e.g. `"0.75"` not `"1"` for 100%.
**Warning signs:** Zwift shows a flat very-low-power segment for the entire workout during acceptance test.

### Pitfall 5: "Export to Zwift" Button Still Disabled in SessionCard

**What goes wrong:** Phase 4 disabled the button with `disabled` prop and a Tooltip "Coming in the next update". Phase 5 must enable it.
**Why it happens:** The stub is explicit in `SessionCard.tsx` lines 184-199. Easy to miss if only reading DuringSessionScreen.
**How to avoid:** The planner must include a task to enable the button and wire the modal open handler.
**Warning signs:** Clicking "Export to Zwift" does nothing after Phase 5 ships.

### Pitfall 6: nosleep.js Import (No TypeScript Types)

**What goes wrong:** TypeScript error `Could not find a declaration file for module 'nosleep.js'`.
**Why it happens:** nosleep.js 0.12.0 does not ship `@types/nosleep.js` on DefinitelyTyped.
**How to avoid:** Add `declare module 'nosleep.js'` in a `.d.ts` file or use `// @ts-ignore` on the import, or type-cast: `const NoSleep = (await import('nosleep.js')).default as { new(): { enable(): void; disable(): void } }`.

---

## Code Examples

### ZWO File: Pre-FTP Example (FreeRide + textevent)

```xml
<?xml version='1.0' encoding='utf-8'?>
<workout_file>
  <name>Endurance — 2026-06-21</name>
  <author>PacerAI</author>
  <description>Aerobic base building</description>
  <sportType>bike</sportType>
  <workout>
    <FreeRide Duration="300" FlatRoad="0">
      <textevent timeoffset="0" message="Easy spin, HR building gradually" duration="10" />
    </FreeRide>
    <FreeRide Duration="1800" FlatRoad="0">
      <textevent timeoffset="0" message="Zone 2 steady effort, maintain conversation pace" duration="10" />
    </FreeRide>
    <FreeRide Duration="300" FlatRoad="0">
      <textevent timeoffset="0" message="Easy spin, let HR settle" duration="10" />
    </FreeRide>
  </workout>
</workout_file>
```

### ZWO File: With FTP Example (SteadyState)

```xml
<?xml version='1.0' encoding='utf-8'?>
<workout_file>
  <name>Endurance — 2026-06-21</name>
  <author>PacerAI</author>
  <description>Sustained aerobic effort</description>
  <sportType>bike</sportType>
  <workout>
    <SteadyState Duration="300" Power="0.5" />
    <SteadyState Duration="2100" Power="0.65" />
    <SteadyState Duration="300" Power="0.5" />
  </workout>
</workout_file>
```

### Timer Display Format

```typescript
// MM:SS formatting — always two digits
function formatTimer(secondsLeft: number): string {
  const m = Math.floor(secondsLeft / 60)
  const s = secondsLeft % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}
```

### Step Structure Parsing (session.structure -> SessionStep[])

```typescript
// session.structure from the API is:
// { warmup: { duration_minutes, description }, main_set: {...}, cooldown: {...} }
// Map to SessionStep[] for SessionStepList

import type { SessionStep } from '@/components/session/SessionStepList'

type StructureSegment = { duration_minutes: number; description: string }
type SessionStructure = {
  warmup?: StructureSegment
  main_set?: StructureSegment
  cooldown?: StructureSegment
}

function parseSteps(structure: unknown, sessionType?: string | null): SessionStep[] {
  if (!structure || typeof structure !== 'object') return []
  const s = structure as SessionStructure
  const steps: SessionStep[] = []
  if (s.warmup) steps.push({ label: s.warmup.description, duration: s.warmup.duration_minutes, zone: 'recovery' })
  if (s.main_set) steps.push({ label: s.main_set.description, duration: s.main_set.duration_minutes, zone: (sessionType as SessionStep['zone']) ?? 'endurance' })
  if (s.cooldown) steps.push({ label: s.cooldown.description, duration: s.cooldown.duration_minutes, zone: 'recovery' })
  return steps
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `setInterval` count accumulation for timers | `Date.now()` delta with `visibilitychange` resync | ~2020 (iOS PWA era) | Timers survive tab switches |
| `WakeLock` not available on iOS | Available in iOS 16.4 Safari, fixed in PWA in iOS 18.4 | iOS 18.4 (2024) | Still need nosleep.js for users on older iOS |
| ZWO with `Cadence="0"` | Omit `Cadence` attribute when unspecified | Community finding, undated | Avoids Zwift trying to hold 0 RPM |

**Deprecated/outdated:**
- `fitparse` (Python): abandoned; do not use (already in CLAUDE.md "What NOT to Use")
- `EventSource` for ZWO download: SSE is chat-only; use `apiFetch` + `Response` for file download

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Power values in ZWO are FTP fractions (not percentage integers) | Architecture Patterns, Pattern 3 | Wrong values would cause Zwift to play at wrong intensity; caught at ZWO-05 acceptance test |
| A2 | `<textevent>` must be a child of the enclosing FreeRide block | Architecture Patterns, Pattern 3 | TextEvent might be ignored or cause parse error; caught at ZWO-05 |
| A3 | `sportType` value must be `"bike"` (not `"cycling"` or `"ride"`) | Common Pitfalls 3 | File silently fails to import in Zwift; caught at ZWO-05 |
| A4 | nosleep.js `enable()` must be called in a user-gesture handler (not on mount) on iOS | Code Examples (wake lock hook) | iOS may ignore enable() if called outside user gesture; mitigation: call on first user interaction |
| A5 | Wake Lock on iOS 18.4 PWA works reliably; on < 18.4 nosleep.js fallback is needed | Common Pitfalls 1 | If nosleep.js is insufficient, user sees screen dim during session; no code fix; UX only |
| A6 | Timer hook should use 250ms interval (not 1000ms) to avoid missing second boundaries | Architecture Patterns, Pattern 1 | 1000ms may visually skip seconds; minor UX issue |

**High-risk assumptions:** A1, A2, A3 are all resolved by the ZWO-05 acceptance test (real Zwift import). A4 requires physical iOS device testing (IOS-03).

---

## Open Questions

1. **nosleep.js TypeScript declaration**
   - What we know: nosleep.js 0.12.0 has no `@types` package
   - What's unclear: Whether to use a local `.d.ts` shim or dynamic import with cast
   - Recommendation: Add a `frontend/src/types/nosleep.d.ts` shim with `declare module 'nosleep.js'` exporting a default class with `enable()` and `disable()` methods

2. **`session.structure` field type on the Session interface in api.ts**
   - What we know: Current `Session` interface in `api.ts` types `structure` as `{ text?: string } | string | null` (from `SessionCard.tsx` usage)
   - What's unclear: Whether `getSessionToday()` actually returns the full structure object `{warmup, main_set, cooldown}` or only a stringified version
   - Recommendation: The planner must add a task to extend the `Session` interface with a `structure` type that includes the segment shape, and verify the backend returns the full JSONB object (not a stringified string)

3. **Free-ride duration step labels for "Ride anyway" path**
   - What we know: D-11 says `DuringSessionScreen` reads `freeRideDurationMins` from Zustand and generates 3 generic placeholder steps
   - What's unclear: Whether these use `zone: 'endurance'` or `zone: undefined` for the zone strip color
   - Recommendation: Use `zone: 'endurance'` for main_set and `zone: 'recovery'` for warmup/cooldown — consistent with how plan.py assigns zones

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| npm (nosleep.js) | IOS-01 | ✓ | 0.12.0 | No fallback; required |
| Physical iOS device | IOS-03 acceptance test | Unknown (human) | -- | Cannot simulate; must use physical device |
| Zwift app | ZWO-05 acceptance test | Unknown (human) | -- | Cannot automate; manual import required |
| xml.etree.ElementTree | ZWO generation | ✓ | Python stdlib | No fallback needed |

**Missing dependencies with no fallback:**
- Physical iOS device: required for IOS-03. Planner must add a `checkpoint:human-verify` task for iOS testing.
- Zwift app access: required for ZWO-05. Planner must add a `checkpoint:human-verify` task for real Zwift import.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Frontend unit framework | Vitest 4.x + React Testing Library 16.x |
| Frontend e2e framework | Playwright 1.61.x |
| Unit config file | `frontend/vitest.config.ts` |
| E2e config file | `frontend/playwright.config.ts` |
| Unit quick run | `cd frontend && npx vitest run src/tests/` |
| E2e run | `cd frontend && npx playwright test` |
| Backend unit run | `cd api && python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|--------------|
| ZWO-01 | generate_zwo() produces valid XML with correct root elements | unit (Python) | `pytest tests/sports_science/test_zwo.py -x` | ❌ Wave 0 |
| ZWO-02 | Power fractions clamped to 0.0-2.0 | unit (Python) | `pytest tests/sports_science/test_zwo.py::test_power_fraction_bounds -x` | ❌ Wave 0 |
| ZWO-03 | Pre-FTP: FreeRide segments with textevent, not SteadyState | unit (Python) | `pytest tests/sports_science/test_zwo.py::test_pre_ftp_uses_freeride -x` | ❌ Wave 0 |
| ZWO-04 | sportType='bike', no Cadence attribute when not set | unit (Python) | `pytest tests/sports_science/test_zwo.py::test_sport_type_and_cadence -x` | ❌ Wave 0 |
| ZWO-05 | Real Zwift import | manual | n/a — human checkpoint | n/a |
| IOS-01 | useWakeLock hook: falls back to nosleep.js when wakeLock not in navigator | unit (Vitest) | `cd frontend && npx vitest run src/tests/useWakeLock.test.ts` | ❌ Wave 0 |
| IOS-02 | useSessionTimer: visibilitychange resyncs elapsed, not reset | unit (Vitest) | `cd frontend && npx vitest run src/tests/useSessionTimer.test.ts` | ❌ Wave 0 |
| IOS-03 | Timer and wake lock on physical iOS Safari | manual | n/a — human checkpoint | n/a |
| -- | DuringSessionScreen: auto-advances after timer hits 0 | unit (Vitest) | `cd frontend && npx vitest run src/tests/session.test.tsx` | ❌ Wave 0 |
| -- | ZWO export modal: shows preview, triggers download, stays open on error | unit (Vitest) | `cd frontend && npx vitest run src/tests/zwo-modal.test.tsx` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `cd frontend && npx vitest run src/tests/ --reporter=dot`
- **Per wave merge:** `cd frontend && npx vitest run src/tests/ && python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green + both manual checkpoints (IOS-03 + ZWO-05) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `api/tests/sports_science/test_zwo.py` — covers ZWO-01 through ZWO-04
- [ ] `frontend/src/types/nosleep.d.ts` — TypeScript declaration for nosleep.js
- [ ] `frontend/src/tests/useSessionTimer.test.ts` — covers IOS-02
- [ ] `frontend/src/tests/useWakeLock.test.ts` — covers IOS-01
- [ ] `frontend/src/tests/session.test.tsx` — covers timer auto-advance + "Session complete" overlay
- [ ] `frontend/src/tests/zwo-modal.test.tsx` — covers ZWO export modal

---

## Security Domain

> `security_enforcement: true` in config.json; `security_asvs_level: 1`.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes | `get_current_user` dependency already applied on all session routes; ZWO export route must use same dependency |
| V3 Session Management | no | Supabase JWTs handle session; no new session state |
| V4 Access Control | yes | ZWO export must filter by both `session_id` AND `user_id` from JWT — never trust path param alone (same pattern as existing PATCH /sessions/{id}) |
| V5 Input Validation | yes | `validate_uuid(session_id)` before DB query; already a utility in `api/utils.py` |
| V6 Cryptography | no | No new crypto; no secrets in generated ZWO XML |

### Known Threat Patterns for this Stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR on ZWO export (session belongs to another user) | Elevation of privilege | Always filter `.eq("user_id", user_id)` in addition to `.eq("id", session_id)` — existing pattern from sessions.py PATCH |
| XSS via session data in XML | Tampering | `xml.etree.ElementTree` auto-escapes text content; safe by default |
| Path traversal via session_id | Tampering | `validate_uuid()` before any DB call; existing utility |
| Unvalidated power fraction in ZWO | Integrity | Clamp and validate in `generate_zwo()` before building any XML element; ZWO-02 |

---

## Project Constraints (from CLAUDE.md)

- **Architecture:** LLM never emits physiological numbers — ZWO power fractions must come only from `ftp` profile field or the 100W default constant, never from LLM output.
- **Tech Stack:** React + Vite + Tailwind (frontend), FastAPI (backend), no fitparse, no claude-agent-sdk.
- **Light mode only:** No pure blacks; design system tokens from PRD apply to all Phase 5 components.
- **No em dashes:** Session complete copy, ZWO modal copy, and all other Phase 5 strings must use commas/semicolons/colons instead.
- **XML generation:** `xml.etree.ElementTree` (stdlib) — no new library needed.
- **fitdecode not fitparse:** Not applicable to Phase 5 (no FIT parsing in this phase).
- **Rejected:** `nosleep.js` is NOT on the rejected list; it is explicitly approved in CLAUDE.md §"Integrations".

---

## Sources

### Primary (MEDIUM confidence)
- `frontend/src/screens/DuringSessionScreen.tsx` — Phase 4 stub being replaced
- `frontend/src/components/session/SessionStepList.tsx` — Reused component interface
- `frontend/src/components/session/SessionCard.tsx` — "Export to Zwift" button stub location
- `api/routes/sessions.py` — Auth pattern, validate_uuid, query filter pattern
- `api/sports_science/plan.py` — `session.structure` shape: `{warmup, main_set, cooldown}`
- `.planning/phases/05-during-session-and-zwo-export/05-UI-SPEC.md` — Approved design contract

### Secondary (LOW confidence — web search)
- [h4l/zwift-workout-file-reference](https://github.com/h4l/zwift-workout-file-reference/blob/master/zwift_workout_file_tag_reference.md) — Community-documented ZWO format
- [MDN Screen Wake Lock API](https://developer.mozilla.org/en-US/docs/Web/API/Screen_Wake_Lock_API) — visibilitychange re-acquire pattern
- [Chrome for Developers — Wake Lock](https://developer.chrome.com/docs/capabilities/web-apis/wake-lock) — Best practice implementation
- [FastAPI Custom Responses](https://fastapi.tiangolo.com/reference/responses/) — Response + Content-Disposition pattern
- nosleep.js 0.12.0 — npm registry, 332K weekly downloads, github.com/richtr/NoSleep.js

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are pre-existing in the project except nosleep.js (verified OK)
- Architecture: HIGH — codebase read directly; patterns match existing sessions.py and SessionCard.tsx
- ZWO format: MEDIUM — community-documented, no official Zwift schema; ZWO-05 acceptance test is the safety net
- Wake lock / iOS behavior: MEDIUM — MDN + Chrome docs, but iOS-specific behavior requires physical device test (IOS-03)
- Pitfalls: MEDIUM — derived from code inspection and ZWO community reference

**Research date:** 2026-06-21
**Valid until:** 2026-07-21 (30 days; ZWO format and Wake Lock API are stable)
