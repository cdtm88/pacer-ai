---
phase: 12
slug: athletic-redesign
status: approved
nyquist_compliant: true
wave_0_complete: true
created: 2026-07-09
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Vitest 4.1.9 + `@testing-library/react` 16.3.2, jsdom 29.1.1 environment |
| **Config file** | `frontend/vitest.config.ts` |
| **Quick run command** | `cd frontend && npx vitest run src/tests/<file>.test.tsx` |
| **Full suite command** | `cd frontend && npm test -- --run` |
| **Estimated runtime** | ~3 seconds (measured: 17 files / 140 tests, 2.3s duration) |

---

## Sampling Rate

- **After every task commit:** Run the specific affected test file(s) — see Per-Decision Verification Map below.
- **After every plan wave:** Run `cd frontend && npm test -- --run` (full suite, ~3s — cheap enough to run every wave).
- **Before `/gsd-verify-work`:** Full suite must be green, plus a manual visual pass (this phase is visual-heavy; DOM assertions cannot catch color/spacing/typography regressions) and the outstanding iOS Safari physical-device re-test (see `project-ios03-timer-persistence.md`).
- **Max feedback latency:** ~3 seconds (full suite is fast enough that there is no reason to skip it between waves).

---

## Per-Decision Verification Map

This phase has no REQUIREMENTS.md IDs (visual overhaul, no new product capabilities). Verification is mapped against CONTEXT.md's locked decisions (D-1..D-12) instead of REQ-IDs. The planner must carry these decision IDs into each plan's `must_haves` and cite them in `requirements`.

| Decision | Behavior | Test File | Automated Command | Status |
|----------|----------|-----------|---------------------|--------|
| D-2 (render-layer-only cockpit rebuild) | Timer/persistence logic unaffected by visual rebuild | `frontend/src/tests/session.test.tsx` | `npx vitest run src/tests/session.test.tsx` | ✅ exists, must stay green through slice B |
| D-6 (Start ride / Export .zwo copy) | Button accessible names, Mark missed dialog | `frontend/src/tests/today.test.tsx` | `npx vitest run src/tests/today.test.tsx` | ⚠️ exists but **requires edits in the same commit** — two "Export to Zwift" assertions break on rename |
| D-10 (shell restyle) | AppLayout height-chain classes preserved | `frontend/src/tests/AppLayout.test.tsx` | `npx vitest run src/tests/AppLayout.test.tsx` | ✅ exists, must stay green through slice E |
| D-7/D-8 (zone map consolidation, button tokens, PromptChip) | No dedicated regression test exists today for zone-color correctness across screens | none | n/a | ❌ Wave 0 gap — see below |
| D-12 (Settings card redesign) | No test file exists for `SettingsScreen.tsx` today | none | n/a | ❌ Wave 0 gap — see below |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Add a small smoke test asserting `ZONE_META` (or equivalent) in the consolidated `lib/zones.ts` exposes the 5 zone hex values matching the PRD table, run once after the D-7/D-8 consolidation task — this is exactly the "silent drift" this phase exists to prevent.
- [ ] Update the two "Export to Zwift" assertions in `frontend/src/tests/today.test.tsx` in the same task/commit as the `SessionCard` copy change (D-6) — do not defer to a later cleanup pass.
- [ ] `SettingsScreen.tsx` has no existing test file. Not a hard blocker for D-12, but given `tdd_mode` and `security_enforcement` are both on, the planner should add a minimal smoke test (renders without throwing, sign-out button present) rather than shipping the redesign fully untested.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Dark cockpit visual correctness (contrast, no pure blacks, watt-hero scale) | D-1, D-2, D-4, D-5 | Automated DOM assertions can't verify color/spacing/typography intent | Load `DuringSessionScreen` in browser at session route, visually confirm near-black ink surface (no `#000`), watt target legible at arm's length, zone chip/timer hierarchy matches wireframe direction A |
| Font rendering (Barlow Condensed weights on hero numerals, Inter elsewhere) | D-5 | Font weight synthesis vs. real weight loading is a rendering concern, not testable via jsdom | Inspect computed `font-family`/`font-weight` in browser devtools on `.stat-num` and hero watt display; confirm no synthetic-bold artifacts |
| iOS Safari session behavior (wake lock, safe-area insets, dvh) after cockpit restyle | D-2 | iOS Safari PWA behavior is not accurately reproducible in jsdom or Simulator | Physical iOS device re-test per `project-ios03-timer-persistence.md` — already outstanding from a prior phase; this phase's cockpit rebuild raises the stakes on this re-test |
| Whole-app visual consistency pass (component unification, no off-token colors remaining) | D-7, D-8, D-9, D-10 | Visual QA across all touched screens is inherently manual | Walk through Today / Agenda / Progress / Coach / Settings / Login in browser at phase gate, confirm no hand-rolled buttons, no duplicated zone maps, no off-token colors remain |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 3s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-07-09 (plan-checker verification passed; all three Wave 0 gaps addressed inside 12-02, 12-05, 12-08)
