# Phase 11: Ride Analysis Dashboard - Research

**Researched:** 2026-07-09
**Domain:** FIT-file time-series parsing (Python/fitdecode) + server-side HR-zone maths (TRUST-01) + Recharts multi-chart hover-sync visualization (React/TS)
**Confidence:** HIGH (all core findings verified directly against the installed codebase, installed package source, and the two placed fixture files — not training-data guesses)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

| ID | Decision | Rationale |
|----|----------|-----------|
| D-11-01 | Serve ride time series via parse-on-demand: a new `GET /api/rides/{id}/stream` re-downloads the stored `.fit` from Supabase Storage and re-parses it. No time-series persistence, no migration. | A 30-min ride parses in ~10ms. Persisting arrays adds a table, a write path, and storage cost for zero user-visible benefit at current ride lengths. |
| D-11-02 | Time-in-zone is computed by a new Python tool `time_in_hr_zones`, reusing `calculate_hr_zones` for boundaries. Returned as part of the stream payload. | TRUST-01. One definition of a zone in the codebase. |
| D-11-03 | Channel presence rule: a channel is "present" iff it has more than one distinct non-null value. Absent channels are omitted from the payload and get no chart, no card, no lap-table column. | This hides elevation and GPS on indoor Zwift files. Real sensors vary; a flat channel means no sensor. |
| D-11-04 | Server-side downsample to a target of ~1 point / 3s, capped so no payload exceeds ~4000 points. | Recharts on mobile Safari (the PWA target) degrades past ~4k points. A 3h ride stays under the cap. |
| D-11-05 | New top-level route `/rides/:rideId` under `AppLayout`; the History tab's rows link into it. A dedicated Analysis tab is added showing the most recent ride by default. | Keeps History as the list; Analysis is the deep-dive. Matches the existing tab pattern in `BottomTabBar` / `DesktopSidebar`. **Research correction: "History tab" no longer exists as a routed screen — see Pitfall 6 / Sources. `RideRow` (the component this decision refers to) now renders inside `ProgressScreen`'s "Ride log" section; `/history` redirects to `/progress`. The link target and nav-tab-count implications of this decision are unchanged; only the file that hosts `RideRow` differs from what this decision's prose assumes.** |
| D-11-06 | Recharts `syncId` provides cross-chart hover sync. No custom crosshair code. | Built-in. Deletes the fiddliest part of the prototype. |
| D-11-07 | The zone-model selector and power-smoothing toggle from the prototype are OUT of scope. | The selector conflicts with single-source-of-truth (D-11-02). Smoothing is a later nice-to-have. |

### Threats / Mitigations

| ID | Threat | Mitigation |
|----|--------|------------|
| T-11-01 | Cross-user ride access via `/stream` | Query scoped to `user_id` from JWT sub (existing T-04-03 pattern). Return 404 if the ride isn't the caller's. |
| T-11-02 | Storage download of a missing/oversized object | 404 if `raw_fit_path` is null. Reuse the 25 MB cap already enforced at upload; no re-check needed since only already-accepted files are stored. |
| T-11-03 | Corrupt stored file crashes the stream parse | fitdecode `ErrorHandling.WARN` (same as upload). On unreadable file return 422 with structured detail. |

### Requirements (RIDE-01..RIDE-12)

See `<phase_requirements>` below for the full table with research support mapped per requirement.

### Roadmap (waves, as locked in CONTEXT.md)

- **Wave 0** (backend data layer): 11-01 (sibling parser + presence + downsample, RIDE-01/02/03), 11-02 (`time_in_hr_zones` tool, RIDE-04)
- **Wave 1** (stream endpoint): 11-03 (`GET /rides/{id}/stream`, RIDE-05, threats T-11-01/02/03)
- **Wave 2** (frontend): 11-04 (API type + fetcher, RIDE-06), 11-05 (`RideChart` component, RIDE-07/08/09), 11-06 (Analysis screen/route/nav tab, RIDE-10/11)
- **Wave 3** (verification): 11-07 (fixtures + tests, RIDE-12) — **research correction: the CONTEXT.md Wave 3 assertion `len(laps) == 7` against `zwift_ride_30min.fit` is factually wrong; verified fixture content has 6 laps. See Pitfall 4.**

### Explicitly Out of Scope (Deferred)

- Time-series persistence (a `ride_streams` table). Revisit only if parse-on-demand latency becomes a problem.
- Zone-model selector (%max vs LTHR) and power-smoothing toggle (D-11-07).
- A local file-input loader. The tab reads from the DB via the stream endpoint; upload stays in History (now: Progress screen's Ride log section).

### Non-negotiable trust constraint (TRUST-01)

Every physiological number (HR-zone boundaries, time-in-zone percentages) MUST come from a deterministic tool in `backend/sports_science/` that returns a `ToolResult` with a named methodology. No zone boundary or zone percentage may be computed in TypeScript. Any zone maths in JS is a defect regardless of correctness.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RIDE-01 | Sibling parser extracts full per-second arrays (power, HR, cadence, speed, altitude, distance) + lap boundaries from raw FIT bytes | See Pattern-driven design in Architecture Patterns; **Pitfall 1** (alignment — do not reuse `parse_fit_file`'s "append only when present" logic) and **Pitfall 2** (use real elapsed-seconds from timestamps, not array index) are the two correctness-critical findings for this requirement |
| RIDE-02 | Channel presence detected per D-11-03, returned as a `channels` map | `detect_presence()` code example verified against both fixtures (Zwift: `altitude`→0 distinct non-null values→False; hilly: `altitude`→635 distinct values→True) |
| RIDE-03 | Series downsampled per D-11-04 before serialisation | `downsample()` code example; Assumption A2 on stride-sampling vs. bucket-mean/LTTB |
| RIDE-04 | `time_in_hr_zones(hr_array, lthr)` ToolResult reusing `calculate_hr_zones` | Full implementation example in Architecture Patterns / Pattern 2, modeled on `compute_tss`'s and `calculate_hr_zones`'s existing structure and exclusive-upper-bound zone-membership convention |
| RIDE-05 | `GET /api/rides/{id}/stream` returns series, channels, laps, HR-zone distribution, scoped to caller | Full request-handling sequence in the System Architecture Diagram; Pattern 1 (IDOR scoping) and Pitfall 3 (LTHR resolution has no live fallback — read `profiles.lthr` only) are both load-bearing for this requirement |
| RIDE-06 | `RideStream` type + `getRideStream(id)` fetcher in `api.ts` | Code example provided, mirrors `getRides()`/`getLatestPmc()` shape exactly |
| RIDE-07 | `RideChart` renders one chart per present channel, shared `syncId`, lap `ReferenceLine`s, CSS-var strokes | Pattern 3 (Recharts styling, copied from `PmcChart.tsx`) + Anti-Pattern note on removed `isFront`/`alwaysShow` props in Recharts v3 |
| RIDE-08 | Synced readout row: time (`Mm SSs`), lap number, per-channel value at hovered point | Note under "State of the Art" / general findings: existing `formatTimer` in `DuringSessionScreen.tsx` uses `MM:SS` colon format, not the `Mm SSs` letter format this requirement specifies — a new formatter is needed, distinct from the existing one (not a reuse case) |
| RIDE-09 | Time-in-zone bar + rows from backend distribution, `--color-zone-*` tokens, absent if HR not present | Pattern 4 (zone color/label reuse from `ZoneChip.tsx`) — Don't Hand-Roll table entry on zone display |
| RIDE-10 | `AnalysisScreen` at `/rides/:rideId` and default `/analysis` (latest ride); new nav tab in `BottomTabBar` + `DesktopSidebar` | Recommended File Targets list; Don't Hand-Roll entry on reusing `getRides()` instead of a new "latest ride" endpoint; Pitfall 6 (5th mobile tab); Open Question 2 (empty state) |
| RIDE-11 | History `RideRow` links each row to `/rides/:id` | **Correction:** `RideRow` is rendered by `ProgressScreen`'s "Ride log" section (not a standalone History screen — `/history` redirects to `/progress`); the link must be added to `frontend/src/components/history/RideRow.tsx` itself, which is shared by both the (dead-routed) `HistoryScreen.tsx` and the live `ProgressScreen.tsx` |
| RIDE-12 | Fixtures + tests (backend zone/channel assertions, frontend absent-elevation-chart assertion) | Validation Architecture section maps each requirement to a test file/command; **Pitfall 4 provides the corrected lap-count assertion (6, not 7)** |
</phase_requirements>

## Summary

This phase is almost entirely a "connect existing pieces" job, not new domain research. The FIT-parsing convention (`fitdecode` + `ErrorHandling.WARN` + `get_value(..., fallback=None)`), the trust-model tool pattern (`ToolResult`, `calculate_hr_zones`), the JWT/IDOR scoping pattern (dual `.eq("id", ...).eq("user_id", ...)` + `validate_uuid`), and the Recharts chart conventions (`ResponsiveContainer`, CSS-var strokes, `isAnimationActive={false}`) are all already established in this codebase and must be copied, not reinvented.

Three things in `11-CONTEXT.md` do not match the current codebase state and need correction before planning: (1) the "History tab" the roadmap describes no longer exists as a routed screen — `RideRow` now lives inside `ProgressScreen`'s "Ride log" section, and `/history` is a redirect to `/progress`; (2) the "existing LTHR resolution path (profile / `estimate_lthr_from_max_hr` fallback)" does not exist as a live, request-time fallback — LTHR is resolved once at onboarding and stored in `profiles.lthr` (null means "not available", full stop, no fallback call is possible because no `max_hr` is persisted anywhere); (3) the Wave 3 fixture assertion `len(laps) == 7` is factually wrong — both fixtures were verified by direct fitdecode execution to have exactly 6 laps each.

**Primary recommendation:** Build `parse_fit_stream` as a genuinely new sibling parser (not a copy of `parse_fit_file`'s per-channel "append only when present" logic, which produces misaligned arrays) that emits `None`-padded, timestamp-aligned per-second channel arrays plus a `lap_bounds` array computed from the same ride `start_time` used for the time axis. Compute `time_in_hr_zones` as a pure function reusing `calculate_hr_zones`. Resolve LTHR by reading `profiles.lthr` only — never call `estimate_lthr_from_max_hr` from the route. Wire the frontend using the exact `PmcChart.tsx` Recharts conventions and the existing `ZoneChip.tsx` zone-color/label maps.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| FIT byte parsing, channel extraction | API/Backend | Database/Storage (source bytes) | `fitdecode` is Python-only; CPU-bound, must run under `asyncio.to_thread` per D-12 convention already used in `parse_fit_file` |
| Channel presence detection (D-11-03) | API/Backend | — | Pure function on parsed arrays; no reason to ship raw channel-null-check logic to the client |
| Downsampling (D-11-04) | API/Backend | — | Payload-size concern; keeps the wire format small and the frontend dumb |
| HR-zone boundary + time-in-zone maths | API/Backend | — | TRUST-01: no physiological number may be computed in TypeScript |
| Cross-user ride ownership check (T-11-01) | API/Backend | — | JWT `sub` is server-verified; never trust a client-supplied `user_id` |
| Raw `.fit` byte retrieval | Database/Storage (Supabase Storage) | API/Backend (orchestrates the download) | Storage already holds `raw_fit_path`; no new persistence needed (D-11-01) |
| Chart rendering, hover crosshair sync | Browser/Client | — | Recharts `syncId` is a client-side rendering concern; D-11-06 explicitly forbids server involvement here |
| Route/nav for `/rides/:rideId` and `/analysis` | Browser/Client | — | Client-side SPA routing via `react-router`; no SSR tier exists in this stack |
| Query caching (`ride-stream`) | Browser/Client | — | TanStack Query; `staleTime: Infinity` matches the existing pattern for immutable per-id resources (`DuringSessionScreen`, `ChatScreen`, `SettingsScreen`) |

## Standard Stack

### Core (all already installed — verified against the repo's own manifests, not assumed)

| Library | Installed version | Purpose | Source of verification |
|---------|---------|---------|--------------|
| `fitdecode` | 0.11.0 | FIT byte parsing (sibling parser) | `requirements.txt` [VERIFIED: requirements.txt] |
| `numpy` | 2.4.6 | Array ops for downsample/presence checks | `requirements.txt` [VERIFIED: requirements.txt] |
| `pydantic` | 2.13.4 | `ToolResult` model | `requirements.txt` [VERIFIED: requirements.txt] |
| `fastapi` | 0.115.* | Route | `requirements.txt` [VERIFIED: requirements.txt] |
| `recharts` | ^3.8.1 | `RideChart` component | `frontend/package.json` [VERIFIED: package.json] — **note: this is v3, not v2 as `CLAUDE.md`'s stack table states; see Pitfall below** |
| `@tanstack/react-query` | ^5.101.0 | `['ride-stream', rideId]` query | `frontend/package.json` [VERIFIED: package.json] |
| `react-router` | ^8.0.1 | `rides/:rideId`, `analysis` routes | `frontend/package.json` [VERIFIED: package.json] — single-package import (`from 'react-router'`, not `react-router-dom`), confirmed in `router.tsx` |
| `lucide-react` | ^1.21.0 | `Activity` icon for the new nav tab | `frontend/package.json` [VERIFIED: package.json] |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Uniform-stride downsampling | LTTB (Largest-Triangle-Three-Buckets) via a library like `downsample-lttb` | LTTB better preserves visual spikes; adds a new dependency for a problem simple stride-sampling solves adequately here (NP/TSS are already computed server-side from the *full* array before downsampling, so downsample fidelity only affects the chart, not any physiological number). Recommend stride-sampling or simple bucket-mean; no new package. |
| Recharts built-in `syncId` | Custom `onMouseMove` + shared React context crosshair | D-11-07/D-11-06 already lock this decision: use `syncId`, no custom code. |

**Installation:** None required — every library this phase touches is already a dependency. No `npm install` / `pip install` needed.

## Package Legitimacy Audit

**No new packages are introduced by this phase.** Every library referenced above (`fitdecode`, `numpy`, `pydantic`, `fastapi`, `recharts`, `@tanstack/react-query`, `react-router`, `lucide-react`) is already installed and pinned in `requirements.txt` / `frontend/package.json`. The Package Legitimacy Gate is not applicable — skip it.

## Architecture Patterns

### System Architecture Diagram

```
Browser (AnalysisScreen)
  │
  │  useQuery(['ride-stream', rideId], () => getRideStream(rideId), { staleTime: Infinity })
  ▼
GET /api/rides/{id}/stream  ──(Vercel rewrite strips /api)──▶  FastAPI: rides.router "/{ride_id}/stream"
  │
  ├─ 1. validate_uuid(ride_id)                                         [T-11-01 defence-in-depth]
  ├─ 2. supabase.table("rides").select(...).eq("id", ride_id)
  │       .eq("user_id", jwt.sub).execute()  → 404 if empty            [T-11-01 IDOR guard]
  ├─ 3. if raw_fit_path is None → 404                                  [T-11-02]
  ├─ 4. bytes = await supabase.storage.from_("fits").download(raw_fit_path)
  │       (wrap in try/except → 404 on failure)                        [T-11-02]
  ├─ 5. parsed = await asyncio.to_thread(parse_fit_stream, bytes)      [D-12 pattern, CPU-bound]
  │       (fitdecode ErrorHandling.WARN; on total parse failure → 422) [T-11-03]
  ├─ 6. channels = detect_presence(parsed)                             [D-11-03, RIDE-02]
  ├─ 7. downsampled = downsample(parsed, target≈1pt/3s, cap=4000)      [D-11-04, RIDE-03]
  ├─ 8. profile = supabase.table("profiles").select("lthr")
  │       .eq("user_id", user_id).execute()
  │    if profile.lthr is not None and channels["heart_rate"]:
  │        hr_zone_distribution = time_in_hr_zones(hr_array, profile.lthr).value  [RIDE-04, TRUST-01]
  │    else:
  │        hr_zone_distribution = None
  └─ 9. return {series, channels, laps, hr_zone_distribution}  (plain JSON, NOT an SSE stream)
       │
       ▼
   RideChart.tsx: one <LineChart syncId="ride"> per present channel
       + <ReferenceLine> per lap boundary + synced hover readout row
       + time-in-zone bars from stream.hr_zone_distribution using ZoneChip color tokens
```

### Recommended File Targets (confirms CONTEXT.md's wave plan against the actual repo layout)

```
backend/routes/rides.py          # add parse_fit_stream() + GET /{ride_id}/stream (same file, additive)
backend/routes/_stream_utils.py  # new: detect_presence(), downsample()
backend/sports_science/zones.py  # add time_in_hr_zones() beside calculate_hr_zones()
frontend/src/lib/api.ts          # add RideStream interface + getRideStream(rideId)
frontend/src/components/rides/RideChart.tsx   # new
frontend/src/screens/AnalysisScreen.tsx       # new
frontend/src/router.tsx          # add rides/:rideId and analysis routes under AppLayout
frontend/src/components/nav/BottomTabBar.tsx  # add Analysis tab (5th tab — see Pitfall)
frontend/src/components/nav/DesktopSidebar.tsx # add Analysis tab
frontend/src/components/history/RideRow.tsx   # add Link to /rides/:id (this is the file ProgressScreen's "Ride log" renders — see Pitfall on History/Progress merge)
```

### Pattern 1: IDOR-safe scoped single-resource lookup (T-11-01)

**What:** Dual-filter on `id` AND `user_id` from the verified JWT `sub`, 404 (not 403) on any mismatch so ride existence can't be enumerated by ID.
**When to use:** Any endpoint that looks up a single row by a path-param ID.
**Example (copied verbatim from `backend/routes/sessions.py:297-319`, the pattern CONTEXT.md calls "existing T-04-03 pattern"):**
```python
user_id = current_user["user_id"]
validate_uuid(ride_id, "ride_id")   # 400 before any DB call — V5 input validation
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

### Pattern 2: ToolResult-wrapped physiological calculation (TRUST-01)

**What:** Every new number returned to the frontend that could be construed as a "physiological number" must originate from a `sports_science/` function returning `ToolResult`.
**Example, modeled directly on `calculate_hr_zones` and `compute_tss`'s structure (source: `backend/sports_science/zones.py`, `backend/sports_science/metrics.py`):**
```python
# backend/sports_science/zones.py — new function alongside calculate_hr_zones
def time_in_hr_zones(hr_array: list[float], lthr: float) -> ToolResult:
    """RIDE-04: seconds and percentage of ride time spent in each HR zone.

    Reuses calculate_hr_zones for boundaries — one definition of a zone
    in the codebase (D-11-02). Zone membership mirrors the exclusive-upper-
    bound convention already documented in calculate_hr_zones's docstring.
    """
    zones = calculate_hr_zones(lthr).value  # [{"zone":1,"name":...,"lower_bpm":...,"upper_bpm":...}, ...]
    total = len(hr_array)
    counts = [0] * len(zones)
    for hr in hr_array:
        for i, z in enumerate(zones):
            lower, upper = z["lower_bpm"], z["upper_bpm"]
            if hr >= lower and (upper is None or hr < upper):
                counts[i] += 1
                break

    result = [
        {
            "zone": z["zone"],
            "name": z["name"],
            "seconds": counts[i],
            "pct": round(100 * counts[i] / total, 1) if total else 0.0,
        }
        for i, z in enumerate(zones)
    ]
    return ToolResult(
        value=result,
        unit="seconds",
        methodology="Coggan/Allen time-in-zone from LTHR-derived HR-zone boundaries",
        inputs={"lthr": lthr, "total_seconds": total},
    )
```

### Pattern 3: Recharts styling conventions (copy from `PmcChart.tsx`, the only existing multi-series chart in the codebase)

```tsx
// Source: frontend/src/components/progress/PmcChart.tsx (existing, verified in repo)
const AXIS_TICK = { fontSize: 11, fill: 'var(--color-ink-3)', fontVariantNumeric: 'tabular-nums' as const }

<div className="card-elev" style={{ padding: '16px 12px 8px' }}>
  <div style={{ height: 240, width: '100%' }}>
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={data} syncId="ride" margin={{ top: 6, right: 8, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--color-line-2)" vertical={false} />
        <XAxis dataKey="t" tick={AXIS_TICK} tickLine={false} axisLine={{ stroke: 'var(--color-line)' }} />
        <YAxis tick={AXIS_TICK} tickLine={false} axisLine={false} width={38} />
        <Tooltip content={<CustomSyncedTooltip />} />
        {stream.laps.map((t) => (
          <ReferenceLine key={t} x={t} stroke="var(--color-line)" strokeDasharray="3 3" />
          // NOTE: do NOT pass isFront or alwaysShow — both removed in Recharts v3
        ))}
        <Line type="monotone" dataKey="power" stroke="var(--color-zone-endurance)" strokeWidth={1.5} dot={false} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  </div>
</div>
```

### Pattern 4: Zone color/label reuse (Don't Hand-Roll — see below)

```tsx
// Source: frontend/src/components/session/ZoneChip.tsx (existing, verified in repo)
export type ZoneType = 'recovery' | 'endurance' | 'tempo' | 'threshold' | 'vo2'
const ZONE_VAR: Record<ZoneType, string> = {
  recovery: '--color-zone-recovery', endurance: '--color-zone-endurance',
  tempo: '--color-zone-tempo', threshold: '--color-zone-threshold', vo2: '--color-zone-vo2',
}
// time_in_hr_zones' zone numbers 1-5 map 1:1 by index to this array:
const ZONE_ORDER: ZoneType[] = ['recovery', 'endurance', 'tempo', 'threshold', 'vo2']
```

### Anti-Patterns to Avoid

- **Computing zone boundaries or percentages in TypeScript:** Any `if (hr > X)` zone-classification logic in `RideChart.tsx` is a TRUST-01 defect regardless of correctness — the backend must send the already-classified `hr_zone_distribution`.
- **Reusing `parse_fit_file`'s "append only when present" array-building for `parse_fit_stream`:** see Pitfall 1 below — this produces channel arrays of different lengths that cannot be zipped into a single per-second series.
- **Calling `estimate_lthr_from_max_hr` from the stream route:** there is no `max_hr` persisted anywhere to feed it (see Pitfall 3). This would be inventing a new resolution path CONTEXT.md explicitly says not to invent.
- **`isFront` / `alwaysShow` props on `ReferenceLine`:** removed in Recharts v3 [CITED: github.com/recharts/recharts/wiki/3.0-migration-guide].

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HR zone boundaries | A JS/TS re-implementation of Coggan/Allen % thresholds | `calculate_hr_zones` (already exists, `backend/sports_science/zones.py`) | TRUST-01; also the boundaries were specifically corrected in Phase 8 (D-06) — a JS copy would silently drift out of sync on the next correction |
| Zone display color/label | New color constants in `RideChart.tsx` | `--color-zone-*` CSS vars + the `ZONE_VAR`/`ZONE_LABEL` maps already in `ZoneChip.tsx` | Single source of truth already exists and is reused by `TodayScreen`, `AgendaScreen`, `SessionStepList`, `DuringSessionScreen` |
| Cross-chart hover crosshair | Custom `onMouseMove` + React context broadcasting hovered index to sibling charts | Recharts `syncId` prop | D-11-06 explicit decision; built-in, zero custom code, works across `LineChart` instances automatically |
| IDOR / ownership check | A new helper function or inline `if ride.user_id != current_user_id` after a non-scoped SELECT | Dual `.eq("id", ...).eq("user_id", ...)` at the query level (Pattern 1 above) | Matches `T-04-03`/`T-05-01` precedent exactly; a post-fetch check is strictly worse (it fetches another user's row into memory before rejecting it) |
| "Latest ride" lookup for default `/analysis` route | A new backend `GET /rides/latest` endpoint | Existing `getRides()` (already returns rides ordered `ride_date desc`) — take `rides[0].id` client-side | Avoids adding a redundant backend endpoint for data the frontend already fetches on `ProgressScreen` |

**Key insight:** Every "hard" primitive this phase needs (zone maths, zone colors, IDOR scoping, hover sync, "latest ride") already has a single, working implementation somewhere in this codebase or in Recharts itself. The actual net-new code is thin: one parser, one presence/downsample utility, one small pure zone-time function, and glue.

## Common Pitfalls

### Pitfall 1: Reusing `parse_fit_file`'s per-channel array-building logic will misalign the chart's X-axis

**What goes wrong:** `parse_fit_file` (existing) appends to `power_array` unconditionally (converting `None`→`0.0`) but appends to `hr_array`/`cadence_array` **only when the sensor value is present**, producing arrays of different, shorter lengths than `power_array`. That's fine for `parse_fit_file`'s only consumer (`compute_tss`, which just needs *a* power array and separate averages), but it is fatal for `parse_fit_stream`: if `heart_rate` has 3 dropout gaps, `hr_array[500]` and `power_array[500]` no longer refer to the same second of the ride, silently corrupting the synced chart and the hover readout.
**Why it happens:** The two parsers have different consumers — `parse_fit_file` never needed positional alignment across channels; `parse_fit_stream` does (every chart shares one X axis via `syncId`).
**How to avoid:** `parse_fit_stream` must build one record per elapsed second (or per FIT record, whichever the sampling strategy is) with **every** channel keyed to the same index, inserting `None` for any channel's gap at that index — never skip an index. Then presence detection and downsampling both operate on these aligned rows.
**Warning signs:** A `RideChart` that shows lap `ReferenceLine`s in slightly the wrong place, or a hover readout that seems to lag/lead the actual chart position, especially on files with real (non-synthetic) sensor dropouts.

### Pitfall 2: Array index is not the same thing as "seconds since ride start" for non-1Hz recording

**What goes wrong:** `parse_fit_file`'s own header comment explicitly warns: "Smart-recording devices (Garmin, Wahoo) may emit fewer than 1 record/sec." Its `duration_secs` calculation already accounts for this by using `last_record_ts - first_record_ts`, not `len(power_samples)`. But if `parse_fit_stream` naively treats `array[i]` as "second `i`" (matching the two synthetic 1Hz test fixtures, which will pass either way), a real user's Garmin/Wahoo file with recording gaps will produce a chart whose X axis silently drifts from wall-clock time, and worse, whose lap `ReferenceLine`s (computed from real timestamps) will land at the wrong X position relative to the (index-based) series.
**Why it happens:** The two placed test fixtures (`zwift_ride_30min.fit`, `hilly_ride_30min.fit`) are synthetic and exactly 1Hz (1800 records over exactly 1800/1799 seconds — verified directly), so this bug is invisible in the fixture-based tests required by RIDE-12.
**How to avoid:** Compute each record's elapsed-seconds value explicitly as `(record.timestamp - start_time).total_seconds()`, using the **same** `start_time` resolution already used by `parse_fit_file` (`session.start_time`, falling back to first record timestamp). Compute `lap_bounds` the same way, from the same `start_time`, so laps and the series always share one time origin. For downsampling with gaps, either interpolate to a uniform grid or downsample by index over the (already timestamp-correct) elapsed-seconds series — do not assume uniform 1Hz spacing.
**Warning signs:** None visible against the placed fixtures — this is a "silent on tests, wrong on real user files" class of bug. Flag explicitly for the coder.

### Pitfall 3: There is no live LTHR-fallback path to call — `profiles.lthr` is the only source

**What goes wrong:** `11-CONTEXT.md`'s Wave 1 plan instructs: "resolve LTHR via the existing profile / `estimate_lthr_from_max_hr` fallback path (do not invent one in the route)." Reading the actual onboarding flow (`backend/sports_science/profile.py`, `backend/routes/onboarding.py`) shows `estimate_lthr_from_max_hr` is called **once, at onboarding time** (Branch B), and its result is written directly into `profiles.lthr`/`profiles.lthr_estimate`. No `max_hr` value is ever persisted to the `profiles` table (confirmed: no `max_hr` column exists anywhere in `backend/` or the Supabase migrations). There is therefore no data available at `/stream` request time to feed `estimate_lthr_from_max_hr` even if the route wanted to call it.
**Why it happens:** `11-CONTEXT.md` was written from the author-supplied PRD without cross-checking the actual onboarding data model; it describes a "fallback path" that never materialized as a request-time capability — LTHR resolution genuinely is a one-shot event that already happened (or didn't) at onboarding.
**How to avoid:** The stream route's LTHR resolution is simply: `SELECT lthr FROM profiles WHERE user_id = :user_id`. If `lthr IS NULL` (Branch C users — "no LTHR, RPE-only"), `hr_zone_distribution` in the response must be `null`, **regardless of whether the ride itself has heart_rate data** — this is correct per TRUST-01 (no LTHR means no zone boundaries can be honestly computed) and mirrors `hr_zones_available` already being `false` for these users.
**Warning signs:** A plan task that tries to call `estimate_lthr_from_max_hr` inside `rides.py`'s stream handler — there is no `max_hr` argument available to pass it.

### Pitfall 4: `11-CONTEXT.md`'s Wave 3 fixture assertion is factually wrong (6 laps, not 7)

**What goes wrong:** `11-CONTEXT.md` line 138 states the Wave 3 test should assert `len(laps) == 7` against `zwift_ride_30min.fit`. Direct execution of `fitdecode.FitReader` against both placed fixtures (verified in this research session) shows **both** fixtures contain exactly **6** `lap` messages, each spanning exactly 300 seconds (5 min × 6 = 30 min), matching the fixture filenames and matching `11-CONTEXT.md`'s own earlier Fixtures section (line 155: "6 laps"). The `len(laps) == 7` figure in the Wave 3 section contradicts the Fixtures section within the same document.
**Why it happens:** Likely a copy-paste/off-by-one slip when the PRD's roadmap doc was authored (possibly confusing "6 laps" with "6 lap-boundary markers create 7 X-axis reference points" — but `laps` as returned by the endpoint should be a list of lap objects/boundaries, and there are 6 `lap` FIT messages).
**How to avoid:** Write the RIDE-12 test asserting `len(laps) == 6` for both fixtures. If the plan wants "7" to represent something else (e.g., 6 lap boundaries + 1 implicit "ride end" marker), that must be an explicit, separately-justified design decision, not silently carried over from CONTEXT.md.
**Warning signs:** A failing test immediately upon running `test_rides_stream.py` for the first time — this pitfall is self-revealing at Wave 3, but flagging it now saves a debugging cycle.

### Pitfall 5: `enhanced_altitude`/`enhanced_speed` vs. `altitude`/`speed` field duplication

**What goes wrong:** Direct fixture inspection shows FIT record frames carry both `altitude` and `enhanced_altitude` (and `speed`/`enhanced_speed`) as separate fields with identical values in both placed fixtures. Some real-world devices only populate one of the pair. Reading only the legacy field name (matching `parse_fit_file`'s existing pattern of reading `power`/`heart_rate`/`cadence` by exact field name) risks silently returning `None` for altitude/speed on a subset of real devices that only emit the `enhanced_*` variant.
**Why it happens:** FIT protocol historically added `enhanced_altitude`/`enhanced_speed` as wider-range successors to `altitude`/`speed`, and different device firmware emits one, the other, or (as in these fixtures) both.
**How to avoid:** Read `enhanced_altitude` first, fall back to `altitude`; same for speed. `frame.get_value("enhanced_altitude", fallback=None) or frame.get_value("altitude", fallback=None)`.
**Warning signs:** Not visible against the placed fixtures (both fields populated identically) — this is a real-world-file risk, not a fixture-test risk.

### Pitfall 6: The mobile bottom nav is already at 4 tabs; adding a 5th changes existing touch-target proportions

**What goes wrong:** `BottomTabBar.tsx` currently renders exactly 4 tabs (`Today`, `Agenda`, `Progress`, `Coach`) using `flex-1` per tab. Adding a 5th `Analysis` tab (per D-11-05/RIDE-10) is a locked decision, not something to relitigate, but it does mean each tab's touch target shrinks by ~20% and the existing visual rhythm (icon + 10px label) should be spot-checked, not assumed identical.
**Why it happens:** D-11-05 was decided against the PRD's original 4-tab assumption; the current codebase's nav (post `project-ui-followups` redesign referenced in memory) already consolidated History into Progress, so this phase is the first to actually grow tab count since that redesign.
**How to avoid:** Not a blocker — implement per D-11-05 as locked — but flag a visual smoke-check (existing `AppLayout.test.tsx` / manual screenshot) as part of Wave 2 verification, and be aware Phase 12 (Athletic Redesign, UI-SPEC already approved, not yet executed) may restyle nav again shortly after — keep the new tab's implementation minimal/conventional so it doesn't need special-case rework.
**Warning signs:** None functional — this is a UI-polish flag, not a correctness bug.

## Code Examples

### Downsample utility (D-11-04) — new, no existing implementation to reuse

```python
# backend/routes/_stream_utils.py
def downsample(series: list[dict], target_interval_secs: int = 3, max_points: int = 4000) -> list[dict]:
    """
    Stride-sample a per-second-aligned series to ~1 point per target_interval_secs,
    capped at max_points so no payload exceeds ~4000 points (D-11-04).

    NP/TSS/zone maths are computed from the FULL series before this function runs —
    downsampling only affects what the chart renders, never a physiological number.
    """
    n = len(series)
    if n == 0:
        return series
    # Effective interval: widen further if target_interval_secs alone would still exceed the cap.
    interval = max(target_interval_secs, -(-n // max_points))  # ceil division
    return series[::interval]
```

### Presence detection (D-11-03) — exact rule from CONTEXT.md, confirmed correct against both fixtures

```python
def detect_presence(channel_values: list[float | None]) -> bool:
    """A channel is 'present' iff it has more than one distinct non-null value (D-11-03)."""
    return len({v for v in channel_values if v is not None}) > 1
```

### Frontend fetcher (RIDE-06) — mirrors existing `getRides()` shape in `api.ts`

```typescript
// frontend/src/lib/api.ts — pattern matches getRides()/getLatestPmc() exactly
export interface RideStreamPoint {
  t: number  // seconds since ride start
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
  laps: number[]  // seconds since ride start, one per lap boundary
  hr_zone_distribution: RideZoneDistribution[] | null
}

export async function getRideStream(rideId: string): Promise<RideStream> {
  const res = await apiFetch(`/api/rides/${rideId}/stream`)
  if (!res.ok) throw new Error(`getRideStream failed: ${res.status}`)
  return res.json() as Promise<RideStream>
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| N/A — this is new functionality | Parse-on-demand (D-11-01) instead of persisting time series | This phase | No migration, no new table; ~10ms re-parse cost per view is acceptable at current ride lengths |
| N/A | `CLAUDE.md`'s stack table lists Recharts 2.x, react-router 7.x | Repo actually has Recharts ^3.8.1 and react-router ^8.0.1 installed | `CLAUDE.md` is stale on these two version numbers; use the installed versions (confirmed via `package.json`), not the CLAUDE.md table, for anything version-sensitive (e.g. `ReferenceLine` props — see Pitfall/Anti-pattern above) |

**Deprecated/outdated:** `ReferenceLine`'s `isFront` and `alwaysShow` props — removed in Recharts v3 [CITED: github.com/recharts/recharts/wiki/3.0-migration-guide]. Do not use them even if training data suggests them from Recharts v2 examples.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | The `CHART_CONFIG` array (RIDE-07) should render charts for power/HR/cadence/speed/altitude but treat `distance` as an auxiliary field for the readout row only, not its own chart | Architecture Patterns / Open Questions | Low — if wrong, planner adds a 6th chart; no correctness issue, just a scope/UX call CONTEXT.md left implicit |
| A2 | Stride-sampling (not bucket-mean or LTTB) is sufficient for the downsample step since physiological numbers are computed from the full array, not the downsampled one | Standard Stack / Code Examples | Low — if a reviewer wants smoother lines, swap stride for bucket-mean without touching any TRUST-01-sensitive code |
| A3 | `hr_zone_distribution` should be `null` whenever `profiles.lthr IS NULL`, even if the ride itself has heart-rate samples | Pitfall 3 | Medium — if wrong (i.e. if the intended behavior is to still show a distribution using some other LTHR source), a Branch-C user would see no zone breakdown even though their ride has HR data; this needs explicit confirmation since it's a UX tradeoff, not purely a technical fact |

## Open Questions

1. **Does `distance` get its own chart, or is it readout-only?**
   - What we know: RIDE-01 requires extracting `distance` per-second; RIDE-07 says "one chart per present channel" but the phase description's channel list (power, HR, cadence, speed, elevation) omits distance.
   - What's unclear: Whether `distance` should render as a 6th line chart or only appear in the synced readout row (and/or drive an x-axis-as-distance toggle, which is explicitly out of scope per D-11-07's "no zone-model selector" spirit — no such toggle was requested).
   - Recommendation: Treat `distance` as readout-only (not its own chart) unless the planner decides otherwise; it's the cheapest interpretation consistent with "no elevation or GPS on Zwift rides" being the headline absent-channel scenario, not "no distance."

2. **Should `AnalysisScreen` have an explicit empty state for zero-rides users?**
   - What we know: `/analysis` defaults to "most recent ride" (D-11-05); `getRides()` can return `[]` for a brand-new user.
   - What's unclear: CONTEXT.md doesn't specify empty-state copy for this screen.
   - Recommendation: Mirror `ProgressScreen`'s existing "No rides yet / Upload a .FIT file..." empty state pattern (same copy, same component shape) rather than inventing new copy.

## Environment Availability

Skipped — this phase has no new external dependencies (no new env vars per `no_new_env: true` in `11-CONTEXT.md` frontmatter, no new services). All required tools (`fitdecode`, Supabase Storage `fits` bucket, Recharts) are already configured and in use elsewhere in the codebase.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Backend framework | pytest 9.1.1 + pytest-asyncio 1.4.0, `asyncio_mode = auto` (no `@pytest.mark.asyncio` needed) [VERIFIED: pytest.ini] |
| Backend config file | `pytest.ini` (`testpaths = tests`) |
| Frontend framework | Vitest (jsdom environment) + `@testing-library/react` [VERIFIED: frontend/vitest.config.ts] |
| Frontend config file | `frontend/vitest.config.ts` |
| Quick run command (backend) | `python -m pytest tests/sports_science/test_zones.py tests/api/test_rides_stream.py -x` |
| Quick run command (frontend) | `cd frontend && npx vitest run src/tests/rideChart.test.tsx` |
| Full suite command | `python -m pytest` (backend) / `cd frontend && npx vitest run` (frontend) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| RIDE-01 | Sibling parser extracts aligned per-second arrays + lap bounds | unit | `pytest tests/api/test_rides_stream.py -k parse -x` | ❌ Wave 0/1 |
| RIDE-02 | Channel presence map correct on both fixtures | unit | `pytest tests/api/test_rides_stream.py -k channels -x` | ❌ Wave 1 |
| RIDE-03 | Downsampled series respects 4000-point cap | unit | `pytest tests/api/test_rides_stream.py -k downsample -x` | ❌ Wave 0 |
| RIDE-04 | `time_in_hr_zones` seconds/pct hand-checked against a known HR array | unit | `pytest tests/sports_science/test_zones.py -k time_in_hr_zones -x` | ❌ Wave 0 (append to existing file) |
| RIDE-05 | `/stream` scoped, 404 on wrong user, 404 on missing `raw_fit_path`, 422 on corrupt file | integration | `pytest tests/api/test_rides_stream.py -x` | ❌ Wave 1 |
| RIDE-06 | `getRideStream` typed fetcher | unit (implicit via component test) | `npx vitest run src/tests/rideChart.test.tsx` | ❌ Wave 2 |
| RIDE-07/08/09 | `RideChart` renders per-present-channel charts, synced readout, zone bars | component | `npx vitest run src/tests/rideChart.test.tsx` | ❌ Wave 2/3 |
| RIDE-10/11 | Route + nav tab + `RideRow` link | component/manual | `npx vitest run src/tests/routerErrorBoundary.test.tsx` (routing smoke) + manual click-through | Partial — routing infra exists, new routes don't |
| RIDE-12 | Fixture-driven backend + frontend assertions per CONTEXT.md (corrected: 6 laps, not 7 — see Pitfall 4) | integration + component | See above | ❌ Wave 3 |

### Sampling Rate
- **Per task commit:** the quick run commands above (backend zone/stream tests; frontend `rideChart.test.tsx`)
- **Per wave merge:** full backend suite (`python -m pytest`) + full frontend suite (`npx vitest run`)
- **Phase gate:** Full suite green before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/api/test_rides_stream.py` — new file, covers RIDE-01, RIDE-02, RIDE-03, RIDE-05, RIDE-12 (backend half)
- [ ] `tests/sports_science/test_zones.py` — append `time_in_hr_zones` tests (RIDE-04); file already exists, no new file needed
- [ ] `frontend/src/tests/rideChart.test.tsx` — new file, covers RIDE-07, RIDE-08, RIDE-09, RIDE-12 (frontend half)
- [ ] No new framework installs needed — pytest/pytest-asyncio and Vitest/RTL are both already configured and used by adjacent test files (`tests/api/test_rides.py`, `frontend/src/tests/history.test.tsx`)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | Reused, not new | Existing `get_current_user` JWT dependency (`backend/auth.py`) — no new auth code needed |
| V3 Session Management | No | No new session state introduced |
| V4 Access Control | Yes | Dual `.eq("id", ...).eq("user_id", ...)` IDOR guard (Pattern 1) — T-11-01 |
| V5 Input Validation | Yes | `validate_uuid(ride_id)` before any DB call (`backend/utils.py`, already exists) |
| V6 Cryptography | No | No new crypto surface |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR via ride ID enumeration | Information Disclosure | Dual-filter query + uniform 404 (never 403, which would confirm the ride exists but belongs to someone else) — matches existing `sessions.py` precedent exactly |
| Missing/deleted Storage object (`raw_fit_path` stale or object never uploaded because `upload_fit`'s Storage step is "best-effort") | Denial of Service (partial) | `raw_fit_path IS NULL` → 404 before attempting download; wrap the `storage.download()` call itself in try/except → 404 on any `StorageApiError`/generic exception, matching the existing best-effort pattern already used for the upload-side `storage.upload()` call |
| Corrupt/malformed `.fit` bytes crash the parser | Denial of Service | `fitdecode.ErrorHandling.WARN` (already the codebase-wide convention) + top-level try/except → 422 structured error, mirroring `parse_fit_file`'s existing `except Exception: return None` → `HTTPException(422, ...)` pattern |
| Oversized Storage object triggers a slow synchronous parse blocking the event loop | Denial of Service | Not a new risk — only files that already passed the 25 MB upload-time cap (`MAX_UPLOAD_BYTES`) can ever be in Storage, so no new size check is needed at stream time (T-11-02 mitigation is exactly this: reuse the existing cap, don't re-implement it) |

## Sources

### Primary (HIGH confidence — verified by direct execution/reading against this repo in this session)
- `backend/routes/rides.py` — existing `parse_fit_file`, `get_user_ftp`, upload pipeline conventions
- `backend/sports_science/zones.py`, `constants.py`, `types.py` — `calculate_hr_zones`, `ToolResult`, HR zone boundary table
- `backend/sports_science/profile.py` — `save_profile`, confirming `profiles.lthr`/`hr_zones_available` are the only persisted LTHR-related fields (no `max_hr` column anywhere)
- `backend/routes/sessions.py` — IDOR-safe scoped-lookup pattern (`export_session_zwo`, `update_session`)
- `backend/auth.py` — JWT verification, `get_current_user` contract
- `.venv/lib/python3.12/site-packages/storage3/_async/file_api.py` — `download()` signature (returns `bytes`), confirming the Storage retrieval pattern for T-11-02
- `tests/fixtures/zwift_ride_30min.fit`, `tests/fixtures/hilly_ride_30min.fit` — directly parsed with `fitdecode.FitReader` in this session to verify record field names (`enhanced_altitude`/`altitude` duplication, `speed`/`enhanced_speed`), lap count (6, not 7), lap timing (exactly 300s per lap), and channel presence counts for `altitude` (0 distinct non-null on Zwift fixture, 635 on hilly fixture)
- `frontend/src/lib/api.ts`, `router.tsx`, `components/nav/BottomTabBar.tsx`, `components/nav/DesktopSidebar.tsx`, `screens/ProgressScreen.tsx`, `screens/HistoryScreen.tsx`, `components/history/RideRow.tsx` — confirmed current 4-tab nav (Today/Agenda/Progress/Coach), confirmed `/history` redirects to `/progress`, confirmed `RideRow` is rendered by `ProgressScreen`'s "Ride log" section
- `frontend/src/components/progress/PmcChart.tsx` — the only existing multi-series Recharts component in the codebase; source of all styling conventions
- `frontend/src/components/session/ZoneChip.tsx` — zone color/label single source of truth
- `frontend/src/index.css` — `--color-zone-*` and other design tokens
- `frontend/package.json`, `requirements.txt`, `pytest.ini`, `frontend/vitest.config.ts` — installed versions and test framework config
- `vercel.json`, `frontend/vite.config.ts` — confirms `/api/*` prefix is a routing-layer rewrite, not present inside the FastAPI app itself

### Secondary (MEDIUM confidence)
- [Recharts 3.0 migration guide](https://github.com/recharts/recharts/wiki/3.0-migration-guide) — `isFront`/`alwaysShow` removal from Reference components [CITED]

### Tertiary (LOW confidence)
- None — all claims in this document trace to a primary source verified in this session.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every version number read directly from the repo's own manifest files, not training data
- Architecture: HIGH — every pattern (IDOR scoping, ToolResult, Recharts styling, nav structure) copied from existing, working code in this repo
- Pitfalls: HIGH — pitfalls 1, 2, 4, 5 were discovered by directly executing `fitdecode` against the actual placed fixtures in this session, not inferred; pitfall 3 (LTHR resolution) was discovered by reading the actual `profiles` schema usage, not assumed from CONTEXT.md's description

**Research date:** 2026-07-09
**Valid until:** 30 days (stable stack; no fast-moving dependencies in this phase's surface area) — but re-verify Pitfall 4's lap-count assumption immediately if the fixture files are ever regenerated/replaced, since the 6-vs-7 discrepancy is fixture-content-dependent, not a general fact.
