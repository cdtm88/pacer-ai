---
status: testing
phase: 04-ui-and-calendar
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md, 04-06-SUMMARY.md, 04-07-SUMMARY.md, 04-08-SUMMARY.md, 04-09-SUMMARY.md]
started: 2026-06-20T00:00:00Z
updated: 2026-06-20T00:00:00Z
---

## Current Test

number: 2
name: Login Screen
expected: |
  Navigate to /login (or open the app unauthenticated). A centered card shows the "PacerAI" logotype, the descriptor "Your adaptive cycling coach.", an email input field, and a "Send magic link" primary button. No em dashes anywhere on the page.
awaiting: user response

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server. From the repo root, start the backend (e.g. uvicorn api.main:app) and the frontend (cd frontend && npm run dev) from scratch. Backend boots without errors and the health/root path responds. Frontend dev server starts and the app loads in the browser at http://localhost:5173 (or configured port) without console errors. No migration or import failures.
result: pass

### 2. Login Screen
expected: Navigate to /login (or open the app unauthenticated). A centered card shows the "PacerAI" logotype, the descriptor "Your adaptive cycling coach.", an email input field, and a "Send magic link" primary button. No em dashes anywhere on the page.
result: [pending]

### 3. Magic Link Send
expected: Enter a valid email and click "Send magic link". The card transitions to show "Check your email" as the heading and "We sent a link to {email}. Click it to sign in." as the body. No page reload; just an in-place state change.
result: [pending]

### 4. AuthGate Redirect
expected: Open the app at / without being signed in. The app immediately redirects to /login without flashing any authenticated content.
result: [pending]

### 5. Navigation Shell
expected: After signing in, the bottom tab bar is visible at the bottom of the screen (mobile viewport). It shows four tabs: Today, Agenda, History, Chat. A Settings gear icon appears in the screen header (not a 5th tab). On desktop (768px+ viewport), a 240px sidebar replaces the bottom bar with the same destinations plus Settings at the bottom.
result: [pending]

### 6. Today Screen
expected: Navigate to / (Today tab). If a session is scheduled for today, a SessionCard appears showing the session objective, zone chip (e.g. "Zone 2"), action buttons ("Mark done", "Mark missed", "Start session", "Export to Zwift"), and a strip of upcoming sessions below. If no session is scheduled, an empty state shows "No session today" copy.
result: [pending]

### 7. TSB Chip Gate
expected: On the Today screen (or wherever the TSB chip would appear), confirm the TSB chip (showing "Fresh", "Balanced", or "Fatigued") is absent when no ride data exists yet (tss_display_ready is false on the backend). It should only appear after enough rides have been uploaded to compute TSB.
result: [pending]

### 8. Mark Session Missed
expected: On a SessionCard for today, click "Mark missed". An alert dialog appears with the title "Mark this session as missed?" and body "This will trigger a re-plan. Your coach will adjust upcoming sessions." Two buttons: "Yes, mark missed" (destructive CTA) and "Keep it" (cancel). Clicking "Yes, mark missed" closes the dialog and triggers a replan. No em dashes in the dialog copy.
result: [pending]

### 9. Mark Session Done
expected: On a SessionCard, click "Mark done". The session is marked as completed (session card updates to reflect completed status or disappears from the active list). No confirmation dialog required for mark done.
result: [pending]

### 10. Agenda Screen
expected: Navigate to Agenda. Sessions are grouped by week with sticky week headers (Monday-anchored). Each row shows date, session type + truncated objective, a small zone-color dot, duration, and a status icon (green check if completed, red X if missed). Tapping a row expands it to show the full objective, structure, and targets.
result: [pending]

### 11. Export to Zwift Disabled
expected: On a SessionCard, the "Export to Zwift" button is visually disabled (greyed out). Hovering over it shows a tooltip: "Coming in the next update". Clicking it does nothing.
result: [pending]

### 12. History Screen
expected: Navigate to History. A FIT upload zone appears at the top (drag-drop area or click to browse). Below it, a list of uploaded rides shows with compliance chip (green >=90%, amber <90%, "Unmatched" for null), TSS, and duration. If no rides have been uploaded, an empty state shows "No rides yet" with an upload prompt.
result: [pending]

### 13. FIT File Upload
expected: Drop a .FIT file onto the upload zone (or click to select one). A success toast appears: "Ride uploaded. History updated." The uploaded ride appears in the ride list below. If an invalid file is dropped, an error toast shows the reason.
result: [pending]

### 14. Chat Screen
expected: Navigate to Chat. A message input textarea and send button are visible. Type a message and send. A typing indicator ("...") appears while the SSE response streams, then the coach's reply appears in a chat bubble. The interface shows coach and user messages styled differently.
result: [pending]

### 15. Onboarding Flow
expected: Navigate to /onboarding (either as a new user with no profile, or directly). The screen shows an SSE-driven interview: the coach asks questions one at a time, and a progress bar advances as messages arrive. After answering questions, a confirmation summary card appears with a "This looks right" CTA and an "Edit a detail" link.
result: [pending]

### 16. Settings Screen
expected: Navigate to Settings. The screen shows a Profile section (display name, read-only email, "Re-send magic link" option), a Google Calendar section with a "Connect Google Calendar" button (or "Connected" chip + Disconnect if already connected), and an Account section with a "Sign out" button. No em dashes anywhere.
result: [pending]

### 17. Calendar Connect
expected: In Settings, click "Connect Google Calendar". The browser redirects to Google's OAuth consent page asking permission for calendar access. (The page may show an "unverified app" warning -- that is expected until Google verification is complete.) After granting access, the user is returned to the app and the Calendar section shows a "Connected" state.
result: [pending]

### 18. During-Session Screen
expected: Navigate to /session. The screen shows a static step list with a current step displayed prominently (40px bold with a zone-color left border), a "Next: ..." step below, and remaining steps at smaller size. A "00:00" timer is shown with the caption "Timer activates in next phase". An "End session" button at the bottom navigates back to /.
result: [pending]

## Summary

total: 18
passed: 1
issues: 0
pending: 17
skipped: 0
blocked: 0

## Gaps

[none yet]
