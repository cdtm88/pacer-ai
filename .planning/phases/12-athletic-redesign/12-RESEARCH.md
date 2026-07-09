# Phase 12: Athletic Redesign - Research

**Researched:** 2026-07-09
**Domain:** Frontend visual redesign (React 19 + Tailwind v4 + shadcn/ui) — no backend changes
**Confidence:** HIGH (all findings are direct codebase reads, not inference)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **Dark ride cockpit.** The during-session view (`DuringSessionScreen`) becomes a dark cockpit surface. This is a user-approved exception to the PRD "light mode only" MVP constraint, scoped to the session route only. Near-black surfaces in the ink family (for example #14171D); NO pure black (#000) anywhere, per PRD. Everything else in the app stays light mode.
2. **Watts are the hero, not the timer.** On the bike: watt target rendered at arm's-length scale (~120-160px fluid clamp), zone chip above it, timer demoted to large-but-secondary. Matches wireframe section 04 direction A. The existing timer/persistence logic in DuringSessionScreen must not be touched; this is a render-layer rebuild only.
3. **Session profile rail** at the bottom of the cockpit (wireframe direction B): whole workout as proportional zone-colored bars, current block lit, elapsed dimmed. Reuse `WorkoutProfileChart` geometry.
4. **No-FTP fallback** in the cockpit: effort word + RPE ("HARD, 8/10, push") at the same hero scale (wireframe direction D).
5. **Display face for numerals.** Barlow Condensed 600/700 for hero numerals only (watts, timers, KPI stat values). Inter stays for all other UI text. This is a user-approved amendment to the PRD single-sans rule. Also fix: Inter is currently loaded at 400-700 but `.stat-num` requests weight 800 (synthesized bold); load the weights actually used.
6. **Today hub upgrade** (`SessionCard` / `TodayScreen`): objective to ~28px; stat tile row (duration / est TSS / IF) using existing `StatTile` under the workout profile chart (wireframe section 05); profile chart taller and central; one fat full-width "Start ride" primary (brand fill); "Export .zwo" secondary; Mark done/missed collapses to a quiet overflow row; "Coming up" rows get mini zone-colored duration bars instead of 8px dots.
7. **Zone color carries intensity everywhere.** The existing zone token system (`--color-zone-*`) is the identity system; push it further (agenda intensity bars, cockpit accents, profile bars). Zone colors must continue to match the PRD hex values exactly.
8. **Component system unification:**
   - Map shadcn `button.tsx` tokens to the real `@theme` palette in `index.css`; `<Button>` becomes the only button; remove hand-rolled inline CTAs as screens are touched.
   - Single `lib/zones.ts` zone map (currently duplicated in AgendaScreen, SessionStepList, ZoneChip, TodayScreen, DuringSessionScreen).
   - Shared `PromptChip` (currently copy-pasted in OnboardingScreen and ChatScreen).
   - Fix off-token colors: Settings uses undefined `--color-accent` and hardcoded `#dc2626`; both become palette tokens (`--color-bad`).
9. **Progress/Agenda polish:** WeeklyLoadChart history bars go neutral gray with the current week in blue accent (wireframe section 06); RideRow's HTML planned-vs-actual table becomes paired bars + compliance chip; Agenda zone dots become short zone-colored intensity bars.
10. **Shell:** screen titles at ~28px display weight with date eyebrow; bottom tab labels 11px/600 with filled-pill active state; desktop sidebar replaces the 3px left-stripe active state with the same filled pill; the Login zone-spectrum wordmark becomes an app-wide brand mark.
11. **Session-complete screen** is the single sanctioned `--color-achieve` (orange) celebration moment.
12. **Settings redesign** to card-grouped sections with real buttons and proper type scale (currently the weakest screen).

### Delivery order (each ships independently)

A. Foundation: fonts, button/token mapping, shared zone map, `--cockpit-*` tokens.
B. Ride cockpit (biggest win).
C. Today hub.
D. Progress + Agenda.
E. Shell + secondary surfaces (header, tabs, Settings, Login dedupe, Onboarding/Chat migration to shared components).

### Constraints that still bind

- No pure blacks anywhere, including the dark cockpit.
- Contrast rules from PRD: #228BE6 only for large text/fills; small blue text uses blue-7; body copy ink/ink-2.
- No em dashes in any copy.
- iOS Safari is the primary during-session target (wake lock, safe-area insets, dvh: all existing behavior preserved).
- No hand-drawn/sketchy styles; the wireframe's marker aesthetic is a structural reference only, not a visual target.

### Explicitly out of scope

- Strava integration, readiness 0-3 check-in flow, "generate today's session" CTA, generation-limit states (deferred to a later phase).
- Zone-color-field ride variant (wireframe direction C).
- Dark mode for the rest of the app (Phase 2 per PRD).
- Nav IA changes: keep 4 tabs (Today / Agenda / Progress / Coach) + Settings.

### Deferred Ideas

None separately logged beyond "Explicitly out of scope" above — CONTEXT.md uses that section as its deferred-ideas equivalent.
</user_constraints>

<phase_requirements>
## Phase Requirements

No REQUIREMENTS.md IDs are mapped to Phase 12. This phase is explicitly scoped as "visual overhaul of existing screens only; no new product capabilities" (all functional `UI-0x` requirements were satisfied in Phase 4 and remain unchanged in behavior). The 12 locked decisions in `12-CONTEXT.md` and the full contract in `12-UI-SPEC.md` are the authoritative scope document for this phase — the planner should trace tasks to those decision numbers (D-1..D-12) rather than to REQUIREMENTS.md IDs.

| ID | Description | Research Support |
|----|-------------|-------------------|
| N/A | Visual overhaul only, no new REQUIREMENTS.md entries | See `12-UI-SPEC.md` Screen-by-Screen Contract for the authoritative per-screen spec; this document supplies the current-codebase state each spec item modifies. |
</phase_requirements>

## Summary

`12-UI-SPEC.md` already locks every visual/interaction decision (colors, type scale, exact component specs) — this research does **not** re-derive design. Its job is to hand the planner an exact map of what exists in the codebase today, so tasks can be written as precise diffs rather than rediscovery. All findings below come from direct file reads on 2026-07-09, not from documentation lookups (this phase has no new external library to research — no new npm packages, no new APIs).

Three load-bearing facts drive sequencing risk:

1. **The button-token gap is real and total.** `frontend/src/components/ui/button.tsx` (shadcn `new-york` preset) references `bg-primary`, `text-primary-foreground`, `bg-destructive`, `bg-secondary`, `text-secondary-foreground`, `hover:bg-accent`, `text-accent-foreground`, `bg-background`, `border-input`, `ring-ring/50` — **none of `--color-primary`, `--color-primary-foreground`, `--color-destructive`, `--color-secondary`, `--color-secondary-foreground`, `--color-accent`, `--color-accent-foreground`, `--color-background`, `--color-input`, `--color-ring` exist anywhere in `frontend/src/index.css`** (confirmed by full-file read — the `@theme` block only defines the blue/ink/zone/brand scale). Every `<Button variant="default">` in the app today renders on Tailwind/browser defaults unless overridden by an inline `style` (which is exactly why `SessionCard`'s Start button has a hand-rolled `style={{ backgroundColor: 'var(--color-brand)' }}` override — it's compensating for the missing token, not styling for its own sake).
2. **Zone maps are duplicated 5x, not 4x as CONTEXT states**, and one of the 5 duplicate sites is dead code. `DuringSessionScreen.tsx`, `TodayScreen.tsx`, `AgendaScreen.tsx`, and `ZoneChip.tsx` each hand-roll their own `ZONE_VAR`/`ZONE_META` map — plus a fifth copy in `SessionStepList.tsx`, which has **zero import references anywhere in the codebase** (verified via repo-wide grep) and appears to be orphaned Phase-4-era code never wired into `DuringSessionScreen`'s eventual `SessionRunner` implementation. `frontend/src/lib/format.ts` already holds the canonical `ZoneKey`/`ZONE_META`/`zoneColor()` (used correctly by `SessionCard.tsx` and `WorkoutProfileChart.tsx`) — this is the consolidation target UI-SPEC names.
3. **The "Export to Zwift" -> "Export .zwo" copy rename (D-6) will break two existing assertions** in `frontend/src/tests/today.test.tsx` (`getByRole('button', { name: /export to zwift/i })` and an `getAllByText('Export to Zwift').length > 1` check that relies on the button's visible text matching the `ZwoExportModal` panel title). `12-UI-SPEC.md`'s copywriting contract only renames the button, not the modal's internal `<p>Export to Zwift</p>` heading — so after the rename there is exactly one match, not two. This must be an explicit task (update both the component and the test) in whichever plan touches `SessionCard`, not an incidental side effect.

**Primary recommendation:** Execute delivery order A -> E as CONTEXT.md specifies, with Foundation (A) as a hard prerequisite wave — every other slice depends on the `--color-primary/…` token block, the `--font-family-display` addition, and the consolidated `lib/zones.ts` existing first. Do not let any B-E task touch `DuringSessionScreen`'s `SessionRunner` state/hooks (see Common Pitfalls) or the visible text strings asserted in `frontend/src/tests/session.test.tsx`.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Design tokens (`@theme` in `index.css`) | Browser / Client (build-time CSS) | — | Tailwind v4 CSS-first theme; no SSR, no backend involvement |
| Font loading (Google Fonts CDN) | Browser / Client | CDN / Static | `<link>` tags in `index.html`; fetched from `fonts.googleapis.com`, not self-hosted |
| Component visual treatment (Button, Card, zone chips) | Browser / Client | — | Pure React render layer; shadcn/Radix primitives, no server round-trip |
| DuringSessionScreen timer/persistence | Browser / Client | — | `useSessionTimer` (wall-clock math) + `localStorage` (`sessionPersistence.ts`) — entirely client-side, must not be touched by this phase |
| Zone/session data (`type`, `structure`, `rpe_target`) | API / Backend | Database / Storage | Unchanged this phase — redesign consumes existing shapes as-is |
| PWA service worker / offline caching | Browser / Client | CDN / Static | `vite-plugin-pwa` workbox config; Google Fonts requests are **not** in the `runtimeCaching` allowlist today (only `/api/sessions/session/*` is) |

This phase touches exactly one tier (Browser/Client render layer) with zero backend, API, or database changes — the simplest possible tier map, but it means every "requirement" in this phase is a UI diff, not a data-flow change, and verification must be visual/DOM-assertion based rather than API-contract based.

## Standard Stack

No new libraries are required. The phase adds one Google Font family and one shadcn block to an already-initialized component system.

### Core (existing, unchanged)
| Library | Version (installed) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.6 | UI runtime | Already in place |
| Tailwind CSS | 4.3.1 | Utility CSS, CSS-first `@theme` | Already in place; this phase only edits `@theme` values |
| shadcn/ui (`new-york` style, `neutral` base, `cssVariables: true`) | components.json confirms init | Component primitives | Already initialized Phase 4; `components.json` unchanged this phase |
| class-variance-authority | 0.7.1 [VERIFIED: npm registry] | `button.tsx` variant logic | Already in place, confirmed current on npm |
| lucide-react | ^1.21.0 | Icons | Already in place |
| radix-ui | ^1.6.0 | Headless primitives (accordion, alert-dialog, tooltip) | Already in place |

### New this phase
| Item | Source | Purpose | Provenance |
|------|--------|---------|--------------|
| Barlow Condensed (weights 600, 700) | Google Fonts CDN (`fonts.googleapis.com`) | Hero-numeral display face (D-5) | `[ASSUMED]` — Google Fonts hosts Barlow Condensed as a standard open-source family (Google Fonts catalog); not independently re-verified via a fetch in this session, but this is a well-known, long-standing Google Fonts entry, not a novel/unverified package |
| shadcn `card` block | shadcn official registry (`npx shadcn add card`) | Settings screen card-grouped sections (D-12) | `[ASSUMED]` — official shadcn registry, no auth/network fetch performed this session; the existing 7 installed blocks (`accordion`, `alert-dialog`, `badge`, `button`, `separator`, `skeleton`, `tooltip`) all came from the same official registry per `components.json`, so `card` follows an established, low-risk pattern |

### Alternatives Considered
None — CONTEXT.md and UI-SPEC.md already made the font and component-source decisions; this research does not second-guess locked user decisions.

**Installation:**
```bash
# Font: no npm install — edit frontend/index.html <link> tag (see Code Examples)

# Card block: adds a component file, not a new npm dependency (shadcn CLI
# copies component source; Card has no additional Radix primitive dependency
# beyond what's already installed)
cd frontend && npx shadcn add card
```

**Version verification:** No new npm packages are introduced by this phase — `class-variance-authority@0.7.1` was spot-checked via `npm view class-variance-authority version` and matches the already-pinned `package.json` range. No other package.json changes are anticipated.

## Package Legitimacy Audit

**Not applicable this phase.** No new npm/pip/cargo packages are being installed. The two additions (a Google Fonts CDN link, and a shadcn CLI-generated local component file) are not registry package installs and do not appear in `package.json`. If a future planner discovers the `card` shadcn add pulls in an undeclared Radix sub-package, run `npm view <pkg> version` at that time — none is expected because `radix-ui@1.6.0` (the unified package) already covers all primitives currently used, and shadcn's Card is composed from plain `div`s with no additional Radix dependency in the current shadcn template generation.

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Current Codebase Inventory (primary research payload)

This section is the actual deliverable requested for this phase — exact current state of every file named in the phase's research scope.

### `DuringSessionScreen.tsx` (frontend/src/screens/DuringSessionScreen.tsx, 736 lines)

Structure: a single file containing both the presentational `SessionRunner` component (lines 167-637) and the data-loading wrapper `DuringSessionScreen` (lines 643-735). There is no separate "screen" vs "runner" file split — the whole render tree, including all the persistence-critical hooks, lives in one component function.

**Local zone map (to be deleted, migrated to `lib/zones.ts`):** `ZONE_META` object, lines 29-35. Also defines local `ZoneType` (line 21), `powerTarget()` (lines 37-45), `formatTimer()` (lines 47-52), `formatClock()` (lines 54-63), `validZone()` (lines 65-68) — these formatting helpers are *not* zone-map duplication and can stay local (they're timer-formatting utilities, not zone metadata).

**Persistence-critical state/hooks — MUST NOT be touched by the render-layer rebuild (D-2):**
- `restoredRef` (line 190) + `computeRestoredState()` (module-level function, lines 145-161) — reads `loadMatchingSession(sessionId)` on first render only.
- `currentIndex`, `completedDurationSecs`, `stepStartEpoch` state (lines 198-200) and `sessionStartTimestampRef` (line 203).
- `useSessionTimer(stepDuration, stepStartEpoch)` call (line 208) — the wall-clock timer hook itself (`frontend/src/hooks/useSessionTimer.ts`), untouched either way since it's a separate file.
- `togglePause`/`isPaused`/`frozenSecs`/`pauseStartRef` (lines 218-233) — pause logic.
- `buildPayload` (lines 243-251), `goNext` (lines 253-270) — every `saveSession(...)` call site.
- Three `useEffect` persistence hooks: mount-save (272-276), 1s-interval save (279-283), `visibilitychange`/`pagehide` save (287-295).
- Live-resume fast-forward `useEffect` (lines 305-322) and the module-level exported `fastForwardSteps()` function (lines 125-143, exported for direct unit testing).
- `finishSession` callback (lines 181-188) which calls `clearSession()` + `markSessionDone()`.

All of the above is logic, not JSX — a render-layer-only rebuild can restyle everything from line 389 (`return (<div className="ds-bg" ...)`) onward without touching any of the above, as long as the same state variables (`displaySecs`, `zoneColor`, `zoneLabel`, `target`, `currentStep`, `nextStep`, `isPaused`, `progressPct`, `overallElapsed`/`overallRemaining`, `isDone`) are read from, not recomputed differently.

**Exact JSX regions the D-1..D-4 cockpit rebuild will replace:**
- Background wash: line 397 (`backgroundColor: color-mix(in srgb, ${zoneColor} 7%, var(--color-surface))`) → becomes `var(--color-cockpit-bg)`.
- Zone strip: line 412 (unchanged mechanism per UI-SPEC).
- Whole-session progress bar block: lines 415-454 (keep per UI-SPEC — "keep the top progress bar for overall elapsed/remaining, add the rail as a new bottom element").
- Zone badge: lines 475-492 (recolor for dark, no bg tint).
- **Timer + power-target hero block: lines 505-549** — this is the exact region where hero hierarchy inverts (currently `formatTimer(displaySecs)` at 96px is the visual hero at lines 507-519; the zone-color power-target lozenge at 30px is secondary at lines 523-541). D-2 requires watts to become the ~120-160px hero and the timer to demote to ~48-72px secondary — this is a swap of visual scale/order, not new data.
- No-FTP fallback: **does not exist yet.** `powerTarget()` (lines 37-45) already handles `ftp == null` by returning a percentage string (e.g. `"56–75% FTP"`) instead of watts — but this still renders inside the *existing* zone-lozenge treatment, not as the hero-scale effort-word+RPE pattern D-4 specifies. This is genuinely new JSX, not a restyle of existing JSX. There is no `rpe_target` plumbed into `SessionRunner`'s props today (`SessionStep` interface, lines 23-27, has no RPE field) — sourcing an RPE value for the no-FTP hero display will need to come from the session's `rpe_target` field (already present in `SessionData`/`SessionRow` elsewhere) being threaded into `SessionStep` or read at the `DuringSessionScreen` data-loader level.
- Session profile rail: **does not exist in this file at all.** `WorkoutProfileChart` is imported nowhere in `DuringSessionScreen.tsx` today (confirmed — only `SessionCard.tsx` imports it). D-3 requires importing it (or extracting its bar-rendering geometry) into this screen for the first time.
- Pause/Skip/End buttons: lines 579-632, currently plain `<button>` elements styled inline (not shadcn `<Button>`) — UI-SPEC's Foundation Fixes §3 explicitly exempts this screen from the `<Button>` migration, so these stay custom `<button>`s, only re-themed to `--cockpit-*` tokens.
- Session-complete screen: **separate early-return block, lines 326-371**, not part of the main cockpit JSX. Currently light (`backgroundColor: var(--color-bg-2)`), plain Inter 700 heading/time, and a `var(--color-blue-6)` CTA button (line 356). D-11 changes only the CTA color to `--color-achieve`; the surrounding surface stays light per UI-SPEC (session-complete is not part of the "cockpit" dark-surface scope — CONTEXT/UI-SPEC do not say to darken this screen, only to change the CTA's accent color).

**iOS Safari behavior already implemented in this file — preserve exactly:**
- `useWakeLock()` call, line 647 (hook body lives in `frontend/src/hooks/useWakeLock.ts` — Wake Lock API with `nosleep.js` fallback, unrelated to this file's JSX and untouched regardless).
- `minHeight: '100dvh'` at lines 334, 391, 690, 723 (four separate return branches — loading state, no-steps state, main SessionRunner state, and the outer `DuringSessionScreen` loading guard) — **all four**, not just the main one, must keep `100dvh` (not `100vh`) if any of these branches get restyled during the cockpit rebuild.
- `env(safe-area-inset-top)` / `env(safe-area-inset-bottom)` padding at lines 341-342 (session-complete) and 463-464 (main content column) — both are `max(20px, env(...))` on the main branch, plain `env(...)` on session-complete; preserve both patterns per-branch.

### `WorkoutProfileChart.tsx` (frontend/src/components/session/WorkoutProfileChart.tsx, 144 lines)

Already imports `zoneColor` correctly from `lib/format.ts` (line 1) — **not** one of the duplicate zone maps. Renders a `flex` row of proportional-width `div`s (lines 69-114) sized via `flexBasis`/`flexGrow` from `duration_minutes`, plus a separate legend row below (lines 116-140). Currently fixed `height: 34` (line 73) — D-6 wants this taller (56-64px) for the Today hub, and D-3 wants its "geometry" (the proportional-bar-sizing approach) reused for the cockpit's session profile rail, which is a materially different visual treatment (zone-colored throughout, current-block "lit", elapsed "dimmed" via `color-mix`) — not a drop-in reuse of this exact component, but of its layout algorithm (`toSegments()` + proportional `flexBasis`/`flexGrow` pattern, lines 34-51 and 79-113). The component only renders `warmup`/`main_set`/`cooldown` segments (3 max) — the cockpit rail needs one segment per *step* in `DuringSessionScreen`'s `SessionStep[]` array (which can be more granular for free-ride sessions, generated by `generateFreeRideSteps()`), so this is a structural adaptation, not a prop-compatible reuse.

### `StatTile.tsx` (frontend/src/components/ui/StatTile.tsx, 70 lines)

Already generic and prop-driven (`label`, `value`, `unit`, `delta`, `tone`) — no changes needed to the component itself for D-6's "stat tile row" to work; it's already used nowhere in `TodayScreen`/`SessionCard` today (confirmed — no import of `StatTile` in either file), so D-6 is a **new usage**, not a restyle of existing usage. The `.stat-num` class (line 42) is exactly the class the Foundation Fixes font split targets — after the split, this component's value span should move to `.stat-num-hero` per UI-SPEC's Typography table (`Today-hub StatTile value` row), since `StatTile` renders at hero scale (`clamp(34px, 8vw, 52px)`, line 44) today.

### `SessionCard.tsx` (frontend/src/components/session/SessionCard.tsx, 312 lines)

- Objective heading: line 141-146, currently `fontSize: 20`. D-6 wants 28px (Display role).
- `WorkoutProfileChart` already rendered at line 160 (existing integration point — D-6 grows/repositions this, doesn't newly add it, unlike `DuringSessionScreen`).
- No `StatTile` row exists yet — must be newly added under line 160.
- Start button: lines 212-220, `<Button variant="default">` **with an inline `style={{ backgroundColor: 'var(--color-brand)', color: '#fff' }}` override** (line 215) — this is the exact hand-rolled override the Foundation Fixes §3 token mapping makes redundant; UI-SPEC explicitly calls out removing it once tokens are fixed. Button text currently "Start session" (line 219) — D-6 renames to "Start ride".
- Export button: lines 222-230, text "Export to Zwift" (line 229) + `aria-label="Export to Zwift"` (line 225) — rename target per D-6/UI-SPEC copywriting contract to "Export .zwo". **Breaks `today.test.tsx` assertions** (see Common Pitfalls).
- Mark done/Mark missed: currently two always-visible `<Button variant="ghost" size="sm">` in a flex row (lines 249-272), below a "Log without riding" label row (lines 232-248) that is purely a static label today, not a disclosure trigger. D-6 wants these collapsed into a single quiet overflow affordance — this is new interactive behavior (a dropdown/expand-on-tap), not present at all currently; the "Log without riding" text is already there as a static heading with no click handler.
- `AlertDialog` for Mark Missed (lines 278-297) — copy already matches UI-SPEC's Copywriting Contract exactly ("Mark this session as missed?" / "This will trigger a re-plan. Your coach will adjust upcoming sessions.") — no change needed here.

### `TodayScreen.tsx` (frontend/src/screens/TodayScreen.tsx, 284 lines)

**Local zone map (duplicate #2):** `ZONE_VAR` + `isValidZone()`, lines 21-31 — used in **two separate "Coming up" strip render blocks**: the empty-state strip (lines 154-201, zone dot at lines 181-191) and the post-session strip (lines 222-280, zone dot at lines 259-269). Both are near-identical copy-pasted JSX blocks (not just the zone map — the entire strip-item `<button>` markup, lines 164-198 and 242-276, is duplicated verbatim between the two states). D-6's "mini zone-colored duration bar" change must be applied to **both** blocks identically, and the zone-map consolidation removes the local `ZONE_VAR` in favor of `lib/zones.ts`.

No `StatTile` usage yet (confirmed no import). `SessionCard` is rendered at line 216 with only `session`/`pmc` props — no `ftp` prop passed here (default `null` per `SessionCard`'s destructuring, line 64), worth flagging since the cockpit's no-FTP fallback and any Today-hub FTP-dependent stat tile (e.g. an IF estimate) will need the profile's `ftp` value threaded through if not already available via the `session`/`pmc` query results.

### `AgendaScreen.tsx` (frontend/src/screens/AgendaScreen.tsx, 347 lines)

**Local zone map (duplicate #3) coexisting with a correct import** — this is the one CONTEXT.md flags as "inconsistently alongside": line 12 imports `ZONE_META` from `lib/format.ts` (used correctly for the top intensity legend, lines 186-201, via `LEGEND_ZONES`/`ZONE_META[z].color`) **but** lines 14-21 separately define a local `ZONE_VAR` used only for the per-row zone dot (lines 280-288). Two different zone-color sources in the same file for two different UI elements — the legend is on-token, the row dot is not (though both currently resolve to the same hex values, so no visual bug today, just duplication). Consolidation collapses both to a single `lib/zones.ts` import.

Row zone dot: 12px circle, line 281-288. Target: mini zone-colored duration bar (24x4px, 2px radius) per D-9, same treatment as the Today-hub "Coming up" bars.

`WeeklyLoadChart` is not imported/used in this file — that component lives under `progress/` and is presumably rendered from a `ProgressScreen` not in this phase's explicit file list (not read this session; likely unaffected structurally, only the chart's own bar-coloring logic changes per D-9).

### `WeeklyLoadChart.tsx` (frontend/src/components/progress/WeeklyLoadChart.tsx, 133 lines)

Current logic to remove entirely per D-9: `JUMP_FACTOR = 1.5` constant (line 23) and the per-bar jump-detection `<Cell>` coloring (lines 116-125) — `fill={jump ? 'var(--color-zone-tempo)' : 'var(--color-zone-endurance)'}`. Replace with a two-tone scheme keyed on "is this bucket the current ISO week" (compare against `weekStartOf(new Date())`, already imported from the sibling `./week` module at line 13 and already used at line 45 to build the 8-week bucket range — the current-week comparison is a straightforward reuse of an already-imported helper, not a new dependency). `ReferenceLine` average marker (lines 107-114) stays unchanged per UI-SPEC.

### `RideRow.tsx` (frontend/src/components/history/RideRow.tsx, 320 lines)

The HTML `<table>` to remove is at lines 245-314 — a single-row `<table>` (one `<tbody><tr>` with Metric/Planned/Actual/Delta columns) rendered only `{ride.compliance_pct != null && (...)}`. `ComplianceChip` (lines 19-46) already exists and is reused elsewhere in the collapsed-row header (line 108) — D-9's paired-bar replacement reuses this same component, it does not need a new one. Note the table currently hardcodes "Planned: 100%" (line 288) as a literal string, not a computed value — the paired-bar replacement's "Planned" track (100% width per UI-SPEC) is directly consistent with this existing hardcoded assumption, so no new planned-data plumbing is needed.

### `ZoneChip.tsx` (frontend/src/components/session/ZoneChip.tsx, 47 lines)

**Local zone map (duplicate #4):** `ZONE_VAR` (lines 7-13) + `ZONE_LABEL` (lines 15-21), both to be deleted in favor of `lib/zones.ts`. Component itself is otherwise minimal and prop-driven (`zone`, optional `label` override) — no visual changes specified in UI-SPEC beyond the zone-map source change.

**Usage check:** not confirmed used anywhere in the 5 read screens this session (not imported by `SessionCard`, `TodayScreen`, `AgendaScreen`, or `DuringSessionScreen` — those all render their own inline zone badges rather than using this component). The planner should `grep -rn "ZoneChip" frontend/src` before assuming this is a live, widely-used component versus another orphaned Phase-4 artifact like `SessionStepList`.

### `SessionStepList.tsx` (frontend/src/components/session/SessionStepList.tsx, 95 lines)

**Local zone map (duplicate #5):** `ZONE_VAR`, lines 12-18. **Repo-wide grep confirms zero import sites** — this component is not rendered anywhere in the application. It appears to be a Phase-4-era placeholder ("Phase 4 only: no ticking, no auto-advance — Phase 5 wires behavior", per its own header comment) that was superseded by `DuringSessionScreen`'s inline `SessionRunner` implementation and never deleted. **Flagging for the planner:** CONTEXT.md's file list includes this component for zone-map migration, but since it's dead code, the correct action may be deletion rather than migration — confirm with a repo-wide grep before writing a task that "migrates" a component nothing renders.

### `PromptChip` (OnboardingScreen.tsx + ChatScreen.tsx)

Confirmed byte-for-byte identical implementations: `ChatScreen.tsx` lines 85-119 and `OnboardingScreen.tsx` lines 113-147 — same props (`label`, `onClick`, `disabled`), same local `hover` state, same inline style object (padding `8px 14px`, `999px` radius, `var(--color-line)` border, hover swaps `var(--color-surface)` → `var(--color-bg-2)`, text `var(--color-ink-2)` at 14px). Each file's own comment acknowledges the duplication ("Kept local (single call site)" / "Duplicated locally"). Extraction to `frontend/src/components/ui/PromptChip.tsx` is a pure copy-paste-and-delete operation — no visual or behavioral changes needed, exactly as UI-SPEC states.

### Settings screens (`SettingsScreen.tsx`, 179 lines)

- `--color-accent` usage: line 117, `style={{ color: 'var(--color-accent)' }}` on the "Re-send magic link" `<button>` (lines 115-122). Since `--color-accent` is currently **undefined** anywhere in `index.css`, this is an invalid custom-property reference — per CSS spec, the `color` property falls back to its inherited value (from the parent `<section>`, which itself doesn't set `color`, cascading up to `body`'s `color: var(--color-ink)`, line 54 of `index.css`). Net effect: this link currently renders in plain `--color-ink` (near-black), not any accent color, making it visually indistinguishable from body text today — a real (if subtle) UX bug beyond just "undefined token", worth mentioning to the planner as motivation.
- `#dc2626` hardcoded fallback: lines 136-137, `borderColor: 'var(--color-destructive, #dc2626)'` and `color: 'var(--color-destructive, #dc2626)'` on the Sign out button. Since `--color-destructive` is also currently undefined, this **actively renders as the hardcoded `#dc2626`** today (the CSS `var()` fallback syntax works correctly here, unlike the bare `var(--color-accent)` above which has no fallback arg) — so Sign out is already red today, just via a hex fallback rather than a token.
- Structure: three `<section>` blocks (Training lines 65-93, Profile lines 98-124, Account lines 129-143) separated by manual 1px divider `<div>`s (lines 95, 126) — exactly the "bare-div + manual divider" pattern UI-SPEC's D-12 replaces with `<Card>`/`<CardHeader>`/`<CardContent>`.
- Buttons are currently plain `<button>` elements (lines 115-122 magic-link, 133-142 sign-out), not shadcn `<Button>` — both convert to `<Button variant="link">` and `<Button variant="destructive">` respectively per UI-SPEC.

### Login screen (`LoginScreen.tsx`, 258 lines)

`BrandMark` component (lines 15-30) is the source of the "zone-spectrum wordmark" D-10 wants adopted app-wide: a `ZONE_SPECTRUM` gradient constant (lines 10-11, `linear-gradient(90deg, ...)` across all 5 zone tokens) rendered as a `3px` tall, `72px` wide rounded bar beneath a 36px ("Pace") wordmark. This is the only other place in the codebase this gradient pattern exists — `DesktopSidebar.tsx`'s current logotype (see below) has no such treatment. UI-SPEC's E slice reuses `ZONE_SPECTRUM` directly (not redefining it) — this constant should likely move to a shared location (or `DesktopSidebar` imports it from `LoginScreen`, though cross-screen imports of a page-local constant is a minor smell the planner should resolve, e.g. by hoisting `ZONE_SPECTRUM` into `lib/zones.ts` alongside the rest of the zone system).

### shadcn `button.tsx` (frontend/src/components/ui/button.tsx, 65 lines)

Full `cva` variant definition read in full — confirmed token references exactly as UI-SPEC's Foundation Fixes §3 states: `bg-primary`/`text-primary-foreground` (default), `bg-destructive` (destructive), `bg-background`/`hover:bg-accent`/`hover:text-accent-foreground`/`border-input` (outline), `bg-secondary`/`text-secondary-foreground` (secondary), `hover:bg-accent`/`hover:text-accent-foreground` (ghost), `text-primary` (link), plus `focus-visible:border-ring`/`ring-ring/50` on the base class string. Tailwind v4's convention resolves `bg-primary` → `--color-primary`, so the UI-SPEC's proposed `@theme` additions (`--color-primary`, `--color-primary-foreground`, `--color-destructive`, `--color-secondary`, `--color-secondary-foreground`, `--color-accent`, `--color-accent-foreground`, `--color-background`, `--color-foreground`, `--color-border`, `--color-input`, `--color-ring`) are the complete and correct set — no additional token is referenced by `button.tsx` that UI-SPEC's mapping block omits.

### Font loading (`frontend/index.html`, `frontend/src/index.css`)

Confirmed via direct read: `index.html`'s only font `<link>` (single line) loads `Inter:wght@400;500;600;700` — **no Barlow Condensed anywhere in the project** (no `public/` font files, no other CSS `@font-face`, no reference in `package.json`). `index.css`'s `@theme` block defines only `--font-family-sans: "Inter", ui-sans-serif, system-ui, sans-serif` (line 49) — no `--font-family-display` token exists yet. `.stat-num` (lines 81-85) is exactly as CONTEXT describes: `font-weight: 800` requested against a 400/500/600/700 loaded set — genuinely a synthesized/faux-bold today in every browser that doesn't have a locally-installed Inter Black variant, which is a real (if subtle) visual defect already in production.

### Dark-mode / theme infrastructure

**None exists.** Confirmed via full read of `index.css`: no `dark:` Tailwind variant usage anywhere in the theme file, no `prefers-color-scheme` media query, no CSS custom-property remapping block, no `data-theme` attribute pattern. `DARK-01` (full app dark mode) is an unstarted v2 requirement — the `--cockpit-*` tokens UI-SPEC proposes are a **freestanding, scoped set** (5 new custom properties: `--color-cockpit-bg/surface/ink/ink-2/line`), not built on top of any existing dark-mode scaffold, because there isn't one. This is a from-scratch addition, correctly scoped by UI-SPEC to apply only within `DuringSessionScreen`'s JSX tree (via explicit `var(--color-cockpit-*)` references in inline styles, not a `dark:` class toggle or a `[data-theme="dark"]` wrapper — the codebase has no such wrapper mechanism to hook into).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Zone color/label/percent lookup | A 6th local `ZONE_VAR`/`ZONE_META` object | `lib/zones.ts` (new, consolidating the existing canonical shape in `lib/format.ts`) | Already 5 duplicate copies exist; a 6th anywhere is the exact anti-pattern this phase exists to fix |
| Button styling | New inline-styled `<button>` on any light-surface screen | shadcn `<Button variant="...">` once tokens are mapped | Foundation Fixes §3 is a prerequisite specifically so no screen needs a bespoke button again |
| Proportional segment/duration bars | A new bar-chart component from scratch for the cockpit rail or Agenda/Today mini-bars | `WorkoutProfileChart`'s `toSegments()` + `flexBasis`/`flexGrow` proportional-layout pattern (lines 34-51, 79-113) | The geometry (CSS flexbox proportional sizing) is already solved and tested via this component; re-derive the layout math, not the whole component, for the cockpit rail (different segment source: steps, not warmup/main/cooldown) |
| Suggested-reply pill buttons | A 3rd copy of `PromptChip` anywhere new work touches chat-like UI | Shared `frontend/src/components/ui/PromptChip.tsx` (to be extracted this phase) | Two identical copies already exist; do not create a third before the extraction lands |

**Key insight:** every "don't hand-roll" item in this phase is *retiring an existing hand-rolled pattern*, not warning against a hypothetical future one — the anti-patterns are already in production.

## Common Pitfalls

### Pitfall 1: Renaming "Export to Zwift" -> "Export .zwo" silently breaks two test assertions
**What goes wrong:** `frontend/src/tests/today.test.tsx` line 154 asserts `screen.getByRole('button', { name: /export to zwift/i })` and line 159 asserts `screen.getAllByText('Export to Zwift').length > 1` (relying on the button's own text plus the `ZwoExportModal`'s internal `<p>Export to Zwift</p>` heading, line 51 of `ZwoExportModal.tsx`, both containing the same string today).
**Why it happens:** UI-SPEC's copywriting contract only renames the `SessionCard` button's copy (D-6), not the modal panel's internal heading — after the rename, only one "Export..." string variant exists in the DOM at a time, and its accessible name no longer matches `/export to zwift/i`.
**How to avoid:** The plan wave touching `SessionCard.tsx`'s button copy must include updating `today.test.tsx`'s two assertions (button name regex → `/export \.zwo/i`, and either update the modal heading to match or change the multi-match assertion to expect exactly one "Export .zwo" match plus a separate modal-heading check). Decide and document whether `ZwoExportModal`'s internal heading also renames to "Export .zwo" for consistency, or intentionally stays "Export to Zwift" as the modal's own title (UI-SPEC is silent on this — flagged in Open Questions).
**Warning signs:** `npm test` failures in `today.test.tsx` immediately after any `SessionCard` copy change in this phase.

### Pitfall 2: Touching `DuringSessionScreen`'s state to "clean up" while restyling
**What goes wrong:** Because `SessionRunner`'s persistence logic and its JSX live in the same function body (lines 167-637), a well-intentioned refactor pass (e.g., extracting the hero block into a sub-component, or reordering hooks for readability) can accidentally change hook call order, closure captures in `buildPayload`/`goNext`, or the `restoredRef.current === null` first-render guard — any of which would silently break iOS kill/reopen persistence in ways `frontend/src/tests/session.test.tsx`'s fast-forward/restore test suite (lines 182-259, 298-462) may or may not catch depending on exactly what changed.
**Why it happens:** D-2's "render-layer rebuild only" instruction is easy to violate unintentionally when the render layer and the state layer are physically interleaved in one file, rather than cleanly separated.
**How to avoid:** Treat everything above line 389 (state, callbacks, effects) as frozen; only edit JSX from line 389 onward for the visual rebuild. If a sub-component extraction is genuinely desired for maintainability, do it as a visually-identical refactor commit *before* the redesign commit, with the full `session.test.tsx` suite green in between, so any regression is attributable to the redesign commit alone.
**Warning signs:** Any diff touching lines 145-322 (helper functions and hook bodies) in the same commit as a JSX-only redesign task.

### Pitfall 3: Barlow Condensed font-swap causing layout shift on already-fluid `clamp()` hero numerals
**What goes wrong:** Google Fonts CDN fonts load asynchronously; between first paint (system-font fallback) and font-load-complete, a `clamp(96px, 18vw, 160px)` hero numeral can reflow/resize because Barlow Condensed's character widths differ substantially from the Inter/system-ui fallback in the `--font-family-display` stack (`"Barlow Condensed", "Inter", ui-sans-serif, sans-serif`).
**Why it happens:** `&display=swap` (present in the proposed new Google Fonts link) intentionally shows fallback text immediately and swaps once the webfont loads — correct for avoiding invisible text (FOIT), but causes a visible reflow (FOUT) especially on a large hero numeral inside a fluid-width layout.
**How to avoid:** This is a known, accepted tradeoff of `display=swap` and not something to "fix" architecturally (self-hosting + `font-display: optional` would eliminate reflow but changes the loading strategy CONTEXT didn't ask for) — but the planner should note this as an expected, minor visual artifact on first cold load per session, not a bug to chase during implementation. If it's visually jarring in review, `font-display: optional` (skip the swap if the font isn't cached in time) is the standard mitigation, but changes the "will Barlow Condensed usually appear at all on slow connections" tradeoff — flag as an open decision, not a default correctness assumption.
**Warning signs:** Visual flicker/reflow on hero numerals during PWA cold start on throttled connections.

### Pitfall 4: Google Fonts CDN requests are not in the PWA's offline-caching allowlist
**What goes wrong:** `vite-plugin-pwa`'s `workbox.runtimeCaching` config (`vite.config.ts`) only caches `/api/sessions/session/*` requests. Google Fonts stylesheet/font-file requests (`fonts.googleapis.com`/`fonts.gstatic.com`) are not precached or runtime-cached by the service worker — they rely solely on the browser's default HTTP cache. If the "works offline for the during-session view" PWA requirement (`UI-09`) is ever exercised on a fully offline device with an evicted browser cache, Barlow Condensed (a **new** font request this phase adds) could fail to load and silently fall back to the next family in the stack (`"Inter"`, then system sans) — a graceful but user-visible degradation, not a hard failure.
**Why it happens:** This is a pre-existing gap (Inter already has the identical exposure) that this phase's font addition inherits rather than introduces.
**How to avoid:** No action required to stay consistent with current behavior; if the planner wants to close this gap, adding a `googleFontsCache` `runtimeCaching` entry (`CacheFirst` handler on the `fonts.googleapis.com`/`fonts.gstatic.com` origins) is the standard `vite-plugin-pwa` pattern, but this would be scope beyond "visual overhaul" and should be called out as an optional stretch task, not assumed as part of this phase's baseline.
**Warning signs:** Hero numerals rendering in a fallback sans-serif specifically on offline/airplane-mode PWA launches.

### Pitfall 5: `AppLayout.tsx`'s `.h-dvh` / `.md:ml-60` classes are load-bearing for an existing regression test
**What goes wrong:** `frontend/src/tests/AppLayout.test.tsx` asserts the outer wrapping `div` has class `.h-dvh` (not `min-h-screen`/`h-screen`) and the inner content wrapper has both `.md:ml-60` and `.h-dvh`. The D-10 shell restyle (header title 20px→28px, tab bar/sidebar active-state changes) touches `AppLayout.tsx`'s `<header>` and its sibling nav components, but must not touch the two wrapping `<div>`s' class lists (lines 32 and 39 of `AppLayout.tsx`) which exist specifically to fix an iOS Safari height-chain bug from Phase 9.
**Why it happens:** A broad "restyle AppLayout.tsx" task description could tempt a wholesale rewrite of the component, inadvertently dropping or renaming these specific classes.
**How to avoid:** Scope the D-10 shell task explicitly to `<header>` (lines 41-72) and leave lines 29-39 (the two wrapping divs) untouched.
**Warning signs:** `AppLayout.test.tsx` failing after a shell-restyle commit.

## Code Examples

### Foundation Fixes: `@theme` button-token block (verified against actual `button.tsx` class usage)
```css
/* frontend/src/index.css — inside the existing @theme block */
--color-primary:              var(--color-brand);      /* #1F6FE5 */
--color-primary-foreground:   #FFFFFF;
--color-destructive:          var(--color-bad);         /* #C0341D */
--color-secondary:            var(--color-bg-2);        /* #F6F6F7 */
--color-secondary-foreground: var(--color-ink);
--color-accent:               var(--color-blue-0);      /* #E9F3FC */
--color-accent-foreground:    var(--color-brand);
--color-background:           var(--color-surface);     /* #FFFFFF */
--color-foreground:           var(--color-ink);
--color-border:               var(--color-line);
--color-input:                var(--color-line);
--color-ring:                 var(--color-brand);

--font-family-display: "Barlow Condensed", "Inter", ui-sans-serif, sans-serif;
```

### Font `<link>` addition
```html
<!-- frontend/index.html — replaces the existing single Inter link -->
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700&display=swap" rel="stylesheet" />
```

### `lib/zones.ts` extraction target shape (consolidating the canonical shape already in `lib/format.ts`)
```typescript
// frontend/src/lib/zones.ts — new file
export type ZoneKey = 'recovery' | 'endurance' | 'tempo' | 'threshold' | 'vo2'

export interface ZoneMeta {
  color: string
  label: string
  pctLow: number
  pctHigh: number | null // DuringSessionScreen's local ZONE_META allows null for vo2's open-ended upper bound (line 34); lib/format.ts's ZONE_META today types pctHigh as non-null number (line 47, vo2: pctHigh: 120) — reconcile this type difference during consolidation, since DuringSessionScreen's powerTarget() branches on `pctHigh ? ... : ...` (line 39-42) relying on the nullable variant.
}

export const ZONE_META: Record<ZoneKey, ZoneMeta> = { /* ... */ }
export function zoneColor(type: string | null): string { /* ... */ }
export function zoneLabel(type: string | null): string { /* new — not in lib/format.ts today */ }

// frontend/src/lib/format.ts — re-export for existing import sites
export { ZONE_META, zoneColor, type ZoneKey } from './zones'
```

## State of the Art

Not applicable in the traditional sense (no external library API has changed) — the relevant "state of the art" shift here is entirely internal-codebase: consolidating 5 duplicate zone maps into 1, and fixing 2 defects (undefined button tokens, unloaded font weight) that have been latent since earlier phases.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| 5 local zone-color maps across `DuringSessionScreen`/`TodayScreen`/`AgendaScreen`/`ZoneChip`/`SessionStepList` | Single `lib/zones.ts`, re-exported from `lib/format.ts` | This phase (Foundation, slice A) | Any future zone-color change (e.g. a 6th zone, or a hex tweak) becomes a 1-file edit instead of a 5-file hunt |
| shadcn `<Button>` rendering on undefined/browser-default tokens | `<Button>` correctly brand-themed via `@theme` mapping | This phase (Foundation, slice A) | Removes the need for every screen to hand-roll inline style overrides on `<Button>` |
| `.stat-num` at unloaded weight 800 (synthesized bold) | Split into `.stat-num` (Inter 700, loaded) / `.stat-num-hero` (Barlow Condensed 700, loaded) | This phase (Foundation, slice A) | Eliminates browser-synthesized bold, which renders inconsistently across engines |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Google Fonts hosts Barlow Condensed at weights 600/700 and the CDN link syntax shown works | Standard Stack, Code Examples | Low — Barlow Condensed is a well-established Google Fonts family; if the exact weight query params are wrong, the browser gracefully falls back to the next family in the stack, no hard failure |
| A2 | `npx shadcn add card` introduces no new npm dependency beyond what's installed | Standard Stack, Package Legitimacy Audit | Low — if wrong, `npm view <new-pkg> version` should be run at that time and a fresh legitimacy check performed; worst case is a small, official-registry Radix primitive |
| A3 | `--font-family-display` fallback chain (`"Barlow Condensed", "Inter", ui-sans-serif, sans-serif`) is the correct CSS to add, mirroring UI-SPEC's own proposed value verbatim | Code Examples | Low — this is copied directly from `12-UI-SPEC.md` §1, not independently derived |
| A4 | `ZoneChip.tsx` and `SessionStepList.tsx` have zero live usages in the current codebase (both confirmed via `grep -rn` this session, but only against the working tree, not against any not-yet-committed branch work) | Current Codebase Inventory | Medium — if either component is in fact wired up via a dynamic import or a route the grep missed, treating it as "safe to delete" instead of "migrate" would remove live functionality. Planner should re-run the grep immediately before writing the corresponding task. |

**If this table is empty:** N/A — see rows above.

## Open Questions

1. **Does the "Export .zwo" copy rename (D-6) also apply to `ZwoExportModal`'s internal panel heading, or only the `SessionCard` button?**
   - What we know: UI-SPEC's copywriting contract table only lists the `SessionCard` primary/secondary CTA renames; `ZwoExportModal.tsx`'s own `<p>Export to Zwift</p>` heading (line 51) is not mentioned anywhere in CONTEXT.md or UI-SPEC.md.
   - What's unclear: whether leaving the modal heading as "Export to Zwift" while the triggering button says "Export .zwo" is an intentional distinction (button = action, modal = destination format name) or an oversight.
   - Recommendation: the planner should make an explicit micro-decision here (likely: rename both, for consistency, and update `today.test.tsx` accordingly) rather than let it fall through as an implicit side effect.

2. **Is `SessionStepList.tsx` dead code that should be deleted, or is there a planned future call site the planner knows about that this research couldn't see?**
   - What we know: zero import references found via repo-wide grep; the component's own header comment says it was a Phase-4 placeholder pending Phase-5 "wiring" that evidently never happened (DuringSessionScreen's `SessionRunner` was built inline instead).
   - What's unclear: whether any other in-flight or planned phase depends on this file existing.
   - Recommendation: treat as a deletion candidate in the Foundation slice (removes a 6th... actually 5th zone-map duplicate for free) unless the planner finds evidence otherwise.

3. **Should the RPE value needed for the cockpit's no-FTP fallback (D-4) be threaded through `SessionStep`, or read separately at the `DuringSessionScreen` data-loader level?**
   - What we know: `session.rpe_target` already exists on the session data shape (confirmed present on `SessionData`/`SessionRow` interfaces elsewhere in the codebase) but is not currently passed into `SessionStep` (`DuringSessionScreen.tsx` lines 23-27) or read anywhere inside `SessionRunner`.
   - What's unclear: whether RPE should vary per-step (e.g., warmup vs. main-set RPE) or is a single session-level value: current data model only has one `rpe_target` per session, not per-step, suggesting a single value applies for the whole no-FTP fallback display regardless of which step is active.
   - Recommendation: plumb `rpe_target` as a `SessionRunner` prop (alongside the existing `ftp` prop) rather than into `SessionStep`, since it's session-level, not step-level, data.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Google Fonts CDN (`fonts.googleapis.com`/`fonts.gstatic.com`) | Barlow Condensed hero-numeral font (D-5) | Assumed reachable (already relied on for Inter today) | n/a | Font stack falls back to `"Inter"` then system sans-serif if unreachable — no hard failure, graceful degradation already proven in production for Inter |
| shadcn CLI (`npx shadcn`) | Adding the `card` block for Settings redesign (D-12) | Not invoked this session (no network fetch performed); `components.json` confirms the project is already correctly configured for it | n/a | If the CLI is unavailable in the execution environment, the `Card`/`CardHeader`/`CardTitle`/`CardContent` component can be hand-written to match the existing 7 installed blocks' style (they're simple, unstyled-by-default wrapper divs) |

**Missing dependencies with no fallback:** none.
**Missing dependencies with fallback:** both rows above have documented graceful fallbacks; neither blocks execution of this phase.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Vitest 4.1.9 + `@testing-library/react` 16.3.2, jsdom 29.1.1 environment |
| Config file | `frontend/vitest.config.ts` |
| Quick run command | `cd frontend && npx vitest run src/tests/<file>.test.tsx` |
| Full suite command | `cd frontend && npm test -- --run` |

### Phase Requirement -> Test Map
Since this phase has no REQUIREMENTS.md IDs, this maps CONTEXT.md decisions to existing tests that are load-bearing (must stay green) or require updates (will need edits as part of the same task).

| Decision | Behavior | Test File | Automated Command | Status |
|----------|----------|-----------|---------------------|--------|
| D-2 (render-layer-only rebuild) | Timer/persistence logic unaffected by visual rebuild | `frontend/src/tests/session.test.tsx` | `npx vitest run src/tests/session.test.tsx` | ✅ exists, must stay green through slice B |
| D-6 (Start ride / Export .zwo copy) | Button accessible names, Mark missed dialog | `frontend/src/tests/today.test.tsx` | `npx vitest run src/tests/today.test.tsx` | ⚠️ exists but **requires edits** — see Pitfall 1 |
| D-10 (shell restyle) | AppLayout height-chain classes preserved | `frontend/src/tests/AppLayout.test.tsx` | `npx vitest run src/tests/AppLayout.test.tsx` | ✅ exists, must stay green through slice E |
| D-8 (zone map consolidation, button tokens, PromptChip) | No dedicated regression test exists today for zone-color correctness across screens | none | n/a | ❌ Wave 0 gap — see below |
| D-12 (Settings card redesign) | No test file exists for `SettingsScreen.tsx` today | none | n/a | ❌ Wave 0 gap — see below |

### Sampling Rate
- **Per task commit:** run the specific affected test file(s) from the table above.
- **Per wave merge:** `cd frontend && npm test -- --run` (full suite) plus a manual visual check (this phase is visual-heavy; automated DOM assertions cannot catch color/spacing/typography regressions).
- **Phase gate:** full suite green + the iOS Safari manual re-verification already tracked in memory (`project-ios03-timer-persistence.md` — physical-device re-test still outstanding from a prior phase; this phase's cockpit rebuild is an additional reason that re-test is now overdue before shipping slice B).

### Wave 0 Gaps
- [ ] No test exists asserting zone-color consistency across `TodayScreen`/`AgendaScreen`/`DuringSessionScreen` after the `lib/zones.ts` consolidation — consider one small smoke test post-consolidation (e.g. `import { ZONE_META } from '@/lib/zones'` and assert the 5 hex values match the PRD table) since this is exactly the kind of "silent drift" this phase is meant to prevent.
- [ ] `SettingsScreen.tsx` has no existing test file — the D-12 card-redesign task is entirely unverified by automation today. Not necessarily a blocker (this phase can ship without adding one), but the planner should decide whether to add a minimal smoke test given `security_enforcement`/`tdd_mode` are both on in `.planning/config.json`.
- [ ] `frontend/src/tests/today.test.tsx`'s two "Export to Zwift" assertions (Pitfall 1) must be updated in the same commit as the `SessionCard` copy change, not left for a later cleanup pass.

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1` in `.planning/config.json`, so this section is required — but this phase introduces **no new attack surface**: no new user input fields, no new auth flows, no new data persistence, no new API endpoints. All existing auth (Supabase session handling in `SettingsScreen.tsx`/`LoginScreen.tsx`) is read-only in this phase's scope (redesigning presentation of already-authenticated screens).

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V2 Authentication | No | No auth flow changes — `LoginScreen.tsx` form fields/submit logic (lines 45-108) are untouched; only the `BrandMark` visual treatment and its reuse in `DesktopSidebar` are in scope |
| V3 Session Management | No | `SettingsScreen.tsx`'s `supabase.auth.getSession()`/`signOut()` calls (lines 39-47, 19-22) are unchanged — only the surrounding card/button visual treatment changes |
| V4 Access Control | No | No route-guard or permission logic touched |
| V5 Input Validation | No | No new form fields introduced this phase (the redesign changes presentation of existing read-only data displays and existing buttons, not new inputs) |
| V6 Cryptography | No | No credential/token handling touched |
| V11 (client-side rendering / XSS via dangerouslySetInnerHTML equivalents) | No | No new user-controlled string is rendered into `dangerouslySetInnerHTML` or similar — all changes are static JSX/CSS |

### Known Threat Patterns for this stack
None newly applicable this phase — no threat model delta from the redesign. If the planner's plan-checker requires an explicit statement: this phase is presentation-layer-only and does not change any trust boundary, data flow, or input surface documented in prior phases' threat models (Phase 8's Trust Model Integrity work, TRUST-01..09, remains fully unaffected — no LLM/tool-call surface exists in any of the files this phase touches).

## Sources

### Primary (HIGH confidence — direct codebase reads this session)
- `frontend/src/screens/DuringSessionScreen.tsx` (full read, 736 lines)
- `frontend/src/components/session/WorkoutProfileChart.tsx` (full read, 144 lines)
- `frontend/src/components/ui/StatTile.tsx` (full read, 70 lines)
- `frontend/src/components/session/SessionCard.tsx` (full read, 312 lines)
- `frontend/src/screens/TodayScreen.tsx` (full read, 284 lines)
- `frontend/src/screens/AgendaScreen.tsx` (full read, 347 lines)
- `frontend/src/components/progress/WeeklyLoadChart.tsx` (full read, 133 lines)
- `frontend/src/components/history/RideRow.tsx` (full read, 320 lines)
- `frontend/src/components/session/ZoneChip.tsx` (full read, 47 lines)
- `frontend/src/components/session/SessionStepList.tsx` (full read, 95 lines)
- `frontend/src/screens/SettingsScreen.tsx` (full read, 179 lines)
- `frontend/src/screens/LoginScreen.tsx` (full read, 258 lines)
- `frontend/src/components/ui/button.tsx` (full read, 65 lines)
- `frontend/src/lib/format.ts` (full read, 72 lines)
- `frontend/src/index.css` (full read, 103 lines)
- `frontend/index.html` (full read)
- `frontend/package.json` (full read)
- `frontend/components.json` (full read)
- `frontend/vite.config.ts` (full read)
- `frontend/vitest.config.ts` (full read)
- `frontend/src/components/AppLayout.tsx` (full read, 93 lines)
- `frontend/src/components/nav/BottomTabBar.tsx` (full read, 57 lines)
- `frontend/src/components/nav/DesktopSidebar.tsx` (full read, 74 lines)
- `frontend/src/hooks/useWakeLock.ts` (full read, 41 lines)
- `frontend/src/hooks/useSessionTimer.ts` (full read, 26 lines)
- `frontend/src/components/session/ZwoExportModal.tsx` (full read, 90 lines)
- `frontend/src/tests/today.test.tsx` (full read, 193 lines)
- `frontend/src/tests/session.test.tsx` (full read, 532 lines)
- `frontend/src/tests/AppLayout.test.tsx` (full read, 37 lines)
- `frontend/src/screens/ChatScreen.tsx` (partial read, `PromptChip` section)
- `frontend/src/screens/OnboardingScreen.tsx` (partial read, `PromptChip` section)
- Repo-wide `grep -rn "SessionStepList"` and `grep -l "Export to Zwift"` (confirmed usage/non-usage)
- `npm view class-variance-authority version` (confirmed 0.7.1 matches installed range)
- `.planning/phases/12-athletic-redesign/12-CONTEXT.md` (full read — user decisions)
- `.planning/phases/12-athletic-redesign/12-UI-SPEC.md` (full read — design contract)
- `.planning/REQUIREMENTS.md` (full read — no Phase 12 entries)
- `.planning/STATE.md` (full read — project history/context)
- `.planning/config.json` (full read — workflow toggles)
- `./.claude/CLAUDE.md` (project constraints, see below)

### Secondary (MEDIUM confidence)
None — no web/documentation lookups were performed this session; this phase's research is entirely codebase inventory, and Context7/WebSearch tools were not invoked because no new external library API needed verification beyond a package.json version spot-check.

### Tertiary (LOW confidence)
- Barlow Condensed's exact availability/weight support on Google Fonts (A1 in Assumptions Log) — based on general knowledge of the Google Fonts catalog, not verified via a live fetch this session.
- shadcn `card` block's dependency footprint (A2) — based on knowledge of shadcn's typical Card composition, not verified via a live registry fetch this session.

## Project Constraints (from CLAUDE.md)

- **Light mode only for MVP; no pure blacks anywhere** — this phase's dark cockpit is an explicit, user-approved, narrowly-scoped exception (D-1), not a violation; every other screen must remain strictly light-mode per this constraint.
- **No em dashes in any generated content or copy** — applies to every new copy string this phase introduces (button labels, effort words, eyebrow text); UI-SPEC's own Copywriting Contract already self-certifies compliance, but any planner-authored task descriptions or copy micro-decisions (e.g. resolving Open Question 1) must also honor this.
- **React 19 + Vite + Tailwind (frontend), Python FastAPI (backend)** — this phase touches only the frontend half of the stack; no backend/FastAPI files are in scope, confirmed by the phase description and by this research finding zero backend references in any of the 24 files read.
- **LLM never emits physiological numbers directly; tool library is the only authoritative source** — not implicated by this phase (no LLM/agent code touched), but worth noting for completeness since the Security Domain section above states no trust-model surface is affected.
- **PWA: web-first, mobile-responsive; during-session view must work on iOS Safari** — directly load-bearing for this phase's cockpit rebuild (D-1/D-2); see Common Pitfalls 2-4 and the iOS Safari behavior inventory in the DuringSessionScreen section above.

## Metadata

**Confidence breakdown:**
- Current-codebase inventory (component structure, line numbers, duplication locations, test assertions): HIGH — every claim is a direct file read or grep result from this session, not inference.
- Standard stack / new additions (Barlow Condensed, shadcn card): MEDIUM — the decisions themselves are locked by UI-SPEC, but the specific claims about Google Fonts availability and shadcn Card's dependency footprint are `[ASSUMED]` (not independently fetched this session).
- Pitfalls (test breakage, persistence-touch risk, font-swap reflow): HIGH for the two test-breakage pitfalls (directly observed via reading the actual test assertions) — MEDIUM for the font-swap/offline-caching pitfalls (standard, well-known web-platform behavior, not specific to this codebase).

**Research date:** 2026-07-09
**Valid until:** Should be treated as valid for the duration of this phase's execution only (no external API/library surface to go stale) — if the phase spans more than ~2-3 weeks, re-grep for `SessionStepList`/`ZoneChip` usage before finalizing any deletion task, in case other in-flight work has since wired them up.
