# Phase 12: Athletic Redesign - Pattern Map

**Mapped:** 2026-07-09
**Files analyzed:** 17
**Analogs found:** 15 / 17

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `frontend/src/index.css` (@theme tokens, `.stat-num`/`.stat-num-hero`, `--cockpit-*`) | config | transform | itself (existing `@theme` block) | exact |
| `frontend/index.html` (font `<link>`) | config | n/a | itself (existing Inter link) | exact |
| `frontend/src/lib/zones.ts` (new) | utility | transform | `frontend/src/lib/format.ts` (`ZONE_META`/`zoneColor`) | exact (extraction source) |
| `frontend/src/components/ui/button.tsx` (no code change, token-only fix) | component | request-response | itself | exact |
| `frontend/src/components/ui/PromptChip.tsx` (new, extracted) | component | event-driven | `frontend/src/screens/ChatScreen.tsx` local `PromptChip` (byte-identical to `OnboardingScreen.tsx`'s copy) | exact |
| `frontend/src/components/ui/card.tsx` (new, shadcn add) | component | request-response | existing shadcn blocks (`button.tsx`, `badge.tsx`) | role-match |
| `frontend/src/screens/DuringSessionScreen.tsx` (JSX-only, lines 389+) | component | event-driven / streaming (timer) | itself (persistence logic frozen; only styling changes) | exact |
| `frontend/src/components/session/WorkoutProfileChart.tsx` (geometry reused, not imported as-is into cockpit) | component | transform | itself (`toSegments()` + flexBasis pattern) | exact (pattern donor) |
| `frontend/src/components/session/SessionCard.tsx` | component | request-response | itself (existing Button/StatTile integration points) | exact |
| `frontend/src/screens/TodayScreen.tsx` | component | request-response | itself; zone-dot → mini-bar pattern donor is `WorkoutProfileChart.tsx` segment styling | exact |
| `frontend/src/screens/AgendaScreen.tsx` | component | request-response | itself; same mini-bar treatment as TodayScreen | role-match |
| `frontend/src/components/progress/WeeklyLoadChart.tsx` | component | transform | itself (Recharts `<Cell>` coloring, `./week` helper already imported) | exact |
| `frontend/src/components/history/RideRow.tsx` | component | transform | `frontend/src/components/history/ComplianceChip.tsx` (already reused elsewhere in same file) | exact |
| `frontend/src/components/session/ZoneChip.tsx` | component | transform | `frontend/src/lib/format.ts` (canonical zone map to migrate to) | exact |
| `frontend/src/components/session/SessionStepList.tsx` (likely deletion, not migration) | component | transform | dead code — no analog needed, confirm via grep before any change | n/a |
| `frontend/src/components/AppLayout.tsx` (header only) | component | request-response | itself (existing `<header>` block; wrapping divs frozen) | exact |
| `frontend/src/screens/SettingsScreen.tsx` | component | CRUD (auth actions) | new shadcn `card.tsx` block + `button.tsx` variants | role-match |
| `frontend/src/screens/LoginScreen.tsx` (`BrandMark`/`ZONE_SPECTRUM`, hoist target) | component | transform | `frontend/src/components/DesktopSidebar.tsx` (consumer of hoisted constant) | role-match |

## Pattern Assignments

### `frontend/src/lib/zones.ts` (utility, transform) — new file

**Analog:** `frontend/src/lib/format.ts` (canonical shape already correct, just needs extracting + `zoneLabel()` added)

**Current canonical pattern to extract** (`frontend/src/lib/format.ts` lines ~30-51):
```typescript
export type ZoneKey = 'recovery' | 'endurance' | 'tempo' | 'threshold' | 'vo2'

export interface ZoneMeta {
  color: string
  label: string
  pctLow: number
  pctHigh: number
}

export const ZONE_META: Record<ZoneKey, ZoneMeta> = {
  recovery: { color: 'var(--color-zone-recovery)', label: 'Recovery', pctLow: 0, pctHigh: 55 },
  endurance: { color: 'var(--color-zone-endurance)', label: 'Endurance', pctLow: 56, pctHigh: 75 },
  tempo: { color: 'var(--color-zone-tempo)', label: 'Tempo', pctLow: 76, pctHigh: 90 },
  threshold: { color: 'var(--color-zone-threshold)', label: 'Threshold', pctLow: 91, pctHigh: 105 },
  vo2: { color: 'var(--color-zone-vo2)', label: 'VO2 Max', pctLow: 106, pctHigh: 120 },
}

export function zoneColor(type: string | null): string {
  if (type && type in ZONE_META) return ZONE_META[type as ZoneKey].color
  return 'var(--color-ink-3)'
}
```

**What must change during extraction (per RESEARCH.md type-reconciliation note):** `pctHigh` must become `number | null` to match `DuringSessionScreen`'s local `ZONE_META` (which allows `null` for vo2's open-ended upper bound) — `DuringSessionScreen.powerTarget()` branches on `pctHigh ? ... : ...`. Add `zoneLabel()` (new, not in `format.ts` today) since `ZoneChip.tsx`'s local `ZONE_LABEL` map needs a home too.

**Re-export shim to add to `lib/format.ts`** (so existing import sites in `SessionCard.tsx`/`WorkoutProfileChart.tsx` keep working unchanged):
```typescript
export { ZONE_META, zoneColor, type ZoneKey } from './zones'
```

**4 duplicate maps to delete and repoint at `lib/zones.ts`:**
- `TodayScreen.tsx` lines 21-31 (`ZONE_VAR` + `isValidZone()`)
- `AgendaScreen.tsx` lines 14-21 (local `ZONE_VAR`, alongside a correct `ZONE_META` import at line 12 — collapse to one import)
- `DuringSessionScreen.tsx` lines 29-35 (`ZONE_META`) — keep local: `powerTarget()` (37-45), `formatTimer()` (47-52), `formatClock()` (54-63), `validZone()` (65-68); these are timer helpers, not zone-map duplication
- `ZoneChip.tsx` lines 7-21 (`ZONE_VAR` + `ZONE_LABEL`) — shown in full below
- `SessionStepList.tsx` lines 12-18 — likely deletion, confirm zero import sites via `grep -rn "SessionStepList" frontend/src` before touching

**`ZoneChip.tsx` current pattern to replace** (full file read, 47 lines):
```typescript
export type ZoneType = 'recovery' | 'endurance' | 'tempo' | 'threshold' | 'vo2'

const ZONE_VAR: Record<ZoneType, string> = {
  recovery:  '--color-zone-recovery',
  endurance: '--color-zone-endurance',
  tempo:     '--color-zone-tempo',
  threshold: '--color-zone-threshold',
  vo2:       '--color-zone-vo2',
}

const ZONE_LABEL: Record<ZoneType, string> = {
  recovery:  'Recovery',
  endurance: 'Endurance',
  tempo:     'Tempo',
  threshold: 'Threshold',
  vo2:       'VO2max',
}

export function ZoneChip({ zone, label }: ZoneChipProps) {
  const cssVar = ZONE_VAR[zone]
  return (
    <span
      className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium"
      style={{
        backgroundColor: `color-mix(in srgb, var(${cssVar}) 15%, transparent)`,
        color: `var(${cssVar})`,
        fontSize: 12, fontWeight: 500, lineHeight: 1.4,
      }}
    >
      {label ?? ZONE_LABEL[zone]}
    </span>
  )
}
```
After migration, `ZoneChip` imports `ZoneKey`, `zoneColor`, `zoneLabel` from `@/lib/zones` (or `@/lib/format`) instead of local maps; the badge JSX/color-mix treatment is unchanged (no visual regression is specified for `ZoneChip` itself — only its data source).

**Note on `ZoneChip.tsx` usage:** repo-wide check shows it is not imported by `SessionCard`, `TodayScreen`, `AgendaScreen`, or `DuringSessionScreen` (they all render inline zone badges). Re-run `grep -rn "ZoneChip" frontend/src` before assuming live usage.

---

### `frontend/src/index.css` (config, transform) — Foundation Fixes §1-4, §7

**Analog:** itself — current `@theme` block (full read, lines 1-90)

**Exact current state to diff against:**
```css
@theme {
  --color-blue-6: #228BE6;
  --color-blue-7: #1B73C0;
  --color-ink:    #1A2230;
  --color-ink-2:  #5F646E;
  --color-ink-3:  #888C93;
  --color-line:   #DFE0E2;
  --color-surface: #FFFFFF;
  --color-bg:     #F2F4F7;
  --color-bg-2:   #F6F6F7;
  --color-brand:   #1F6FE5;
  --color-achieve: #F76707;
  --color-good:      #2B8A5B;
  --color-bad:       #C0341D;
  --color-zone-recovery:  #2B8A5B;
  --color-zone-endurance: #228BE6;
  --color-zone-tempo:     #F0A030;
  --color-zone-threshold: #E8590C;
  --color-zone-vo2:       #C92A2A;
  --font-family-sans: "Inter", ui-sans-serif, system-ui, sans-serif;
}

.stat-num {
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  font-weight: 800;   /* BUG: unloaded weight, synthesized bold */
}
```

**Additions specified verbatim in `12-UI-SPEC.md` §1-4, §7 (copy exactly, no new colors invented):**
```css
--color-primary:              var(--color-brand);
--color-primary-foreground:   #FFFFFF;
--color-destructive:          var(--color-bad);
--color-secondary:            var(--color-bg-2);
--color-secondary-foreground: var(--color-ink);
--color-accent:                var(--color-blue-0);
--color-accent-foreground:    var(--color-brand);
--color-background:           var(--color-surface);
--color-foreground:           var(--color-ink);
--color-border:                var(--color-line);
--color-input:                 var(--color-line);
--color-ring:                  var(--color-brand);
--font-family-display: "Barlow Condensed", "Inter", ui-sans-serif, sans-serif;

--color-cockpit-bg:      #14171D;
--color-cockpit-surface: #1D2129;
--color-cockpit-ink:     #F2F3F5;
--color-cockpit-ink-2:   #9AA0AC;
--color-cockpit-line:    #2A2F3A;
```

**`.stat-num` split (replaces the single class above):**
```css
.stat-num {
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  font-weight: 700;
}
.stat-num-hero {
  font-family: var(--font-family-display);
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
  font-weight: 700;
}
```

**`frontend/index.html` font link — current state:** single `<link>` loading `Inter:wght@400;500;600;700` only. Replace with:
```html
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap" rel="stylesheet" />
```

---

### `frontend/src/components/ui/button.tsx` (component, request-response) — no code change, token-fix only

**Analog:** itself (full file read, 65 lines) — confirms the token-fix in `index.css` is complete and correct; no `button.tsx` edits needed.

**Token references confirmed** (`cva` variant block, lines 12-22):
```typescript
default: "bg-primary text-primary-foreground hover:bg-primary/90",
destructive: "bg-destructive text-white hover:bg-destructive/90 ...",
outline: "border bg-background shadow-xs hover:bg-accent hover:text-accent-foreground ...",
secondary: "bg-secondary text-secondary-foreground hover:bg-secondary/80",
ghost: "hover:bg-accent hover:text-accent-foreground ...",
link: "text-primary underline-offset-4 hover:underline",
```
This is the exact and complete set of tokens the `index.css` additions above must cover — no extra token is referenced anywhere else in this file.

**Removal target once tokens land:** `SessionCard.tsx` lines 212-220 have an inline override compensating for the missing tokens:
```typescript
<Button
  variant="default"
  style={{ backgroundColor: 'var(--color-brand)', color: '#fff' }}  // DELETE once tokens fixed
>
  Start session  {/* RENAME to "Start ride" per D-6 */}
</Button>
```

---

### `frontend/src/components/ui/PromptChip.tsx` (component, event-driven) — new file, extraction

**Analog:** `frontend/src/screens/ChatScreen.tsx` lines 85-119 (byte-identical to `frontend/src/screens/OnboardingScreen.tsx` lines 113-147 — verified both, only one shown)

**Pattern to extract verbatim, no visual changes:**
```typescript
function PromptChip({
  label,
  onClick,
  disabled,
}: {
  label: string
  onClick: () => void
  disabled?: boolean
}) {
  const [hover, setHover] = useState(false)
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        padding: '8px 14px',
        borderRadius: '999px',
        border: '1px solid var(--color-line)',
        backgroundColor: hover && !disabled ? 'var(--color-bg-2)' : 'var(--color-surface)',
        color: 'var(--color-ink-2)',
        fontSize: '14px',
        fontFamily: 'var(--font-family-sans)',
        cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.6 : 1,
        transition: 'background-color 0.15s',
        whiteSpace: 'nowrap',
      }}
    >
      {label}
    </button>
  )
}
```
Extract to `frontend/src/components/ui/PromptChip.tsx` unchanged, export it, delete both local copies, update both screens' imports.

---

### `frontend/src/screens/DuringSessionScreen.tsx` (component, event-driven) — JSX-only rebuild

**Analog:** itself — persistence logic (lines 1-388) is frozen and must not be used as a pattern to copy elsewhere; only lines 389+ (JSX return) are the pattern-mapping target.

**Frozen boundary (do not touch, do not use as an analog for other files' state logic):** `restoredRef`/`computeRestoredState()` (145-161, 190), `currentIndex`/`completedDurationSecs`/`stepStartEpoch` (198-203), `useSessionTimer` call (208), pause logic (218-233), `buildPayload`/`goNext` (243-270), three persistence `useEffect`s (272-295), fast-forward effect + `fastForwardSteps()` (125-143, 305-322), `finishSession` (181-188).

**Exact JSX regions to restyle (render-layer only):**
- Background wash (line 397): `backgroundColor: color-mix(in srgb, ${zoneColor} 7%, var(--color-surface))` → `var(--color-cockpit-bg)`
- Hero block (lines 505-549): currently timer-as-hero (96px Inter 700, lines 507-519) + zone-lozenge power target (30px, lines 523-541) — invert per UI-SPEC: watts at `clamp(96px, 18vw, 160px)` Barlow Condensed 700 `--color-cockpit-ink`; timer demoted to `clamp(48px, 10vw, 72px)` Barlow Condensed 600 `--color-cockpit-ink-2`
- Pause/Skip/End buttons (lines 579-632): plain `<button>`s stay custom (Foundation Fixes §3 exception for this screen only) — only re-theme border/text from `--color-line`/`--color-ink-2` to `--color-cockpit-line`/`--color-cockpit-ink-2`
- Session-complete early return (lines 326-371): stays light-mode; only the CTA color changes (line 356, `var(--color-blue-6)` → `var(--color-achieve)`)
- `100dvh` (4 occurrences: 334, 391, 690, 723) and `env(safe-area-inset-*)` (341-342, 463-464): preserve exactly, in all branches touched

**Net-new JSX (no existing analog in this file — build fresh, following the cockpit token scheme above):**
- No-FTP effort-word+RPE hero fallback (D-4) — does not exist yet; `powerTarget()` (lines 37-45) already branches on `ftp == null` but only produces a percentage string for the existing lozenge treatment, not the new hero-scale JSX
- Session profile rail (D-3) — does not exist in this file; reuse `WorkoutProfileChart`'s layout algorithm, not the component as-is (see next section)

---

### `frontend/src/components/session/WorkoutProfileChart.tsx` (component, transform) — geometry donor, not direct reuse

**Analog:** itself (full file, 144 lines) — imports `zoneColor` correctly from `lib/format.ts` (line 1), already the pattern to generalize.

**Proportional-sizing pattern to copy for the cockpit rail** (`toSegments()` lines 34-51, flexBasis/flexGrow render lines 69-114):
```typescript
// Segment layout algorithm — reuse this math for the cockpit rail's step-based segments
// (current component only handles 3 fixed segments: warmup/main_set/cooldown;
// cockpit rail needs 1 segment per SessionStep, which can be more granular for free rides)
```
Do not import `WorkoutProfileChart` into `DuringSessionScreen.tsx` as a drop-in component — it is not prop-compatible with per-step segments. Build a new rail element inside `DuringSessionScreen.tsx` using the same `flexBasis`/`flexGrow` proportional-width approach, with three visual states per segment: current block "lit" (full zone-color + glow/border), elapsed "dimmed" (`color-mix(... 35%, var(--color-cockpit-bg))`), upcoming (standard zone-color opacity).

**Height change for Today-hub reuse (D-6):** current fixed `height: 34` (line 73) — grow to 56-64px when used in `SessionCard.tsx`.

---

### `frontend/src/components/progress/WeeklyLoadChart.tsx` (component, transform)

**Analog:** itself (full file, 133 lines)

**Current pattern to remove** (`JUMP_FACTOR` + per-bar `<Cell>` coloring, lines 23, 116-125):
```typescript
const JUMP_FACTOR = 1.5
// ...
fill={jump ? 'var(--color-zone-tempo)' : 'var(--color-zone-endurance)'}
```

**Replacement pattern (two-tone, current-week highlight):** reuse the already-imported `weekStartOf()` helper from `./week` (line 13, already used at line 45 to build the 8-week bucket range) to compare each bucket's week-start against `weekStartOf(new Date())`:
```typescript
fill={isCurrentWeek ? 'var(--color-brand)' : 'var(--color-ink-3)'}
```
`ReferenceLine` average marker (lines 107-114) stays unchanged — do not touch.

---

### `frontend/src/components/history/RideRow.tsx` (component, transform)

**Analog:** `frontend/src/components/history/ComplianceChip.tsx` (lines 19-46) — already reused elsewhere in the same file (line 108, collapsed-row header) — reuse this same component for the new paired-bar row rather than building a new compliance indicator.

**Table to remove** (lines 245-314): single-row `<table>` rendered only when `ride.compliance_pct != null`, with hardcoded literal `"Planned: 100%"` (line 288).

**Replacement spec (per UI-SPEC):** two stacked 8px bars, `border-radius: 4px` — "Planned" track (`--color-line` fill, 100% width) and "Actual" bar (width `min(150, compliance_pct)%`, color `--color-good` when `compliance_pct >= 90` else `--color-warn` — same threshold `ComplianceChip` already uses internally, confirm exact threshold value when editing `ComplianceChip.tsx`).

---

### `frontend/src/screens/SettingsScreen.tsx` (component, CRUD) — card redesign

**Analog:** new shadcn `card.tsx` block (not yet installed — `npx shadcn add card`, official registry, follows the same pattern as the 7 already-installed blocks in `components.json`)

**Current pattern to replace** (three `<section>` blocks: Training 65-93, Profile 98-124, Account 129-143, separated by manual divider `<div>`s at 95, 126):
```typescript
<section>...</section>
<div style={{ height: 1, background: 'var(--color-line)' }} />  {/* manual divider, replaced by Card boundaries */}
```
→ `<Card><CardHeader><CardTitle>...</CardTitle></CardHeader><CardContent>...</CardContent></Card>` per section.

**Off-token color fixes (Foundation Fixes §4):**
```typescript
// line 117 — currently invalid (undefined --color-accent, silently falls back to inherited --color-ink)
style={{ color: 'var(--color-accent)' }}  →  style={{ color: 'var(--color-brand)' }}   // Re-send magic link

// lines 136-137 — currently a working hex fallback, not a bug per se, but drop it once token exists
style={{ borderColor: 'var(--color-destructive, #dc2626)', color: 'var(--color-destructive, #dc2626)' }}
  →  <Button variant="destructive">  // Sign out — token now correctly resolves via index.css fix above
```

**Buttons:** both plain `<button>`s (115-122 magic-link, 133-142 sign-out) convert to `<Button variant="link">` and `<Button variant="destructive">` respectively.

---

### `frontend/src/components/DesktopSidebar.tsx` / `frontend/src/screens/LoginScreen.tsx` (component, request-response) — brand mark hoist

**Analog:** `LoginScreen.tsx`'s `BrandMark` component (lines 15-30) — the only existing implementation of the zone-spectrum wordmark pattern.

**Pattern to hoist** (currently page-local, `ZONE_SPECTRUM` gradient constant, lines 10-11):
```typescript
const ZONE_SPECTRUM = 'linear-gradient(90deg, ...)'  // across all 5 zone tokens
// rendered as: 36px "Pace" wordmark + 3px tall, 72px wide rounded gradient bar beneath
```
Recommendation (per RESEARCH.md): hoist `ZONE_SPECTRUM` into `lib/zones.ts` alongside the rest of the zone system, so `DesktopSidebar.tsx` imports it directly rather than reaching into a screen-local constant. Scale down for the sidebar: "Pace" wordmark from `text-4xl`(36px) to ~20px for the 240px sidebar width; same gradient bar treatment beneath.

---

## Shared Patterns

### Zone color/label lookup
**Source:** `frontend/src/lib/format.ts` (existing canonical `ZONE_META`/`zoneColor()`), consolidating into new `frontend/src/lib/zones.ts`
**Apply to:** `ZoneChip.tsx`, `TodayScreen.tsx`, `AgendaScreen.tsx`, `DuringSessionScreen.tsx` (zone map only, not its timer helpers), and any cockpit rail / mini-bar rendering
**Rule:** never write a 6th local zone map — 5 duplicates already exist and this phase's entire purpose includes retiring them.

### Button styling
**Source:** `frontend/src/components/ui/button.tsx` (`cva` variants), once `index.css` token block lands
**Apply to:** every light-surface screen's CTAs (`SessionCard`, `TodayScreen`, `SettingsScreen`) — `<Button variant="default"|"outline"|"link"|"destructive"|"ghost">` replaces hand-rolled inline-styled `<button>`s
**Exception:** `DuringSessionScreen.tsx`'s Pause/Skip/End/session-complete controls stay custom `<button>`s against `--cockpit-*` tokens — do not migrate these to `<Button>`.

### Proportional zone-colored bars
**Source:** `frontend/src/components/session/WorkoutProfileChart.tsx` `toSegments()` + `flexBasis`/`flexGrow` layout (lines 34-51, 79-113)
**Apply to:** cockpit session profile rail (D-3, per-step segments), Today-hub "Coming up" mini-bars (D-6), Agenda row mini-bars (D-9) — reuse the layout math, not the component's fixed 3-segment prop shape.

### Shared pill-button component
**Source:** `frontend/src/screens/ChatScreen.tsx` lines 85-119 (byte-identical `OnboardingScreen.tsx` lines 113-147)
**Apply to:** new `frontend/src/components/ui/PromptChip.tsx` — pure extraction, zero visual change.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| Cockpit no-FTP effort-word+RPE hero display (new JSX inside `DuringSessionScreen.tsx`) | component (sub-region) | request-response | Genuinely new UI; `powerTarget()`'s existing null-FTP percentage-string branch is a different (smaller-scale) treatment, not a hero-scale analog |
| Session profile rail (new JSX inside `DuringSessionScreen.tsx`) | component (sub-region) | transform | Does not exist in this file at all today; nearest pattern is `WorkoutProfileChart`'s layout algorithm (see Pattern Assignments), used as a geometry donor, not a direct analog |
| `frontend/src/components/ui/card.tsx` (shadcn add) | component | request-response | Not yet installed in this codebase; the other 7 shadcn blocks establish the install/style pattern to follow but none is itself a "Card" |

## Metadata

**Analog search scope:** `frontend/src/{lib,components,screens,hooks}`, `frontend/index.html`, `frontend/src/index.css`
**Files scanned:** ~18 (all files named in `12-CONTEXT.md` and `12-RESEARCH.md`'s Current Codebase Inventory)
**Pattern extraction date:** 2026-07-09
