---
status: testing
phase: 09-frontend-resilience
source: [09-VERIFICATION.md]
started: 2026-07-07T22:15:00Z
updated: 2026-07-07T22:15:00Z
---

## Current Test

number: 1
name: iOS ZWO export downloads without popup-block
expected: |
  On a physical iOS device (Safari), export a session to Zwift (.zwo). The file
  downloads/opens without a "popup blocked" prompt. Code fix: `exportSessionZwo`
  opens `window.open('', '_blank')` synchronously as the first statement (before
  any await), then navigates it once the blob resolves.
awaiting: user response

## Tests

### 1. iOS ZWO export downloads without popup-block
expected: Export flow completes on a real iOS Safari session with no blocked-popup prompt.
result: [pending]

### 2. AppLayout scroll/pin behaves correctly on iOS
expected: |
  On a physical iOS device (Safari) or mobile viewport, open Chat. The input
  stays pinned to the bottom of the viewport (not pushed off-screen by the
  dynamic toolbar), and auto-scroll follows new messages. Code fix: AppLayout.tsx
  uses h-dvh instead of min-h-screen on both wrapping divs.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
