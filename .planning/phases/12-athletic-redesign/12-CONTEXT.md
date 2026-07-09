# Phase 12: Athletic Redesign — Context

**Captured:** 2026-07-09, from an interactive design review session (wireframe reference: `ref-wireframes-full.png` at repo root). These are USER DECISIONS; do not re-ask them.

## Phase goal

The finished app should feel like Zwift or Strava: a sports product, not a SaaS dashboard. This phase is a visual overhaul of existing screens only; no new product capabilities.

## Locked decisions

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

## Explicitly out of scope

- Strava integration (PRD out-of-scope; the wireframe's Strava panel is ignored).
- Readiness 0-3 check-in flow, "generate today's session" CTA, and generation-limit states (product features; deferred to a later phase).
- Zone-color-field ride variant (wireframe direction C) — a possible v2 swipe variant, not this phase.
- Dark mode for the rest of the app (Phase 2 per PRD).
- Nav IA changes: keep 4 tabs (Today / Agenda / Progress / Coach) + Settings; do NOT adopt the wireframe's 3-tab layout.

## Delivery order (each ships independently)

A. Foundation: fonts, button/token mapping, shared zone map, `--cockpit-*` tokens.
B. Ride cockpit (biggest win).
C. Today hub.
D. Progress + Agenda.
E. Shell + secondary surfaces (header, tabs, Settings, Login dedupe, Onboarding/Chat migration to shared components).

## Constraints that still bind

- No pure blacks anywhere, including the dark cockpit.
- Contrast rules from PRD: #228BE6 only for large text/fills; small blue text uses blue-7; body copy ink/ink-2.
- No em dashes in any copy.
- iOS Safari is the primary during-session target (wake lock, safe-area insets, dvh: all existing behavior preserved).
- No hand-drawn/sketchy styles; the wireframe's marker aesthetic is a structural reference only, not a visual target.
