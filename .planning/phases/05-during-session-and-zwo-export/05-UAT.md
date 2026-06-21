---
status: testing
phase: 05-during-session-and-zwo-export
source: [05-VERIFICATION.md]
started: 2026-06-21T00:00:00Z
updated: 2026-06-21T00:00:00Z
---

## Current Test

number: 1
name: ZWO-05 — Real Zwift import test
expected: |
  Export a planned session as .zwo; drag into Zwift workout folder (~/Documents/Zwift/Workouts/<user-id>/);
  confirm workout appears with correct name, correct power targets (FTP fractions as decimals),
  and correct duration. For pre-FTP sessions, confirm FreeRide segments appear with RPE textevent labels.
awaiting: user response

## Tests

### 1. ZWO-05 — Real Zwift import test
expected: Generated .zwo file imports cleanly into Zwift. Power targets display as expected FTP percentages. Duration matches planned session. sportType=bike confirmed.
result: [pending]

### 2. IOS-03 — Physical iOS Safari timer + wake lock
expected: On a physical iPhone in installed-PWA mode (added via Share → Add to Home Screen): screen stays lit for 60+ seconds, timer resyncs correctly after backgrounding (switch to another app for 30s, return, verify elapsed is correct), auto-advance fires at segment end, Skip button works, Session complete overlay appears. Record iOS version tested.
result: [pending]

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps
