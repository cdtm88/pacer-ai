---
status: testing
phase: 12-athletic-redesign
source: [12-VERIFICATION.md]
started: 2026-07-09T19:14:26Z
updated: 2026-07-09T19:14:26Z
---

## Current Test

number: 1
name: Dark cockpit visual correctness
expected: |
  Near-black ink surface (no pure black), watt target legible at arm's length
  (clamp 96-160px), timer visibly demoted/secondary, no-FTP effort-word+RPE
  fallback matches wireframe direction A.
awaiting: user response

## Tests

### 1. Dark cockpit visual correctness
expected: Load DuringSessionScreen (active session route) in a real browser and visually confirm the cockpit surface, watt-hero scale, and zone-chip/timer hierarchy. Near-black ink surface (no pure black), watt target legible at arm's length (clamp 96-160px), timer visibly demoted/secondary, no-FTP effort-word+RPE fallback matches wireframe direction A.
result: [pending]

### 2. Font rendering inspection
expected: Inspect computed font-family/font-weight in browser devtools on .stat-num, .stat-num-hero, and the cockpit hero watt/timer elements. Barlow Condensed 600/700 renders as a real loaded weight (no synthetic-bold artifacts); Inter renders at 400/700 on inline stat-num elements.
result: [pending]

### 3. iOS Safari physical-device re-test
expected: Physical iOS Safari device re-test of the rebuilt cockpit: wake lock, safe-area insets, 100dvh, and kill/reopen session persistence. No regression versus pre-phase-12 behavior; timer/session state survives backgrounding and app kill exactly as before the render-layer rebuild. (Known outstanding re-test already tracked in project memory as IOS-03; raised in stakes by this phase's DuringSessionScreen rebuild.)
result: [pending]

### 4. Whole-app visual consistency walkthrough
expected: Walk through Today / Agenda / Progress / Analysis / Coach / Settings / Login in a browser at phase gate. No hand-rolled buttons remain outside the DuringSessionScreen exception, no duplicated zone maps, no off-token colors, consistent athletic visual language across all screens.
result: [pending]

## Summary

total: 4
passed: 0
issues: 0
pending: 4
skipped: 0
blocked: 0

## Gaps
