# Phase 11: Ride Analysis Dashboard - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 11 (new + modified)
**Analogs found:** 11 / 11

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|---------------|
| `backend/routes/_stream_utils.py` (new) | utility | transform | `backend/sports_science/zones.py` (pure-function style) | role-match |
| `backend/routes/rides.py` — `parse_fit_stream()` (add) | utility/parser | file-I/O | `backend/routes/rides.py::parse_fit_file` (same file, lines 66-~200) | exact |
| `backend/routes/rides.py` — `GET /{ride_id}/stream` (add) | route/controller | request-response | `backend/routes/sessions.py::export_session_zwo` (lines 271-345) + `backend/routes/rides.py::list_rides` (lines 632-660) | exact |
| `backend/sports_science/zones.py` — `time_in_hr_zones()` (add) | service (pure fn) | transform | `backend/sports_science/zones.py::calculate_hr_zones` (lines 31-53) | exact |
| `tests/sports_science/test_zones.py` (append) | test | CRUD/unit | existing tests in same file | exact |
| `tests/api/test_rides_stream.py` (new) | test | request-response | `tests/api/test_rides.py` (upload/list route tests) | role-match |
| `frontend/src/lib/api.ts` — `RideStream` + `getRideStream()` (add) | service/fetcher | request-response | `frontend/src/lib/api.ts::getRides` (lines 154-160) + `Ride` interface (84-98) | exact |
| `frontend/src/components/rides/RideChart.tsx` (new) | component | transform/render | `frontend/src/components/progress/PmcChart.tsx` (full file) + `frontend/src/components/session/ZoneChip.tsx` | exact |
| `frontend/src/screens/AnalysisScreen.tsx` (new) | component/screen | request-response | `frontend/src/screens/ProgressScreen.tsx` (query + loading/empty/error state patterns) | role-match |
| `frontend/src/router.tsx` (modify) | route config | request-response | existing `AppLayout` children block (lines 172-204) | exact |
| `frontend/src/components/nav/BottomTabBar.tsx` / `DesktopSidebar.tsx` (modify) | component/nav | event-driven | same files, existing `TABS`/`NAV_ITEMS` arrays | exact |
| `frontend/src/components/history/RideRow.tsx` (modify) | component | event-driven | same file (existing collapsed-row `<button>` block) | exact |
| `frontend/src/tests/rideChart.test.tsx` (new) | test | CRUD/unit | `frontend/src/tests/history.test.tsx` / `AppLayout.test.tsx` | role-match |

## Pattern Assignments

### `backend/routes/_stream_utils.py` (new utility, transform)

**Analog:** `backend/sports_science/zones.py` (pure-function, no DB/IO style) and the RESEARCH.md code examples (already codebase-verified).

**Core pattern — presence + downsample** (from `11-RESEARCH.md` Code Examples, verbatim, ready to use):
```python
def detect_presence(channel_values: list[float | None]) -> bool:
    """A channel is 'present' iff it has more than one distinct non-null value (D-11-03)."""
    return len({v for v in channel_values if v is not None}) > 1

def downsample(series: list[dict], target_interval_secs: int = 3, max_points: int = 4000) -> list[dict]:
    n = len(series)
    if n == 0:
        return series
    interval = max(target_interval_secs, -(-n // max_points))  # ceil division
    return series[::interval]
```
No imports needed beyond stdlib — keep this file dependency-free like `zones.py`.

---

### `backend/routes/rides.py` — `parse_fit_stream()` (new function, additive)

**Analog:** `parse_fit_file()`, same file, lines 66-~200 (`backend/routes/rides.py`).

**Imports pattern** (already present at top of file, lines 27-47) — reuse as-is, no new imports required beyond stdlib `datetime`:
```python
import fitdecode
from typing import Optional
from datetime import datetime, timezone
```

**Parser skeleton to copy (structure only — do NOT copy the alignment logic, see Pitfall 1/2 in RESEARCH.md):**
```python
def parse_fit_stream(file_bytes: bytes) -> Optional[dict]:
    """
    Sibling to parse_fit_file (RIDE-01). Unlike parse_fit_file, every channel
    array MUST be the same length and index-aligned to elapsed seconds since
    start_time — insert None for gaps, never skip an index (RESEARCH Pitfall 1).
    Compute elapsed seconds as (record.timestamp - start_time).total_seconds(),
    not array index (RESEARCH Pitfall 2). Read enhanced_altitude/enhanced_speed
    first, fall back to altitude/speed (RESEARCH Pitfall 5).
    """
    try:
        with fitdecode.FitReader(
            io.BytesIO(file_bytes),
            error_handling=fitdecode.ErrorHandling.WARN,
        ) as reader:
            for frame in reader:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                if frame.name == "session":
                    ts = frame.get_value("start_time", fallback=None)
                    ...
                    continue
                if frame.name == "lap":
                    # capture lap boundary seconds-from-start into lap_bounds
                    continue
                if frame.name != "record":
                    continue
                # build one aligned row per record, None for missing channels
    except Exception:
        logger.warning("parse_fit_stream failed", exc_info=True)
        return None
```
Reuse the same `try/except -> None on total failure` contract as `parse_fit_file` so the route's existing 422 pattern (below) applies unchanged.

---

### `backend/routes/rides.py` — `GET /{ride_id}/stream` (new route)

**Analog A (IDOR scoping, T-11-01):** `backend/routes/sessions.py::export_session_zwo`, lines 297-320 (copy verbatim, `sessions` → `rides`, `session_id` → `ride_id`):
```python
user_id = current_user["user_id"]
validate_uuid(ride_id, "ride_id")   # 400 before any DB call
supabase = await _get_async_supabase()

result = await (
    supabase.table("rides")
    .select("id, user_id, raw_fit_path")
    .eq("id", ride_id)
    .eq("user_id", user_id)   # IDOR guard — dual filter, not just id
    .execute()
)
if not result.data:
    raise HTTPException(
        status_code=404,
        detail={"error": "ride_not_found", "detail": "No ride found for this user with the given id"},
    )
```

**Analog B (route decorator + Depends pattern):** `backend/routes/rides.py::list_rides`, lines 632-645:
```python
@router.get("/{ride_id}/stream")
async def get_ride_stream(
    ride_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    ...
```

**Storage download + 404/422 error handling (T-11-02, T-11-03) — mirrors `upload_fit`'s size-cap/parse-fail pattern** (`rides.py` lines 485-507):
```python
if not ride["raw_fit_path"]:
    raise HTTPException(status_code=404, detail={"error": "ride_not_found", "detail": "No stored file for this ride"})
try:
    file_bytes = await supabase.storage.from_("fits").download(ride["raw_fit_path"])
except Exception:
    raise HTTPException(status_code=404, detail={"error": "ride_not_found", "detail": "Stored file unavailable"})

parsed = await asyncio.to_thread(parse_fit_stream, file_bytes)  # D-12: CPU-bound, off-thread
if parsed is None:
    raise HTTPException(status_code=422, detail={"error": "fit_parse_failed", "detail": "Could not read this ride file"})
```

**LTHR resolution (Pitfall 3 — read `profiles.lthr` only, no fallback call):**
```python
profile_result = await (
    supabase.table("profiles").select("lthr").eq("user_id", user_id).execute()
)
lthr = profile_result.data[0]["lthr"] if profile_result.data else None
hr_zone_distribution = None
if lthr is not None and channels.get("heart_rate"):
    hr_zone_distribution = time_in_hr_zones(hr_array, lthr).value
```

---

### `backend/sports_science/zones.py` — `time_in_hr_zones()` (add, TRUST-01)

**Analog:** `calculate_hr_zones()`, same file, lines 31-53. Full implementation already drafted in `11-RESEARCH.md` (Pattern 2) and is ready to paste with no material changes:
```python
def time_in_hr_zones(hr_array: list[float], lthr: float) -> ToolResult:
    """RIDE-04: seconds and percentage of ride time spent in each HR zone.
    Reuses calculate_hr_zones for boundaries (D-11-02)."""
    zones = calculate_hr_zones(lthr).value
    total = len(hr_array)
    counts = [0] * len(zones)
    for hr in hr_array:
        for i, z in enumerate(zones):
            lower, upper = z["lower_bpm"], z["upper_bpm"]
            if hr >= lower and (upper is None or hr < upper):
                counts[i] += 1
                break
    result = [
        {"zone": z["zone"], "name": z["name"], "seconds": counts[i],
         "pct": round(100 * counts[i] / total, 1) if total else 0.0}
        for i, z in enumerate(zones)
    ]
    return ToolResult(
        value=result,
        unit="seconds",
        methodology="Coggan/Allen time-in-zone from LTHR-derived HR-zone boundaries",
        inputs={"lthr": lthr, "total_seconds": total},
    )
```
Same `ToolResult(value=..., unit=..., methodology=..., inputs=...)` contract as `calculate_power_zones`/`calculate_hr_zones`/`estimate_lthr_from_max_hr` — do not deviate from this shape.

---

### `frontend/src/lib/api.ts` — `RideStream` interface + `getRideStream()` (add)

**Analog:** `Ride` interface (lines 84-98) + `getRides()` (lines 154-160):
```typescript
export async function getRides(): Promise<Ride[]> {
  const res = await apiFetch('/api/rides/')
  if (!res.ok) throw new Error(`getRides failed: ${res.status}`)
  ...
}
```

**Pattern to copy exactly (from RESEARCH.md, already matches `getRides` shape):**
```typescript
export interface RideStreamPoint {
  t: number
  power: number | null
  heart_rate: number | null
  cadence: number | null
  speed: number | null
  altitude: number | null
  distance: number | null
}
export interface RideZoneDistribution { zone: number; name: string; seconds: number; pct: number }
export interface RideStream {
  series: RideStreamPoint[]
  channels: Record<'power' | 'heart_rate' | 'cadence' | 'speed' | 'altitude' | 'distance', boolean>
  laps: number[]
  hr_zone_distribution: RideZoneDistribution[] | null
}

export async function getRideStream(rideId: string): Promise<RideStream> {
  const res = await apiFetch(`/api/rides/${rideId}/stream`)
  if (!res.ok) throw new Error(`getRideStream failed: ${res.status}`)
  return res.json() as Promise<RideStream>
}
```
Uses the same `apiFetch` wrapper (lines 1-23) that injects the Supabase JWT — no new auth code needed on the frontend.

---

### `frontend/src/components/rides/RideChart.tsx` (new)

**Analog A (chart chrome):** `frontend/src/components/progress/PmcChart.tsx` (full file, 259 lines) — the only existing multi-series Recharts component.

**Imports + axis-tick constant to copy (lines 1-13, 40):**
```tsx
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from 'recharts'
const AXIS_TICK = { fontSize: 11, fill: 'var(--color-ink-3)', fontVariantNumeric: 'tabular-nums' as const }
```

**Card + chart shell to copy (lines 129, 168-169, 177-202, adapted per-channel, height 200 not 240 per UI-SPEC):**
```tsx
<div className="card-elev" style={{ padding: '16px 12px 8px' }}>
  <div style={{ height: 200, width: '100%' }}>
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} syncId="ride" margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--color-line-2)" vertical={false} />
        <XAxis dataKey="t" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: 'var(--color-line)' }} />
        <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={38} />
        <Tooltip content={<CustomSyncedTooltip />} />
        {laps.map((t) => (
          <ReferenceLine key={t} x={t} stroke="var(--color-line)" strokeDasharray="3 3" />
          // do NOT pass isFront or alwaysShow — removed in Recharts v3
        ))}
        <Line type="monotone" dataKey={channelKey} stroke={channelColor} strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  </div>
</div>
```

**Tooltip component pattern (structure to copy, content differs — synced readout row instead of a floating tooltip):** `PmcTooltip` in `PmcChart.tsx` lines 50-87 shows the `card-elev` + `payload`-driven row-list convention; RideChart's readout row is a persistent bar (not a hover-only tooltip), but reuses the same `card-elev`, `stat-num`, `--color-ink`/`--color-ink-2` styling.

**Analog B (zone color/label reuse, Pattern 4 / Don't Hand-Roll):** `frontend/src/components/session/ZoneChip.tsx` (full file, 47 lines) — reuse `ZoneType`, `ZONE_VAR`, `ZONE_LABEL`, and the `<ZoneChip>` component directly for the time-in-zone rows. Do not hand-roll a second zone-color map.
```tsx
import { ZoneChip, type ZoneType } from '../session/ZoneChip'
const ZONE_ORDER: ZoneType[] = ['recovery', 'endurance', 'tempo', 'threshold', 'vo2']
```

---

### `frontend/src/screens/AnalysisScreen.tsx` (new)

**Analog:** `frontend/src/screens/ProgressScreen.tsx` (query pattern lines 96-98, loading/empty/error copy lines 221-245).

**Query pattern to copy:**
```tsx
const ridesQuery = useQuery({ queryKey: ['rides'], queryFn: getRides })
const streamQuery = useQuery({
  queryKey: ['ride-stream', rideId],
  queryFn: () => getRideStream(rideId!),
  enabled: !!rideId,
  staleTime: Infinity,
})
```

**Loading spinner to copy verbatim (from `router.tsx` `AuthGate`/`FirstRunGate`, lines 56-60 and 92-96 — same markup both places, this is the established loading affordance):**
```tsx
<div className="w-8 h-8 rounded-full border-2 border-t-transparent animate-spin"
     style={{ borderColor: 'var(--color-blue-6)', borderTopColor: 'transparent' }}
     aria-label="Loading" />
```

**Empty/error state copy to mirror exactly (ProgressScreen.tsx lines ~221, ~235, ~245):** "No rides yet" heading + "Upload a .FIT file..." body; "Could not load history. Tap to retry." → adapt to "Could not load ride data. Tap to retry." per UI-SPEC Copywriting Contract.

**"Latest ride" default lookup (Don't Hand-Roll — no new backend endpoint):** reuse `getRides()` (already imported pattern in `ProgressScreen.tsx`), take `rides[0].id` client-side when `:rideId` param is absent.

---

### `frontend/src/router.tsx` (modify — add routes)

**Analog:** existing `AppLayout` children array, lines 172-204. Insert two new route objects following the exact same shape (`path`, `element`, `ErrorBoundary: RouteErrorFallback`):
```tsx
{
  path: 'rides/:rideId',
  element: <AnalysisScreen />,
  ErrorBoundary: RouteErrorFallback,
},
{
  path: 'analysis',
  element: <AnalysisScreen />,
  ErrorBoundary: RouteErrorFallback,
},
```
Import `AnalysisScreen` alongside the other screen imports (lines 12-17). No new gate components needed — these routes sit inside the existing `AuthGate` → `FirstRunGate` → `AppLayout` chain, same as `progress`/`agenda`.

---

### `frontend/src/components/nav/BottomTabBar.tsx` + `DesktopSidebar.tsx` (modify — add tab)

**Analog:** existing `TABS`/`NAV_ITEMS` const arrays (both files, lines 4-9). Add one entry, no new styling:
```tsx
import { Activity } from 'lucide-react'
// insert after Progress, before Coach, per UI-SPEC ordering:
{ to: '/analysis', label: 'Analysis', Icon: Activity },
```
Rendering logic (`.map(({ to, label, Icon }) => ...)`) is unchanged in both files — active-state styling (`--color-brand`, dot indicator / left-border) applies automatically to the new tab with zero new code.

---

### `frontend/src/components/history/RideRow.tsx` (modify — add link)

**Analog:** same file's existing collapsed-row `<button>` block (lines 67-80+) and `ComplianceChip` styling convention (inline `style={{ fontSize, fontWeight, color }}` objects, lines 18-45).
```tsx
import { Link } from 'react-router'
// added inside the collapsed row, alongside existing date/chip/stats:
<Link to={`/rides/${ride.id}`} style={{ fontSize: 13, fontWeight: 600, color: 'var(--color-brand)' }}>
  View analysis
</Link>
```
Do not restyle or remove any existing element in this file (UI-SPEC explicit constraint — the table→bars redesign is Phase 12's job).

---

### `frontend/src/components/AppLayout.tsx` (modify — ROUTE_TITLES)

**Analog:** existing `ROUTE_TITLES` map + `title` resolution, lines 8-14, 23.
```tsx
const ROUTE_TITLES: Record<string, string> = {
  '/': 'Today',
  '/agenda': 'Agenda',
  '/progress': 'Progress',
  '/analysis': 'Analysis',
  '/chat': 'Coach',
  '/settings': 'Settings',
}
// dynamic /rides/:rideId needs a startsWith fallback since ROUTE_TITLES is keyed by exact pathname:
const title = pathname.startsWith('/rides/') ? 'Analysis' : (ROUTE_TITLES[pathname] ?? 'PacerAI')
```

---

### Tests

**`tests/sports_science/test_zones.py` (append):** follow existing test structure in this file for `calculate_hr_zones` — hand-checked HR array in, exact seconds/pct assertions out.

**`tests/api/test_rides_stream.py` (new):** analog is `tests/api/test_rides.py` (upload/list route integration tests) — same `httpx.AsyncClient` + JWT-fixture pattern, asserting 404 on wrong user, 404 on missing `raw_fit_path`, 422 on corrupt file, `channels["altitude"]` per fixture, `len(laps) == 6` (RESEARCH Pitfall 4 — not 7).

**`frontend/src/tests/rideChart.test.tsx` (new):** analog is `frontend/src/tests/history.test.tsx` / `AppLayout.test.tsx` — Vitest + `@testing-library/react`, render with `channels.altitude=false`, assert no elevation `card-elev` chart present in the DOM.

## Shared Patterns

### IDOR-safe scoped lookup (T-11-01)
**Source:** `backend/routes/sessions.py::export_session_zwo`, lines 297-320
**Apply to:** `GET /rides/{id}/stream` route handler
```python
validate_uuid(ride_id, "ride_id")
result = await (
    supabase.table("rides").select(...).eq("id", ride_id).eq("user_id", user_id).execute()
)
if not result.data:
    raise HTTPException(status_code=404, detail={"error": "ride_not_found", ...})
```

### ToolResult-wrapped physiological calculation (TRUST-01)
**Source:** `backend/sports_science/zones.py::calculate_hr_zones`, lines 31-53
**Apply to:** `time_in_hr_zones()`
```python
return ToolResult(value=..., unit=..., methodology=..., inputs={...})
```

### CPU-bound parse off the event loop (D-12)
**Source:** `backend/routes/rides.py::upload_fit`, line 498
**Apply to:** the new stream route
```python
parsed = await asyncio.to_thread(parse_fit_stream, file_bytes)
```

### Recharts styling conventions
**Source:** `frontend/src/components/progress/PmcChart.tsx`, lines 40, 129-232
**Apply to:** `RideChart.tsx` (all channel panels)
CSS-var strokes, `AXIS_TICK` constant, `isAnimationActive={false}`, `card-elev` wrapper, no `isFront`/`alwaysShow` on `ReferenceLine` (Recharts v3).

### Zone color/label single source of truth
**Source:** `frontend/src/components/session/ZoneChip.tsx`
**Apply to:** `RideChart.tsx`'s time-in-zone section
`ZONE_VAR`, `ZONE_LABEL`, `<ZoneChip>` — do not hand-roll a second map.

### TanStack Query fetch pattern
**Source:** `frontend/src/screens/ProgressScreen.tsx`, lines 96-98; `frontend/src/lib/api.ts::getRides`
**Apply to:** `AnalysisScreen.tsx`
`useQuery({ queryKey: [...], queryFn: ... })`; `staleTime: Infinity` for immutable per-id resources (matches `DuringSessionScreen`/`ChatScreen`/`SettingsScreen` convention per RESEARCH.md).

### Loading spinner
**Source:** `frontend/src/router.tsx::AuthGate`/`FirstRunGate`, lines 56-60
**Apply to:** `AnalysisScreen.tsx` loading state
`w-8 h-8 rounded-full border-2 border-t-transparent animate-spin`, `border-color: var(--color-blue-6)`.

## No Analog Found

None — every file in this phase has a strong existing analog in the codebase (this phase is "connect existing pieces," per RESEARCH.md Summary).

## Metadata

**Analog search scope:** `backend/routes/`, `backend/sports_science/`, `frontend/src/lib/`, `frontend/src/components/`, `frontend/src/screens/`, `frontend/src/router.tsx`, `tests/`
**Files scanned:** `backend/routes/rides.py`, `backend/routes/sessions.py`, `backend/sports_science/zones.py`, `frontend/src/lib/api.ts`, `frontend/src/components/progress/PmcChart.tsx`, `frontend/src/components/session/ZoneChip.tsx`, `frontend/src/router.tsx`, `frontend/src/components/nav/BottomTabBar.tsx`, `frontend/src/components/nav/DesktopSidebar.tsx`, `frontend/src/components/history/RideRow.tsx`, `frontend/src/components/AppLayout.tsx`, `frontend/src/screens/ProgressScreen.tsx`
**Pattern extraction date:** 2026-07-09
