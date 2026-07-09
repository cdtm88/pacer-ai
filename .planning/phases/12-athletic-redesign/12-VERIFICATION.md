---
phase: 12-athletic-redesign
verified: 2026-07-09T19:12:38Z
status: human_needed
score: 12/12 must-haves verified
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Load DuringSessionScreen (active session route) in a real browser and visually confirm the cockpit surface, watt-hero scale, and zone-chip/timer hierarchy"
    expected: "Near-black ink surface (no pure black), watt target legible at arm's length (clamp 96-160px), timer visibly demoted/secondary, no-FTP effort-word+RPE fallback matches wireframe direction A"
    why_human: "Automated DOM/grep checks confirm token values and JSX structure but cannot judge perceived scale, glanceability, or arm's-length legibility"
  - test: "Inspect computed font-family/font-weight in browser devtools on .stat-num, .stat-num-hero, and the cockpit hero watt/timer elements"
    expected: "Barlow Condensed 600/700 renders as a real loaded weight (no synthetic-bold artifacts); Inter renders at 400/700 on inline stat-num elements"
    why_human: "Font weight synthesis vs. real weight loading is a rendering concern not observable via jsdom/grep"
  - test: "Physical iOS Safari device re-test of the rebuilt cockpit: wake lock, safe-area insets, 100dvh, and kill/reopen session persistence"
    expected: "No regression versus pre-phase-12 behavior; timer/session state survives backgrounding and app kill exactly as before the render-layer rebuild"
    why_human: "iOS Safari PWA behavior (wake lock, dvh, background suspension) is not reproducible in jsdom or the iOS Simulator; this is a known outstanding re-test already tracked in project memory (IOS-03) and raised in stakes by this phase's DuringSessionScreen rebuild"
  - test: "Walk through Today / Agenda / Progress / Analysis / Coach / Settings / Login in a browser at phase gate"
    expected: "No hand-rolled buttons remain outside the DuringSessionScreen exception, no duplicated zone maps, no off-token colors, consistent athletic visual language across all screens"
    why_human: "Whole-app visual consistency is inherently a perceptual/manual QA pass, not a grep-checkable property"
---

# Phase 12: Athletic Redesign Verification Report

**Phase Goal:** The app feels like a sports product (Zwift/Strava register), not a SaaS dashboard: the during-ride view becomes a dark cockpit with the watt target as an arm's-length hero and a session profile rail; hero numerals get a display treatment; Today becomes the hub with stat tiles (duration/est TSS/IF) and one fat Start CTA; zone colors carry intensity everywhere; all buttons/tokens/zone maps unify into one component system.

**Verified:** 2026-07-09T19:12:38Z
**Status:** human_needed
**Re-verification:** No — initial verification

This phase has no REQUIREMENTS.md IDs (confirmed: `grep -i "phase 12" .planning/REQUIREMENTS.md` returns nothing). Verification is mapped against `12-CONTEXT.md`'s 12 locked decisions (D-1..D-12), per phase instructions and `12-VALIDATION.md`'s own Per-Decision Verification Map.

## Goal Achievement

### Observable Truths (mapped to CONTEXT.md D-1..D-12)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | D-1: DuringSessionScreen renders on a near-black cockpit surface, no pure black anywhere (incl. `--cockpit-*` tokens) | VERIFIED | `index.css:67` `--color-cockpit-bg: #14171D` (not `#000`); `DuringSessionScreen.tsx` background switched from zone-tinted light wash to `var(--color-cockpit-bg)`; repo-wide grep for `#000`/`#000000` in `src/`+`index.html` found zero hits in application code (only a default Vite logo SVG asset, unrelated to app UI) |
| 2 | D-2: Watts are the arm's-length hero, timer demoted secondary; timer/persistence logic and iOS behavior unchanged (render-layer-only) | VERIFIED | Watt target `clamp(96px, 18vw, 160px)` Barlow Condensed 700 (`DuringSessionScreen.tsx:519-540`); timer demoted to `clamp(48px, 10vw, 72px)` Barlow Condensed 600, `--color-cockpit-ink-2`; diff of `9c6ac2d..HEAD` confirms lines <389 (all `useState`/`useRef`/`useEffect`/`saveSession`/`fastForwardSteps`/`computeRestoredState`) are byte-for-byte outside the diff hunks — only the JSX render tree (389+) and a new `rpe_target` prop were touched; `session.test.tsx` (persistence/restore/fast-forward suite) passes in the full 149-test run, so the invariant is behaviorally exercised, not just present |
| 3 | D-3: Session profile rail — whole workout as proportional zone-colored bars, current lit, elapsed dimmed | VERIFIED | `DuringSessionScreen.tsx:672-714` new rail block: `flexBasis`/`flexGrow` per step (reused `WorkoutProfileChart` geometry pattern), `isElapsed` → `color-mix(... 35%, cockpit-bg)`, `isCurrent` → border + box-shadow glow, `role="img"` + `aria-label` for accessibility |
| 4 | D-4: No-FTP fallback renders effort-word + RPE at the same hero scale/position as the watt target | VERIFIED | `DuringSessionScreen.tsx:509-556`: `hasFtp` ternary renders `EFFORT_WORD[zone]` + `rpe_target`/10 + `EFFORT_CUE[zone]` at the identical `clamp(96px,18vw,160px)` Barlow Condensed 700 block; `rpe_target` threaded from `session?.rpe_target` through `SessionRunner` props (new API field, hand-fixed into `api.ts`'s `Session` interface per review) |
| 5 | D-5: Barlow Condensed 600/700 loads for hero numerals; Inter stays elsewhere; no synthesized-bold defect | VERIFIED | `index.html:10` loads `Inter:wght@400;500;600;700&family=Barlow+Condensed:wght@600;700`; `index.css` `--font-family-display` token defined; `.stat-num` (Inter 700, corrected from unloaded 800) vs `.stat-num-hero` (Barlow Condensed 700) class split confirmed at `index.css:104,112`; `StatTile.tsx` value span uses `stat-num-hero`, delta span uses `stat-num` |
| 6 | D-6: Today hub — 28px objective, StatTile row (duration/TSS/IF), taller centered profile chart, one fat Start CTA + Export secondary, collapsed Mark-done/missed overflow, mini zone bars on "Coming up" | VERIFIED | `SessionCard.tsx:162` objective at `fontSize: 28`; `StatTile` row for Duration/TSS/IF (`:185-191`); `WorkoutProfileChart` height param defaults 34, Today passes 56-64 (`WorkoutProfileChart.tsx:23,61`); "Start ride"/"Export .zwo" CTAs (`:250,256,260`); `logExpanded` overflow row with `inert` gating when collapsed (post-review fix, `:304-308`); `TodayScreen.tsx` both "Coming up" strips use `zoneColor()` + 24×4px 2px-radius bars (`:174-175, 255-256`) |
| 7 | D-7: Zone color carries intensity everywhere (agenda bars, cockpit accents, profile rail); hex values match PRD exactly | VERIFIED | `lib/zones.ts` hex values (`#2B8A5B/#228BE6/#F0A030/#E8590C/#C92A2A`) match `index.css`'s `--color-zone-*` tokens and `docs/prd.md`'s published palette table verbatim; used across `DuringSessionScreen` (rail, zone chip, progress bar), `TodayScreen`/`AgendaScreen` (mini bars), `SessionCard`/`WorkoutProfileChart` |
| 8 | D-8: Component system unification — single `<Button>`, single `lib/zones.ts` zone map, shared `PromptChip`, off-token colors fixed | VERIFIED | `index.css:53-64` full shadcn button-token block mapped to real palette; `lib/zones.ts` is the sole `ZONE_META` declaration in `src/` (grep confirms zero other `Record<Zone...>` maps); `SessionStepList.tsx` (5th duplicate) deleted (file absent); `PromptChip.tsx` extracted, consumed by both `OnboardingScreen.tsx` and `ChatScreen.tsx`, zero other `function PromptChip` definitions remain; `SettingsScreen.tsx` resend-link → `--color-brand`, sign-out → `--color-bad` (no hardcoded hex) |
| 9 | D-9: Progress/Agenda polish — WeeklyLoadChart neutral history + current-week blue, RideRow paired bars, Agenda mini zone bars | VERIFIED | `WeeklyLoadChart.tsx:121` `isCurrentWeek ? 'var(--color-brand)' : 'var(--color-ink-3)'`, jump-detection amber logic removed; `RideRow.tsx:244-285` paired Planned/Actual bars replacing the old `<table>`, `ComplianceChip` retained, post-review overflow-clip fix applied; `AgendaScreen.tsx` imports `zoneColor` from `@/lib/zones` (local `ZONE_VAR` duplicate removed) |
| 10 | D-10: Shell — 28px display titles with date eyebrow above, 11px/600 filled-pill tab labels, sidebar filled-pill (no 3px stripe), zone-spectrum wordmark as app-wide brand mark | VERIFIED | `AppLayout.tsx:51-60` eyebrow (`todayLabel()`) rendered above the `<h1>` (28px/600); `BottomTabBar.tsx:36-47` filled pill (`borderRadius:999`, `color-mix(... 12%)`) replacing the old 4px dot, label bumped to 11px/600; `DesktopSidebar.tsx` imports `ZONE_SPECTRUM` from `lib/zones.ts` and uses the same 999px pill; `LoginScreen.tsx` also imports the hoisted `ZONE_SPECTRUM` (no redefinition) |
| 11 | D-11: Session-complete CTA uses the single sanctioned `--color-achieve` orange | VERIFIED | `DuringSessionScreen.tsx:369` `backgroundColor: 'var(--color-achieve)'` (was `--color-blue-6`); `index.css:31` `--color-achieve: #F76707`; grep confirms no other screen references `--color-achieve` |
| 12 | D-12: Settings redesign to card-grouped sections with real Button instances and on-token colors | VERIFIED | `SettingsScreen.tsx` uses `Card`/`CardHeader`/`CardContent` for all three sections (post-review: `CardTitle` reverted to `<h2>` to restore heading semantics per WR-03 fix); `Button variant="destructive"` for sign-out; `SettingsScreen.test.tsx` exists (new smoke test, first coverage for this screen) |

**Score:** 12/12 truths verified (0 present-but-behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/index.html` | Barlow Condensed font `<link>` | VERIFIED | Line 10, combined with Inter in one Google Fonts link |
| `frontend/src/index.css` | button-token block, `--font-family-display`, `--cockpit-*`, `.stat-num`/`.stat-num-hero`, `--color-achieve` | VERIFIED | All present, confirmed by grep at lines 31, 53-71, 104-118 |
| `frontend/src/lib/zones.ts` | Canonical `ZoneKey`/`ZONE_META`/`zoneColor()`/`zoneLabel()`/`ZONE_SPECTRUM` | VERIFIED | Single source of truth; `lib/format.ts` re-exports for legacy import sites |
| `frontend/src/tests/zones.test.ts` | Drift-guard smoke test | VERIFIED | Exists, part of the green 149-test run |
| `frontend/src/components/ui/PromptChip.tsx` | Shared extracted component | VERIFIED | Both consumers migrated, no duplicate definitions remain |
| `frontend/src/components/ui/card.tsx` | shadcn Card primitive | VERIFIED | Used by `SettingsScreen.tsx` |
| `frontend/src/screens/DuringSessionScreen.tsx` | Cockpit render tree | VERIFIED | Confirmed via diff, persistence boundary untouched |
| `frontend/src/components/session/SessionCard.tsx` | Redesigned Today card | VERIFIED | StatTile row, CTAs, overflow row all present |
| `frontend/src/screens/SettingsScreen.tsx` + test | Card-grouped redesign + smoke test | VERIFIED | Both present |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `button.tsx` tokens | `index.css` `@theme` | `--color-primary`/`--color-destructive`/etc. | WIRED | Block present, mapped to real palette, no undefined tokens |
| `StatTile.tsx` value span | `.stat-num-hero` | className | WIRED | Confirmed at `StatTile.tsx:42` |
| `SessionCard`/`AgendaScreen`/`TodayScreen`/`DuringSessionScreen`/`ZoneChip` | `lib/zones.ts` | import | WIRED | All five confirmed importing from `@/lib/zones` (directly or via `format.ts` re-export); zero orphaned local zone maps remain |
| `OnboardingScreen`/`ChatScreen` | `PromptChip.tsx` | import | WIRED | Both confirmed |
| `DesktopSidebar`/`LoginScreen` | `ZONE_SPECTRUM` in `lib/zones.ts` | import | WIRED | Both confirmed, no redefinition |
| `DuringSessionScreen` data-loader | `SessionRunner` | `rpe_target` prop | WIRED | Threaded from `session?.rpe_target` through to the no-FTP hero fallback |

### Behavioral Spot-Checks / Test Suite

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full frontend test suite green | `cd frontend && npm test -- --run` | 19 files / 149 tests passed, 2.27s | PASS |
| Production build succeeds | `cd frontend && npm run build` | `tsc -b && vite build` completed, dist artifacts generated | PASS |
| Persistence/restore invariant (D-2) exercised | `session.test.tsx` (subset of full run) | Included in the 149 passing tests — resume/discard/fast-forward cases all pass | PASS |
| No pure black in app source | `grep -rniE "#000000\b|#000\b" src/ index.html` | Only match is `src/assets/vite.svg` (default Vite logo asset, not app UI) | PASS |
| No em-dash in user-facing string literals | `grep` for `—` inside quoted string literals in `src/screens`,`src/components` | Zero matches (all `—` occurrences are in code comments, which the CLAUDE.md "no em dashes in copy" rule does not govern) | PASS |
| Zone hex values match PRD | `grep` `index.css` vs `docs/prd.md` | `#2B8A5B`/`#228BE6`/`#F0A030`/`#E8590C`/`#C92A2A` identical in both | PASS |
| WCAG contrast of each zone color vs `--color-cockpit-bg` (#14171D) | Manual luminance calc | recovery 4.18:1, endurance 5.05:1, tempo 8.35:1, threshold 5.01:1, vo2 3.29:1 — all ≥ the UI-SPEC's 3.0:1 large-text threshold | PASS |

### Code Review Findings (12-REVIEW.md) Cross-Check

| Finding | Status | Evidence |
|---------|--------|----------|
| WR-01 (RideRow compliance bar overflow) | FIXED | Commit `6a8f928`: outer track now `overflow: hidden`, fill capped at 100% |
| WR-02 (SessionCard keyboard-focusable hidden actions) | FIXED | `inert={!logExpanded ? true : undefined}` added |
| WR-03 (Settings lost heading semantics) | FIXED | `CardTitle` reverted to `<h2>` for all three sections |
| WR-04 (em dash in ZwoExportModal copy) | FIXED | Copy changed to "FTP: not yet estimated. Free-ride format applies."; dependent test updated |
| WR-05 (em dash placeholder glyphs in SessionCard) | FIXED | `'—'` → `'--'` for Duration/TSS/IF empty states |
| WR-06 (Session API type incompleteness) | DEFERRED (accepted, per phase instructions) | Documented as a follow-up in `12-REVIEW.md`; not a phase-12-introduced regression, architectural in nature |
| IN-01/IN-02/IN-03 | DEFERRED (accepted, per phase instructions) | Pre-existing or intentional-behavior-change items, explicitly non-blocking per review |

### Requirements Coverage

Not applicable — this phase carries no REQUIREMENTS.md IDs. Confirmed via `grep -i "phase 12" .planning/REQUIREMENTS.md` (zero matches) and phase directive stating requirements are `TBD` by design, verified instead against `12-CONTEXT.md`'s D-1..D-12 (table above).

### Anti-Patterns Found

None blocking. No `TBD`/`FIXME`/`XXX` markers found in files modified by this phase. `TODO`/`HACK`/`PLACEHOLDER` scan against the phase's touched files returned no hits. The six real defects found by code review (WR-01 through WR-05) were fixed in commit `6a8f928` prior to this verification; WR-06 and the three Info items are explicitly accepted, documented follow-ups per the phase's own review sign-off, not unresolved debt markers.

### Out-of-Scope Confirmation

Per `12-CONTEXT.md`'s "Explicitly out of scope" section, the following correctly do NOT appear anywhere in this phase's changes (confirmed absent from the diff and from all screens reviewed): Strava integration, readiness 0-3 check-in flow / generation-limit states, zone-color-field ride variant, app-wide dark mode, and bottom-nav IA changes (nav tab count/order unchanged by this phase's commits — the existing 5-tab bar, added in phase 11, predates and is untouched by phase 12).

### Human Verification Required

See frontmatter `human_verification` — four items carried forward directly from `12-VALIDATION.md`'s "Manual-Only Verifications" table (dark-cockpit visual correctness, font-rendering inspection, iOS Safari physical-device re-test, whole-app visual consistency walkthrough). These are inherently perceptual/device-dependent checks that automated grep/DOM assertions cannot resolve, and the phase's own validation strategy flags them as required before ship.

### Gaps Summary

No blocking gaps. All 12 locked decisions (D-1..D-12) are implemented and wired in the codebase, not just claimed in SUMMARY.md — each was independently traced to specific file/line evidence above, cross-referenced against the actual git diff (`9c6ac2d..HEAD`) rather than trusting narrative claims. The full test suite (149 tests) and production build both pass. All five real defects found by code review were fixed before this verification ran; the remaining review items are explicitly accepted architectural follow-ups, not phase-12 regressions. The only open items are the four human-verification checks above, which are visual/device-dependent by nature and were already flagged as manual-only in this phase's own validation strategy.

---

_Verified: 2026-07-09T19:12:38Z_
_Verifier: Claude (gsd-verifier)_
