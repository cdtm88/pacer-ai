---
status: diagnosed
phase: 04-ui-and-calendar
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md, 04-04-SUMMARY.md, 04-05-SUMMARY.md, 04-06-SUMMARY.md, 04-07-SUMMARY.md, 04-08-SUMMARY.md, 04-09-SUMMARY.md]
started: 2026-06-20T00:00:00Z
updated: 2026-06-21T20:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: Kill any running server. From the repo root, start the backend (e.g. uvicorn api.main:app) and the frontend (cd frontend && npm run dev) from scratch. Backend boots without errors and the health/root path responds. Frontend dev server starts and the app loads in the browser at http://localhost:5173 (or configured port) without console errors. No migration or import failures.
result: pass

### 2. Login Screen
expected: Navigate to /login (or open the app unauthenticated). A centered card shows the "PacerAI" logotype, the descriptor "Your adaptive cycling coach.", an email input field, and a "Send magic link" primary button. No em dashes anywhere on the page.
result: pass

### 3. Magic Link Send
expected: Enter a valid email and click "Send magic link". The card transitions to show "Check your email" as the heading and "We sent a link to {email}. Click it to sign in." as the body. No page reload; just an in-place state change.
result: pass
note: "a bit slow but passed"

### 4. AuthGate Redirect
expected: Open the app at / without being signed in. The app immediately redirects to /login without flashing any authenticated content.
result: pass

### 5. Navigation Shell
expected: After signing in, the bottom tab bar is visible at the bottom of the screen (mobile viewport). It shows four tabs: Today, Agenda, History, Chat. A Settings gear icon appears in the screen header (not a 5th tab). On desktop (768px+ viewport), a 240px sidebar replaces the bottom bar with the same destinations plus Settings at the bottom.
result: issue
reported: "redirects to /login after signing in"
severity: major

### 6. Today Screen
expected: Navigate to / (Today tab). If a session is scheduled for today, a SessionCard appears showing the session objective, zone chip (e.g. "Zone 2"), action buttons ("Mark done", "Mark missed", "Start session", "Export to Zwift"), and a strip of upcoming sessions below. If no session is scheduled, an empty state shows "No session today" copy.
result: pass
note: "Design improvements applied: zone color accent bar added to card top, action row changed to 4 stacked full-width buttons per UI-SPEC"

### 7. TSB Chip Gate
expected: On the Today screen (or wherever the TSB chip would appear), confirm the TSB chip (showing "Fresh", "Balanced", or "Fatigued") is absent when no ride data exists yet (tss_display_ready is false on the backend). It should only appear after enough rides have been uploaded to compute TSB.
result: skipped
reason: Not enough ride data to verify; will revisit later

### 8. Mark Session Missed
expected: On a SessionCard for today, click "Mark missed". An alert dialog appears with the title "Mark this session as missed?" and body "This will trigger a re-plan. Your coach will adjust upcoming sessions." Two buttons: "Yes, mark missed" (destructive CTA) and "Keep it" (cancel). Clicking "Yes, mark missed" closes the dialog and triggers a replan. No em dashes in the dialog copy.
result: issue
reported: "mark missed popup is just broken"
severity: major

### 9. Mark Session Done
expected: On a SessionCard, click "Mark done". The session is marked as completed (session card updates to reflect completed status or disappears from the active list). No confirmation dialog required for mark done.
result: issue
reported: "mark as done does nothing"
severity: major

### 10. Agenda Screen
expected: Navigate to Agenda. Sessions are grouped by week with sticky week headers (Monday-anchored). Each row shows date, session type + truncated objective, a small zone-color dot, duration, and a status icon (green check if completed, red X if missed). Tapping a row expands it to show the full objective, structure, and targets.
result: pass

### 11. Export to Zwift Disabled
expected: On a SessionCard, the "Export to Zwift" button is visually disabled (greyed out). Hovering over it shows a tooltip: "Coming in the next update". Clicking it does nothing.
result: skipped
reason: Spec removed — button is active and functional; no disabled state needed

### 12. History Screen
expected: Navigate to History. A FIT upload zone appears at the top (drag-drop area or click to browse). Below it, a list of uploaded rides shows with compliance chip (green >=90%, amber <90%, "Unmatched" for null), TSS, and duration. If no rides have been uploaded, an empty state shows "No rides yet" with an upload prompt.
result: issue
reported: "Upload failed. uploadRide failed: 422. Try again."
severity: major

### 13. FIT File Upload
expected: Drop a .FIT file onto the upload zone (or click to select one). A success toast appears: "Ride uploaded. History updated." The uploaded ride appears in the ride list below. If an invalid file is dropped, an error toast shows the reason.
result: issue
reported: "same — uploadRide failed: 422"
severity: major

### 14. Chat Screen
expected: Navigate to Chat. A message input textarea and send button are visible. Type a message and send. A typing indicator ("...") appears while the SSE response streams, then the coach's reply appears in a chat bubble. The interface shows coach and user messages styled differently.
result: issue
reported: "no response; also UI needs improving"
severity: major

### 15. Onboarding Flow
expected: Navigate to /onboarding (either as a new user with no profile, or directly). The screen shows an SSE-driven interview: the coach asks questions one at a time, and a progress bar advances as messages arrive. After answering questions, a confirmation summary card appears with a "This looks right" CTA and an "Edit a detail" link.
result: issue
reported: "just in a loop — AI keeps re-asking 'What are your main fitness goals?' regardless of answer"
severity: major

### 16. Settings Screen
expected: Navigate to Settings. The screen shows a Profile section (display name, read-only email, "Re-send magic link" option), a Google Calendar section with a "Connect Google Calendar" button (or "Connected" chip + Disconnect if already connected), and an Account section with a "Sign out" button. No em dashes anywhere.
result: pass

### 17. Calendar Connect
expected: In Settings, click "Connect Google Calendar". The browser redirects to Google's OAuth consent page asking permission for calendar access. (The page may show an "unverified app" warning -- that is expected until Google verification is complete.) After granting access, the user is returned to the app and the Calendar section shows a "Connected" state.
result: blocked
blocked_by: third-party
reason: "Google OAuth app not configured — production verification deferred to a future phase"

### 18. During-Session Screen
expected: Navigate to /session. The screen shows a static step list with a current step displayed prominently (40px bold with a zone-color left border), a "Next: ..." step below, and remaining steps at smaller size. A "00:00" timer is shown with the caption "Timer activates in next phase". An "End session" button at the bottom navigates back to /.
result: pass

## Summary

total: 18
passed: 8
issues: 7
pending: 0
skipped: 2
blocked: 1

## Gaps

- truth: "After signing in via magic link, app shows navigation shell at /"
  status: failed
  reason: "User reported: redirects to /login after signing in"
  severity: major
  test: 5
  root_cause: "useAuth.ts calls getSession() on mount; if it resolves before the PKCE exchange in AuthCallbackScreen completes, it sets isLoading:false, session:null — poisoning the store. When AuthCallbackScreen then calls navigate('/'), AuthGate sees isLoading:false, session:null and immediately redirects to /login."
  artifacts:
    - path: "frontend/src/hooks/useAuth.ts"
      issue: "getSession() resolves with null while on /auth/callback, sets isLoading:false with no session before PKCE exchange completes"
    - path: "frontend/src/screens/AuthCallbackScreen.tsx"
      issue: "calls setAuth then navigate('/') — React Router may render AuthGate with stale null session if Zustand set hasn't flushed"
  missing:
    - "Skip setAuth(isLoading:false) in useAuth when current path is /auth/callback"

- truth: "Mark session missed dialog appears and triggers replan on confirm"
  status: failed
  reason: "User reported: mark missed popup is just broken"
  severity: major
  test: 8
  root_cause: "SessionCard.tsx implements mark-missed confirmation as inline state-toggled p/button elements — no AlertDialog component, so no role=alertdialog in DOM. The shadcn AlertDialog component exists but is never imported in SessionCard."
  artifacts:
    - path: "frontend/src/components/session/SessionCard.tsx"
      issue: "Uses inline conditional render (missedOpen ? ... : ...) instead of <AlertDialog> from @/components/ui/alert-dialog"
  missing:
    - "Replace inline confirmation block with <AlertDialog> bound to missedOpen state"

- truth: "Mark session done marks session as completed"
  status: failed
  reason: "User reported: mark as done does nothing"
  severity: major
  test: 9
  root_cause: "api/routes/sessions.py PATCH handler calls .update().eq().execute() without .select() — supabase-py returns data=[] on all updates without .select(), so if not result.data always raises 404. Frontend catches the 404 and re-enables the button, appearing to do nothing."
  artifacts:
    - path: "api/routes/sessions.py"
      issue: "lines 244-250: .update({'status':'completed'}).eq(...).execute() missing .select(_SESSION_COLUMNS) — returns empty data on success, triggers 404"
  missing:
    - "Add .select(_SESSION_COLUMNS) before .execute() in the update_session handler"

- truth: "FIT file upload succeeds and ride appears in History list"
  status: failed
  reason: "User reported: Upload failed. uploadRide failed: 422. Try again."
  severity: major
  test: 12
  root_cause: "Backend raises 422 when parsed is None OR duration_secs < 600. A short/invalid FIT file fails fitdecode parsing and hits this guard. In Playwright tests, full-uat.spec.ts has a LIFO route registration bug — /rides/upload registered before /rides/ so general handler wins and upload request hits real backend."
  artifacts:
    - path: "api/routes/rides.py"
      issue: "lines 489-496: 422 raised when parse_fit_file() returns None or duration_secs < 600 — real UAT needs a valid FIT file with 10+ min of data"
    - path: "frontend/tests/e2e/full-uat.spec.ts"
      issue: "lines 231-232: /rides/upload registered before /rides/ — LIFO means general handler wins, upload requests hit real backend"
  missing:
    - "Swap route registration order in full-uat.spec.ts (register /rides/ first, /rides/upload last)"
    - "Use test-ride.fit from repo root for real UAT testing"

- truth: "Sending a chat message returns a streamed coach reply"
  status: failed
  reason: "User reported: no response; also UI needs improving"
  severity: major
  test: 14
  root_cause: "Two bugs: (1) createConversation() backend returns {conversation_id:...} but frontend reads conversation?.id — always undefined, so handleSend bails immediately before any SSE request. (2) sseUrl() always appends ?token=... even when path already has query params, producing malformed URL with two ? chars."
  artifacts:
    - path: "frontend/src/lib/api.ts"
      issue: "createConversation() types response as Conversation (field: id) but backend returns {conversation_id}; id is always undefined"
    - path: "frontend/src/lib/api.ts"
      issue: "sseUrl() line 35: always appends ?token= even when path has existing query string — should use & when ? already present"
    - path: "frontend/src/screens/ChatScreen.tsx"
      issue: "line 110: guard `if (!conversation?.id ...)` bails before SSE due to shape mismatch"
  missing:
    - "Map conversation_id to id in createConversation() response: return {id: data.conversation_id, ...}"
    - "Fix sseUrl() to use & instead of ? when path already contains ?"

- truth: "Onboarding interview advances through questions without looping"
  status: failed
  reason: "User reported: just in a loop — AI keeps re-asking 'What are your main fitness goals?' regardless of answer"
  severity: major
  test: 15
  root_cause: "save_messages() is defined but never called in api/routes/onboarding.py — AI responses are never persisted, so every turn loads empty history and the agent repeats its opening question"
  artifacts:
    - path: "api/routes/onboarding.py"
      issue: "save_messages() never called after streaming response completes"
  missing:
    - "Call save_messages() with both user message and AI response after each turn"
