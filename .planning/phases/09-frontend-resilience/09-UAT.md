---
status: complete
phase: 09-frontend-resilience
source: [09-VERIFICATION.md]
started: 2026-07-07T22:15:00Z
updated: 2026-07-08T14:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. iOS ZWO export downloads without popup-block
expected: Export flow completes on a real iOS Safari session with no blocked-popup prompt.
result: pass
verified_via: |
  iOS Simulator (iPhone 17, Safari), driven via idb (Meta's iOS UI-automation
  CLI, installed for this test) against a real signed-up test account with a
  generated training plan. Tapped "Export to Zwift" -> "Download .zwo" on a
  scheduled session. Safari opened a new tab immediately (the pre-gesture
  `window.open('', '_blank')`) and showed its native "Do you want to
  download..." confirmation dialog -- at no point did a "Pop-up Blocked"
  banner appear. Confirmed "Download" completed by finding the saved file on
  the simulator's filesystem (Safari's Downloads container) and inspecting
  its contents: a well-formed .zwo XML workout file matching the session
  (name, description, FreeRide segments).

### 2. AppLayout scroll/pin behaves correctly on iOS
expected: |
  On a physical iOS device (Safari) or mobile viewport, open Chat. The input
  stays pinned to the bottom of the viewport (not pushed off-screen by the
  dynamic toolbar), and auto-scroll follows new messages. Code fix: AppLayout.tsx
  uses h-dvh instead of min-h-screen on both wrapping divs.
result: pass
verified_via: |
  iOS Simulator (iPhone 17, Safari) confirmed the chat input renders pinned
  directly above Safari's own toolbar with no overlap. Deeper interaction
  (typing/scroll) was cross-checked in Chrome mobile-viewport emulation since
  the Simulator has no tap/type driver installed:
  - Confirmed AppLayout's root div carries class "h-dvh" and its computed
    height tracks window.innerHeight exactly at two different viewport
    heights (780px and 874px, simulating Safari's toolbar collapsed/expanded)
    — matching min-h-screen's known iOS bug (fixed 100vh, doesn't shrink)
    being genuinely fixed by h-dvh.
  - Sent messages in a live chat session; message-list container scrollTop
    tracked to scrollHeight - clientHeight (atBottom: true) after each new
    message, confirming auto-scroll.

## Summary

total: 2
passed: 2
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps
