---
phase: 04-ui-and-calendar
verified: 2026-06-20T17:15:00Z
status: gaps_found
score: 2/5
behavior_unverified: 1
overrides_applied: 0
gaps:
  - truth: "All six screens (Onboarding, Today/Home, Agenda, History, During-Session, Chat) are implemented and navigable; mobile bottom tab bar and desktop left sidebar both work"
    status: partial
    reason: "Real screen files exist (OnboardingScreen.tsx, HistoryScreen.tsx, ChatScreen.tsx, SettingsScreen.tsx) but router.tsx imports NONE of them. Lines 113-131 in router.tsx define stub replacements that return <div>Text</div>. Only TodayScreen, AgendaScreen, DuringSessionScreen, and LoginScreen are actually wired. UI-01 (Onboarding), UI-04 (History), UI-06 (Chat), and UI-07 (Settings nav destination) are therefore non-functional in the running app."
    artifacts:
      - path: "frontend/src/router.tsx"
        issue: "Lines 114-131: OnboardingScreen, HistoryScreen, ChatScreen, SettingsScreen are inline stubs returning <div>Text</div>; real screen files at frontend/src/screens/ are never imported"
      - path: "frontend/src/screens/OnboardingScreen.tsx"
        issue: "File exists with full implementation but is unreachable — router.tsx defines its own OnboardingScreen stub"
      - path: "frontend/src/screens/HistoryScreen.tsx"
        issue: "File exists with FIT upload, CTL sparkline, ride list but is unreachable"
      - path: "frontend/src/screens/ChatScreen.tsx"
        issue: "File exists with SSE chat implementation but is unreachable"
      - path: "frontend/src/screens/SettingsScreen.tsx"
        issue: "File exists with calendar connect/disconnect but is unreachable"
    missing:
      - "Import OnboardingScreen from './screens/OnboardingScreen' in router.tsx and replace the inline stub"
      - "Import HistoryScreen from './screens/HistoryScreen' in router.tsx and replace the inline stub"
      - "Import ChatScreen from './screens/ChatScreen' in router.tsx and replace the inline stub"
      - "Import SettingsScreen from './screens/SettingsScreen' in router.tsx and replace the inline stub"

  - truth: "The Today screen shows today's session card with Start Session, Export to Zwift, Mark Done, and Mark Missed actions; the TSB form chip appears only after 28+ days of data"
    status: partial
    reason: "SessionCard renders all four buttons correctly. Mark Done calls markSessionDone which calls PATCH /sessions/{id} -- this endpoint does NOT exist in the backend (sessions.py has only GET endpoints: /sessions/today, /sessions/upcoming, /pmc_history/latest, /profiles/me, /pmc_history/). The button silently fails on every click with a thrown error. CR-03 from code review is confirmed."
    artifacts:
      - path: "frontend/src/components/session/SessionCard.tsx"
        issue: "markSessionDone (line 75) calls PATCH /sessions/{id} which does not exist"
      - path: "api/routes/sessions.py"
        issue: "No PATCH or PUT endpoint defined; only GET endpoints present"
      - path: "frontend/src/lib/api.ts"
        issue: "Lines 179-187: markSessionDone sends PATCH /sessions/{sessionId} but backend has no such route"
    missing:
      - "Add PATCH /sessions/{id} endpoint to api/routes/sessions.py that sets status='completed'"

  - truth: "Google Calendar events are created for planned sessions with full detail in the event body; when the plan changes, corresponding events update, move, or delete; Calendar OAuth uses production credentials, not Testing mode"
    status: partial
    reason: "calendar_sync.py and calendar.py are both substantive and wired. CAL-01 initial push wiring uses a separate POST /onboarding/plan-calendar-sync endpoint -- the frontend must call this after onboarding completes, but the OnboardingScreen stub in router.tsx (gap 1) cannot call it. CAL-03 (production credentials, not Testing mode) cannot be verified programmatically and requires human confirmation. Additionally, onboarding_start discards the conversation_id (WR-05): line 261 awaits create_conversation but does not capture the return value, and sse_generator is called without it -- each SSE reply starts a fresh context, so multi-turn interviews lose prior turns."
    artifacts:
      - path: "api/routes/onboarding.py"
        issue: "Line 261: create_conversation return value discarded; sse_generator called without conversation_id; each POST /onboarding/start starts a fresh agent context"
      - path: "frontend/src/screens/OnboardingScreen.tsx"
        issue: "Exists with plan-calendar-sync call logic but is not reachable (see gap 1)"
    missing:
      - "Capture conversation_id from create_conversation and pass it to sse_generator so multi-turn interview state is preserved (WR-05 fix)"
      - "Human must confirm Google Cloud OAuth consent screen is set to Production (not Testing) -- see user_setup block in 04-07-PLAN.md"

  - truth: "Calendar sync failures surface gracefully to the user without disrupting the plan or chat"
    status: partial
    reason: "CAL-04 fire-and-forget isolation is correctly implemented in adaptations.py (BackgroundTasks) and calendar_sync.py (exception swallowing). However, compliance_pct is always null because process_ride_background in rides.py queries 'training_sessions' (line 309) but the actual Supabase table is named 'sessions' -- CR-04 is confirmed. The exception is swallowed (line 322) so the endpoint does not fail, but compliance data is silently lost. This breaks UI-04 compliance chips in HistoryScreen."
    artifacts:
      - path: "api/routes/rides.py"
        issue: "Line 309: supabase.table('training_sessions') -- table does not exist; actual table is 'sessions'. Exception is caught and swallowed at line 322, causing compliance_pct to always be null."
    missing:
      - "Change 'training_sessions' to 'sessions' on line 309 of api/routes/rides.py"

behavior_unverified_items:
  - truth: "Calendar OAuth uses production credentials, not Testing mode (CAL-03)"
    test: "In Google Cloud Console, navigate to APIs & Services -> OAuth consent screen and verify the app status is 'In production' (not 'Testing'). Verify the calendar.events scope is listed."
    expected: "OAuth consent screen shows 'In production'; calendar.events scope is approved; real users outside the test user list can authorize."
    why_human: "No code-level assertion can prove the Google Cloud project's consent-screen publication status. This is a dashboard configuration that must be visually confirmed."

human_verification:
  - test: "Navigate to /onboarding in a fresh browser session after magic-link login"
    expected: "The full conversational interview UI (ChatBubble, ChatInput, progress bar) appears, not a plain '<div>Onboarding</div>'"
    why_human: "router.tsx stub currently prevents the real OnboardingScreen from rendering. This gap must be fixed (gap 1) before this test makes sense."
  - test: "Navigate to /history"
    expected: "FIT upload drop zone appears at top, ride list below (or 'No rides yet' empty state)"
    why_human: "Same stub gap as onboarding -- blocked on gap 1 fix."
  - test: "Navigate to /chat"
    expected: "Coaching chat interface with 'Ask your coach anything' empty state appears"
    why_human: "Same stub gap."
  - test: "Navigate to /settings"
    expected: "Settings page with Profile, Google Calendar (Connect/Disconnect), and Account (Sign out) sections"
    why_human: "Same stub gap."
  - test: "Click 'Mark done' on today's session card"
    expected: "Session status updates to completed; no error thrown; the card refreshes"
    why_human: "PATCH /sessions/{id} endpoint is missing. This test will fail until gap 2 is fixed."
  - test: "Confirm Google Cloud OAuth consent screen is set to Production"
    expected: "Google Cloud Console shows 'In production' for the PacerAI app; calendar.events scope approved"
    why_human: "CAL-03 requirement; cannot be verified from code"
---

# Phase 04: UI and Calendar Verification Report

**Phase Goal:** The app is usable and clean on both phone and desktop; all screens are functional; Google Calendar events are created, updated, and deleted in sync with plan changes

**Verified:** 2026-06-20T17:15:00Z
**Status:** gaps_found
**Re-verification:** No -- initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All six screens are implemented and navigable; mobile bottom tab bar and desktop left sidebar both work | FAILED | router.tsx lines 114-131: OnboardingScreen, HistoryScreen, ChatScreen, SettingsScreen are inline stubs (<div>Text</div>); real files exist at frontend/src/screens/ but are never imported |
| 2 | Today screen shows session card with Start Session, Export to Zwift, Mark Done, Mark Missed; TSB chip gated on 28+ days | FAILED | TSB gate, 3 of 4 buttons work; Mark Done calls PATCH /sessions/{id} which does not exist in backend (sessions.py has no PATCH endpoint) -- CR-03 confirmed |
| 3 | Google Calendar events created/updated/deleted in sync; OAuth uses production credentials (not Testing mode) | PRESENT_BEHAVIOR_UNVERIFIED | calendar.py and calendar_sync.py are substantive and wired correctly; CAL-01/CAL-02/CAL-04 code exists; CAL-03 production-mode status cannot be verified without human checking Google Cloud Console |
| 4 | Calendar sync failures surface gracefully without disrupting plan or chat | FAILED | CAL-04 isolation correctly implemented; however rides.py line 309 queries 'training_sessions' (table does not exist) instead of 'sessions' -- compliance_pct silently always null (CR-04) |
| 5 | App installable as PWA on iOS/Android; offline during-session; iOS install banner; light mode only, no pure blacks, no em dashes | VERIFIED | IOSInstallBanner.tsx gates on iOS UA + ontouchstart + not standalone + not dismissed; three valid PNG icons present; vite-plugin-pwa configured with navigateFallback; no #000000 in index.css; no em dashes in UI copy; 31/31 frontend tests pass |

**Score:** 2/5 truths verified (1 present, behavior-unverified)

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/router.tsx` | Route skeleton for all screens | STUB | Imports only 4 real screens; OnboardingScreen/HistoryScreen/ChatScreen/SettingsScreen are stubs |
| `frontend/src/screens/OnboardingScreen.tsx` | Full onboarding interview | ORPHANED | Exists with real implementation; not imported in router.tsx |
| `frontend/src/screens/HistoryScreen.tsx` | History with FIT upload | ORPHANED | Exists with real implementation; not imported in router.tsx |
| `frontend/src/screens/ChatScreen.tsx` | SSE chat screen | ORPHANED | Exists with real implementation; not imported in router.tsx |
| `frontend/src/screens/SettingsScreen.tsx` | Settings with calendar | ORPHANED | Exists with real implementation; not imported in router.tsx |
| `frontend/src/screens/TodayScreen.tsx` | Today screen | VERIFIED | Imports SessionCard, fetches via TanStack Query |
| `frontend/src/screens/AgendaScreen.tsx` | Agenda grouped by week | VERIFIED | Week grouping, zone dots, accordion expand |
| `frontend/src/screens/DuringSessionScreen.tsx` | Static stepper | VERIFIED | Timer placeholder, SessionStepList, End session button |
| `frontend/src/components/session/SessionCard.tsx` | 4-button action row | PARTIAL | 3/4 actions wired; Mark Done calls nonexistent PATCH endpoint |
| `api/routes/sessions.py` | Session/PMC/profile endpoints | VERIFIED | 4 GET endpoints, JWT-protected, 13 tests pass |
| `api/routes/calendar.py` | OAuth routes | VERIFIED | auth/callback/settings/disconnect; Fernet encryption; CSRF state |
| `api/calendar_sync.py` | push/update/delete helpers | VERIFIED | asyncio.to_thread; exception swallowing; no-op when no tokens |
| `api/routes/adaptations.py` | Background calendar sync | VERIFIED | BackgroundTasks wired for update/delete on replan |
| `api/routes/rides.py` | compliance_pct computation | FAILED | Line 309 queries 'training_sessions' instead of 'sessions'; compliance always null |
| `frontend/src/components/pwa/IOSInstallBanner.tsx` | iOS banner | VERIFIED | ontouchstart gate; localStorage dismiss; 3 tests pass |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `router.tsx` | `OnboardingScreen.tsx` | import | NOT WIRED | Inline stub defined; real file not imported |
| `router.tsx` | `HistoryScreen.tsx` | import | NOT WIRED | Inline stub defined; real file not imported |
| `router.tsx` | `ChatScreen.tsx` | import | NOT WIRED | Inline stub defined; real file not imported |
| `router.tsx` | `SettingsScreen.tsx` | import | NOT WIRED | Inline stub defined; real file not imported |
| `SessionCard.tsx` | `PATCH /sessions/{id}` | markSessionDone | NOT WIRED | Endpoint missing in backend |
| `api/main.py` | `api/routes/calendar.py` | include_router(calendar_router, prefix='/calendar') | WIRED | Confirmed in main.py line 62 |
| `api/routes/adaptations.py` | `api/calendar_sync.py` | BackgroundTasks update_calendar_event | WIRED | Lines 667, 730 |
| `api/routes/onboarding.py` | `api/calendar_sync.py` | push_all_sessions_to_calendar | WIRED | Line 230 (via asyncio.ensure_future, separate endpoint) |
| `frontend/src/lib/api.ts` | `api/routes/sessions.py` | apiFetch('/sessions/today') | WIRED | getSessionToday, getUpcomingSessions, getLatestPmc all defined |
| `CalendarStatus.tsx` | `GET /calendar/auth` | window.location.href redirect | WIRED | Line 30 in CalendarStatus.tsx |
| `api/routes/rides.py` | `sessions` table | supabase.table('sessions') for compliance | NOT WIRED | Line 309 queries 'training_sessions' instead |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|--------------|--------|-------------------|--------|
| `TodayScreen.tsx` | session | GET /sessions/today | Yes -- queries sessions table via Supabase | FLOWING |
| `AgendaScreen.tsx` | sessions | GET /sessions/upcoming | Yes -- queries sessions table | FLOWING |
| `ChatScreen.tsx` | messages | GET /chat/stream SSE | N/A -- file not routed | DISCONNECTED (orphan) |
| `HistoryScreen.tsx` | rides | GET /rides/ | N/A -- file not routed | DISCONNECTED (orphan) |
| `CalendarStatus.tsx` | connected | GET /calendar/settings | Yes -- decrypts Fernet tokens | FLOWING |
| `RideRow.tsx (in HistoryScreen)` | compliance_pct | rides.compliance_pct | No -- always null (training_sessions bug) | STATIC |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Frontend 31 tests pass | `cd frontend && npm test -- --run` | 31/31 PASS | PASS |
| Backend sessions/auth/calendar tests pass | `.venv/bin/pytest tests/api/test_sessions.py tests/api/test_auth.py tests/api/test_calendar.py -x -q` | 24/24 PASS | PASS |
| No pure black in CSS | `grep "#000000" frontend/src/index.css` | No match | PASS |
| router.tsx imports real screens | `grep "import.*screens" frontend/src/router.tsx` | Only 4 screens imported (DuringSession, Login, Today, Agenda) | FAIL |
| PATCH /sessions/{id} exists | `grep -n "PATCH\|patch" api/routes/sessions.py` | No match | FAIL |
| training_sessions in rides.py | `grep -n "training_sessions" api/routes/rides.py` | Line 309: confirmed | FAIL |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| CAL-01 | 04-07 | Sessions pushed to Google Calendar with full detail | PARTIAL | push_all_sessions_to_calendar exists; initial push wired via separate endpoint; onboarding conversation_id discarded (WR-05) |
| CAL-02 | 04-07 | Plan changes update/delete calendar events | VERIFIED | BackgroundTasks wired in adaptations.py lines 667, 730 |
| CAL-03 | 04-07 | Production OAuth credentials; tokens encrypted, never in browser storage | UNVERIFIED | Code: Fernet encryption confirmed; production vs Testing mode status requires human confirmation |
| CAL-04 | 04-07 | Sync failures graceful, non-blocking | VERIFIED | Exception swallowing in calendar_sync.py; BackgroundTasks isolation in adaptations.py |
| UI-01 | 04-06 | Onboarding conversational flow | FAILED | OnboardingScreen.tsx exists but router.tsx does not import it -- serves <div>Onboarding</div> |
| UI-02 | 04-05 | Today screen with 4 actions; TSB chip gated | PARTIAL | 3/4 actions work; Mark Done calls nonexistent PATCH endpoint |
| UI-03 | 04-05 | Agenda grouped by week with zone colors | VERIFIED | AgendaScreen.tsx wired; week grouping with zone dot tokens |
| UI-04 | 04-06 | History with FIT upload and compliance | FAILED | HistoryScreen.tsx exists but not imported in router.tsx; also compliance_pct always null (training_sessions bug) |
| UI-05 | 04-08 | During-Session static stepper | VERIFIED | DuringSessionScreen.tsx wired; SessionStepList renders 3-tier hierarchy; static timer note present |
| UI-06 | 04-06 | Chat with SSE streaming | FAILED | ChatScreen.tsx exists but not imported in router.tsx |
| UI-07 | 04-05 | Mobile bottom tab bar; desktop left sidebar | VERIFIED | BottomTabBar and DesktopSidebar implemented; AppLayout responsive at 768px breakpoint |
| UI-08 | 04-03 | Design system: Inter, blue-6, no pure black, no em dashes | VERIFIED | index.css has all tokens; no #000000; no em dashes in UI copy |
| UI-09 | 04-08 | PWA installable; offline during-session; iOS banner | VERIFIED | vite-plugin-pwa with navigateFallback; IOSInstallBanner gated correctly; 3 PWA icons present |
| UI-10 | 04-03 | Light mode only | VERIFIED | No dark: variant classes; no #000000 |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/router.tsx` | 113-131 | Stub screen components returning `<div>Text</div>` -- real screen files exist but are not imported | BLOCKER | Onboarding, History, Chat, Settings screens are non-functional in the app |
| `api/routes/rides.py` | 309 | `supabase.table("training_sessions")` -- table does not exist (correct name is "sessions") | BLOCKER | compliance_pct silently always null; UI-04 compliance chips broken |
| `api/routes/onboarding.py` | 261 | `create_conversation` return value discarded; sse_generator called without conversation_id | WARNING | Multi-turn onboarding interview loses context on every reply (WR-05) |
| `frontend/src/lib/api.ts` | 181-187 | `markSessionDone` calls PATCH /sessions/{id} which has no backend route | BLOCKER | Mark Done silently fails on every tap |

### Human Verification Required

#### 1. Screen routing fix required first

**Test:** Before running any screen navigation tests, apply the four import fixes to router.tsx (gap 1) and rerun `npm run build`.
**Expected:** Build succeeds; navigating to /onboarding shows the interview UI; /history shows the upload zone; /chat shows the conversation UI; /settings shows the calendar connect panel.
**Why human:** Code change required; verify visually.

#### 2. Google Calendar OAuth -- Production mode (CAL-03)

**Test:** Log in to Google Cloud Console. Navigate to APIs & Services -> OAuth consent screen. Verify the app status is "In production" (not "Testing"). Verify calendar.events scope is approved.
**Expected:** Status shows "In production"; no per-user test-whitelist required for real users to authorize.
**Why human:** Dashboard configuration -- no code-level assertion can see the Google Cloud project's consent-screen publication status.

#### 3. Mark Done action (after gap 2 fix)

**Test:** After adding PATCH /sessions/{id} endpoint, click "Mark done" on today's session card.
**Expected:** Session status updates to completed; card refreshes without error toast.
**Why human:** Requires a live session in the DB and a running backend.

### Gaps Summary

Four gaps block the phase goal:

1. **CRITICAL: Four screen stubs not replaced** (IN-02). `router.tsx` still contains inline stub components for OnboardingScreen, HistoryScreen, ChatScreen, and SettingsScreen. The real implementations at `frontend/src/screens/` are never imported. This means UI-01, UI-04, and UI-06 are completely non-functional. Fix: replace each stub with the corresponding import from `./screens/`.

2. **Mark Done silently broken** (CR-03). `SessionCard` calls `markSessionDone` which sends `PATCH /sessions/{id}` -- a route that does not exist in `api/routes/sessions.py`. Every click throws an error internally. Fix: add a `PATCH /sessions/{session_id}` endpoint to sessions.py that updates `status='completed'`.

3. **compliance_pct always null** (CR-04). `api/routes/rides.py` line 309 queries `training_sessions` instead of `sessions`. The exception is swallowed, so the compliance lookup always silently returns no rows. Fix: change `"training_sessions"` to `"sessions"` on line 309.

4. **CAL-03 human confirmation pending**. Whether the Google Cloud OAuth consent screen is set to Production (not Testing) cannot be verified from code. This was a blocking human-verify task in the plan (Task 0 of 04-07). Must be confirmed before any real user testing.

The navigation shell (AppLayout, BottomTabBar, DesktopSidebar), TodayScreen, AgendaScreen, DuringSessionScreen, PWA infrastructure, backend auth (JWT), backend sessions endpoints, and Google Calendar sync helpers are all substantive and correctly implemented. Gaps 1-3 are all in wiring, not in the underlying implementations.

---

_Verified: 2026-06-20T17:15:00Z_
_Verifier: Claude (gsd-verifier)_
