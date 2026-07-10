---
status: complete
phase: 05-during-session-and-zwo-export
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md, 05-03-SUMMARY.md, 05-04-SUMMARY.md, 05-05-SUMMARY.md, e2e-test-report.md]
started: 2026-06-21T00:00:00Z
updated: 2026-06-21T02:00:00Z
---

## Current Test

[testing complete — 6/6 passed]

## Tests

### 1. Zone accent bar on session cards
expected: Open Today screen. A session card with a known training type (e.g. "endurance", "tempo", "threshold") shows a 4px colored bar across the very top edge of the card — before the date line. Colors: recovery=green (#2B8A5B), endurance=blue (#228BE6), tempo=orange (#F0A030), threshold=orange-red (#E8590C), vo2=red (#C92A2A). A rest-day card with no type shows no bar.
result: pass

### 2. Today screen: only planned sessions appear
expected: If you have completed or missed a session earlier today, the Today screen should show "No session today" (or the next day's session if the schedule has one) — NOT the already-completed/missed session card. Mark a session done or missed, then re-open Today. The same card should not reappear.
result: pass
note: "Fix applied — backend now returns 404 (not {}) when no planned session; frontend already maps 404 to null"

### 3. Mark missed: no 500 on adaptation failure
expected: Mark a session as missed. The action completes successfully (session disappears from Today / is marked missed in Agenda). No error toast or 500 from the backend — even if signal detection internally fails. The missed status is recorded.
result: pass
note: "Overlay bug (AlertDialog z-index issue on iOS) fixed — replaced with inline confirmation state in action row"

### 4. ZWO-05 — Real Zwift import
expected: Navigate to a structured session with an FTP, tap "Export to Zwift" then "Download .zwo". Open the file and confirm well-formed XML with <sportType>bike</sportType>, SteadyState segments with Power values as decimals 0.0-2.0, no Cadence attribute. Import into the real Zwift app — it imports without error and the workout preview shows correct segment count and intensities.
result: pass
note: "Fixes: media_type→octet-stream, explicit filename from Content-Disposition, iOS blob→new tab for Share sheet"

### 5. IOS-03 — Physical iOS Safari timer + wake lock
expected: On a physical iPhone in installed-PWA mode (added via Share → Add to Home Screen): screen stays lit for 60+ seconds, timer resyncs correctly after backgrounding (switch to another app for 30s, return, verify elapsed is correct), after app is killed and relaunched timer resumes from correct elapsed position, 3-second countdown auto-advance fires at segment end, Skip button advances immediately, Session complete overlay appears.
result: pass
note: "Verified after fix(05): persist sessionStartTimestamp and freeRideDurationMins across iOS PWA kill"

### 6. Session complete — Today view clears
expected: After completing a session via the in-session flow (reaching the end, tapping "Back to today" or equivalent), the Today screen should no longer show that session card. The session should be marked complete in the backend and the Today view should reflect this (either showing "No session today" or the next scheduled session).
result: pass
note: "Fix: added finishSession callback in DuringSessionScreen — calls markSessionDone(sessionId) then invalidates RQ cache before navigating"

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
