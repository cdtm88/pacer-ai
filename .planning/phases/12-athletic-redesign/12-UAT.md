---
status: complete
phase: 12-athletic-redesign
source: [12-VERIFICATION.md]
started: 2026-07-09T19:14:26Z
updated: 2026-07-10T19:01:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Dark cockpit visual correctness
expected: Load DuringSessionScreen (active session route) in a real browser and visually confirm the cockpit surface, watt-hero scale, and zone-chip/timer hierarchy. Near-black ink surface (no pure black), watt target legible at arm's length (clamp 96-160px), timer visibly demoted/secondary, no-FTP effort-word+RPE fallback matches wireframe direction A.
result: pass
source: automated
evidence: |
  Playwright against http://localhost:5173/session (started a 30-min free ride).
  Computed styles: cockpit bg rgb(20,23,29) = #14171D exactly (not pure black).
  Watt hero "0-110W": font-family "Barlow Condensed", weight 700, 96px at 390px
  viewport (clamp(96px,18vw,160px) floor). Timer "02:23": Barlow Condensed 600,
  48px, color #9AA0AC (--color-cockpit-ink-2) (clamp(48px,10vw,72px) floor).
  Zone chip renders as border+text badge, no bg fill, matching spec. Source
  inspection of DuringSessionScreen.tsx confirms session profile rail (D-3)
  present with correct current-block glow/border + elapsed-block dimming logic.
  No-FTP fallback path not exercised (test profile has FTP=200W set) but
  copy/layout logic verified by source read.

### 2. Font rendering inspection
expected: Inspect computed font-family/font-weight in browser devtools on .stat-num, .stat-num-hero, and the cockpit hero watt/timer elements. Barlow Condensed 600/700 renders as a real loaded weight (no synthetic-bold artifacts); Inter renders at 400/700 on inline stat-num elements.
result: pass
source: automated
evidence: |
  document.fonts inspection confirms Barlow Condensed 700 status "loaded" (real
  face, not synthesized). .stat-num-hero elements (Progress StatTiles, cockpit
  watt/timer) computed font-family "Barlow Condensed", weight 700/600 as
  specified. .stat-num inline elements computed Inter weight 700 where used for
  numeric tabular readouts, matching the Foundation Fixes weight-800-to-700 fix.

### 3. iOS Safari physical-device re-test
expected: Physical iOS Safari device re-test of the rebuilt cockpit: wake lock, safe-area insets, 100dvh, and kill/reopen session persistence. No regression versus pre-phase-12 behavior; timer/session state survives backgrounding and app kill exactly as before the render-layer rebuild. (Known outstanding re-test already tracked in project memory as IOS-03; raised in stakes by this phase's DuringSessionScreen rebuild.)
result: pass
source: automated
evidence: |
  Run on iOS 26.5 Simulator (iPhone 17 Pro), NOT a physical device — user
  redirected from physical-device to simulator for this session; simulator is
  known to not perfectly represent Safari PWA/wake-lock behavior per project
  README, so this is a strong but not 100%-equivalent signal. Driven live via
  idb (tap/button) against mobile Safari at http://localhost:5173, signed in
  as the real user (their choice, in-session).

  Started a 30-min free-ride session, confirmed cockpit renders identically to
  desktop Chrome (near-black bg, watt hero, demoted timer, zone chip, profile
  rail all correct at this viewport). Then drove the actual IOS-03 regression
  concern directly:
  1. Backgrounded Safari (HOME button) for 15s, relaunched: block-elapsed timer
     went from 00:38 to 01:17 (39s), matching wall-clock gap exactly. No
     freeze, no reset, no jump.
  2. Force-terminated Safari entirely (simctl terminate, full process kill,
     not just background) and relaunched cold: block-elapsed timer went from
     01:17 to 02:09 (52s across a ~23s kill+relaunch gap plus JS cold-reload
     time), again continuous and correct — session state survived a full app
     kill, not just backgrounding. This is a harder test than plain
     backgrounding and it passed.
  3. Ended the session cleanly via the End session control with no errors.

  No regression versus pre-phase-12 IOS-03 behavior observed. Wake lock itself
  and true hardware safe-area-inset rendering in standalone (Add to Home
  Screen) mode were NOT verified here (simulator + browser-tab mode limits) —
  recommend a physical-device spot-check next time the app is on a real
  device, but this is no longer a phase-12 blocker.

### 4. Whole-app visual consistency walkthrough
expected: Walk through Today / Agenda / Progress / Analysis / Coach / Settings / Login in a browser at phase gate. No hand-rolled buttons remain outside the DuringSessionScreen exception, no duplicated zone maps, no off-token colors, consistent athletic visual language across all screens.
result: issue
source: automated
reported: "Today, Agenda, Progress, Analysis, Coach, and Login screens all match the UI-SPEC precisely (filled-pill nav active states, mini zone-duration bars, Barlow Condensed StatTiles, PromptChip, zone-spectrum sidebar wordmark). But SettingsScreen's new Card-grouped sections (Foundation Fixes/Section E) render broken: computed backgroundColor is transparent (rgba(0,0,0,0)) instead of white, and border-color computes to #1A2230 (--color-ink, via currentColor fallback) instead of the light --color-line border. Root cause: components/ui/card.tsx uses Tailwind classes bg-card/border/text-card-foreground, but index.css never defines --color-card or --color-card-foreground in @theme (Foundation Fixes Section 3 mapped button/accent tokens but not card tokens), and there is no `@layer base { * { @apply border-border } }` rule, so the bare `border` utility falls back to currentColor. Cards on Settings show the page's gray background bleeding through with a near-black border instead of a lifted white surface."
severity: major

## Summary

total: 4
passed: 3
issues: 1
pending: 0
skipped: 0
blocked: 0

## Gaps

- truth: "SettingsScreen card sections render as white lifted surfaces (--color-surface) with light --color-line borders, per the UI-SPEC card-grouped redesign"
  status: failed
  reason: "Automated check: Card component computed backgroundColor is transparent and border-color is --color-ink instead of --color-line"
  severity: major
  test: 4
  root_cause: "frontend/src/index.css @theme block never defines --color-card / --color-card-foreground (components/ui/card.tsx uses bg-card/text-card-foreground Tailwind classes), and lacks a base-layer rule applying --color-border globally, so shadcn's <Card> renders with an unstyled transparent background and a currentColor (near-black) border instead of the intended white surface + light border."
  artifacts:
    - path: "frontend/src/index.css"
      issue: "Missing --color-card / --color-card-foreground theme tokens; no @layer base border-color rule"
    - path: "frontend/src/components/ui/card.tsx"
      issue: "Depends on bg-card/border/text-card-foreground utilities that have no backing CSS variables"
  missing:
    - "Add --color-card: var(--color-surface); and --color-card-foreground: var(--color-ink); to the @theme block in index.css"
    - "Verify border-color resolves to --color-line on Card (either via a base-layer border-border rule or explicit border-[color:var(--color-line)] on the component)"
  debug_session: ""
