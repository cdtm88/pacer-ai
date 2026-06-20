---
phase: 04-ui-and-calendar
verified: 2026-06-20T22:15:00Z
status: gaps_found
score: 3/5
behavior_unverified: 0
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 2/5
  gaps_closed:
    - "router.tsx now imports all four real screens (OnboardingScreen, HistoryScreen, ChatScreen, SettingsScreen) — stubs removed"
    - "PATCH /sessions/{session_id} endpoint added to sessions.py with JWT ownership guard"
    - "compliance lookup table fixed from training_sessions to sessions with correct column names"
    - "onboarding.py now captures conversation_id and loads prior turns via load_conversation"
  gaps_remaining:
    - "CAL-03: Railway not deployed; Google OAuth consent screen verification not submitted; production OAuth flow untestable"
    - "4 Vitest unit tests in today.test.tsx fail: assertions expect lowercase TSB labels (fresh/balanced/fatigued) but TsbChip now renders sentence-case (Fresh/Balanced/Fatigued) after 04-10 E2E fix"
  regressions:
    - "today.test.tsx: 4 tests fail due to sentence-case label mismatch introduced by commit 8666c20 (TsbChip.tsx label fix for E2E compatibility)"
gaps:
  - truth: "Google Calendar events are created/updated/deleted in sync; OAuth uses production credentials, not Testing mode"
    status: failed
    reason: "CAL-03 explicitly requires production credentials before real user testing. Railway backend is not deployed (no live callback URL). Google OAuth verification has not been submitted to the Verification Centre — required for calendar.events sensitive scope. No later milestone phase covers these items: Phase 5 owns ZWO/iOS only. The ROADMAP.md success criterion #3 for Phase 4 states this must be TRUE. calendar.py implementation is complete; the gap is infrastructure and Google review, not code."
    artifacts:
      - path: "api/routes/calendar.py"
        issue: "Implementation is complete and correct; blocked on external infrastructure only"
    missing:
      - "Railway deployment (FastAPI + DB) to provide a live OAuth callback URL"
      - "App logo, privacy policy URL, Terms of Service URL (required by Google for verification)"
      - "Submit to Google Verification Centre for calendar.events sensitive scope"
      - "Once verified: run production OAuth flow end-to-end with real Google account"

  - truth: "All six screens are implemented and navigable; mobile bottom tab bar and desktop left sidebar both work"
    status: partial
    reason: "Screen routing is now fully wired (gap 1 closed). However, 4 Vitest unit tests in today.test.tsx now fail because TsbChip.tsx was updated to sentence-case labels (Fresh/Balanced/Fatigued) by commit 8666c20 but the unit tests still assert lowercase (fresh/balanced/fatigued). This is a test-code regression introduced by the E2E compatibility fix. The app renders correctly; the tests are inconsistent with the implementation."
    artifacts:
      - path: "frontend/src/tests/today.test.tsx"
        issue: "Lines 100, 105, 110, 137: getByText('fresh'), getByText('fatigued'), getByText('balanced') -- all fail because TsbChip now renders 'Fresh', 'Fatigued', 'Balanced' (sentence case)"
      - path: "frontend/src/components/session/TsbChip.tsx"
        issue: "STATE_STYLE.label values changed to sentence case in commit 8666c20; unit test assertions not updated to match"
    missing:
      - "Update today.test.tsx assertions to use sentence-case: 'Fresh', 'Balanced', 'Fatigued' (3 label checks + 1 in SessionCard block)"
      - "Update today.test.tsx line 126-128: queryByText assertions for cold-start gate also need sentence-case"

human_verification:
  - test: "Complete the Google OAuth flow with a real Google account on the production deployment"
    expected: "User is redirected to Google, grants calendar.events scope, is redirected back to /settings?calendar=connected, calendar status shows connected"
    why_human: "Requires Railway backend deployed with live BACKEND_BASE_URL; requires Google OAuth verification approved; cannot be simulated by mock tests"
  - test: "After connecting calendar, trigger a plan adaptation and verify Google Calendar events update"
    expected: "Calendar events for moved/removed sessions are updated or deleted; new session events are created"
    why_human: "Requires live Railway backend, real Supabase DB, and Google Calendar API access"
---

# Phase 04: UI and Calendar Verification Report (Re-verification)

**Phase Goal:** The app is usable and clean on both phone and desktop; all screens are functional; Google Calendar events are created, updated, and deleted in sync with plan changes

**Verified:** 2026-06-20T22:15:00Z
**Status:** gaps_found
**Re-verification:** Yes -- after gap closure (plans 04-09, 04-10, 04-11)

## Previous Verification Summary

Previous score: 2/5. Four gaps blocked: screen stubs in router.tsx, missing PATCH endpoint, wrong compliance table name, CAL-03 production OAuth.

Plans 04-09 and 04-10 closed three of the four code gaps. Plan 04-11 documented CAL-03 as deferred (external blockers: Railway not deployed, Google verification required). One code regression was introduced by 04-10 (unit test label mismatch).

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | All six screens (Onboarding, Today, Agenda, History, During-Session, Chat, Settings) are implemented and navigable; mobile bottom tab bar and desktop left sidebar both work | PARTIAL | router.tsx lines 13-16: all four previously-stub screens now imported from ./screens/. 34/34 Playwright E2E tests pass (frontend/test-results/.last-run.json status=passed, timestamped 2026-06-20 21:42). However 4 Vitest unit tests in today.test.tsx fail due to sentence-case label mismatch (TsbChip 'Fresh' vs test assert 'fresh') |
| 2 | Today screen shows session card with Start Session, Export to Zwift, Mark Done, Mark Missed; TSB chip gated on 28+ days | VERIFIED | PATCH /sessions/{session_id} added at line 221 of sessions.py (commit 6064c66); markSessionDone in api.ts calls PATCH /sessions/{sessionId}; SessionCard line 76 calls it. Playwright T09 passes confirming no crash. TSB gate and sentence-case labels verified via E2E T07 |
| 3 | Google Calendar events created/updated/deleted in sync; Calendar OAuth uses production credentials, not Testing mode | FAILED | CAL-01/CAL-02/CAL-04 code is complete and E2E-mocked; CAL-03 requires production deployment and Google review. Railway backend not deployed. Google verification not submitted. Phase 5 ROADMAP does not cover this. No later milestone phase addresses CAL-03 |
| 4 | Calendar sync failures surface gracefully without disrupting plan or chat | VERIFIED | compliance lookup now queries sessions table (rides.py line 300, commit bdae60c); exception swallowed at line 313 (best-effort). calendar_sync.py exception swallowing unchanged. BackgroundTasks isolation in adaptations.py unchanged |
| 5 | App installable as PWA on iOS/Android; offline during-session; iOS install banner; light mode only, no pure blacks, no em dashes | VERIFIED | Unchanged from initial verification: IOSInstallBanner.tsx, vite-plugin-pwa, no #000000 in index.css, no em dashes in UI copy |

**Score:** 3/5 truths verified (0 present, behavior-unverified)

## Gap Closure Verification

| Gap (prior) | Fix | Commit | Code Evidence | Status |
|-------------|-----|--------|---------------|--------|
| router.tsx stub screens | Import from ./screens/ | 1c7ee6b | Lines 13-16: `import { OnboardingScreen } from './screens/OnboardingScreen'` etc.; no inline stubs remain | CLOSED |
| Missing PATCH /sessions/{id} | Add endpoint | 6064c66 | sessions.py line 221: `@router.patch("/sessions/{session_id}")` with JWT guard and user-scoped filter | CLOSED |
| compliance_pct always null | Fix table name | bdae60c | rides.py line 300: `supabase.table("sessions").select("tss_target, type")` | CLOSED |
| Onboarding conversation_id discarded | Capture and load | 8e5715e | onboarding.py lines 243-267: conversation_id captured, load_conversation called, metadata event sent to client | CLOSED |
| CAL-03 production OAuth | Not closeable by code | — | Railway not deployed; Google verification not submitted; no code gap but infrastructure blockers remain | OPEN |

## New Regression: Unit Test Label Mismatch (Introduced by 04-10)

Commit 8666c20 changed `TsbChip.tsx` STATE_STYLE labels to sentence case (`Fresh`, `Balanced`, `Fatigued`) for Playwright E2E compatibility. The Vitest unit tests in `today.test.tsx` were not updated and still assert lowercase.

**Result:** 27/31 Vitest unit tests pass; 4 fail.

Failing assertions:
- `src/tests/today.test.tsx:100` — `getByText('fresh')` (should be `'Fresh'`)
- `src/tests/today.test.tsx:105` — `getByText('fatigued')` (should be `'Fatigued'`)
- `src/tests/today.test.tsx:110` — `getByText('balanced')` (should be `'Balanced'`)
- `src/tests/today.test.tsx:137` — `getByText('fresh')` (should be `'Fresh'`)
- `src/tests/today.test.tsx:126-128` — `queryByText` cold-start assertions also need updating

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `frontend/src/router.tsx` | All screens imported and routed | VERIFIED | Lines 13-16: OnboardingScreen, HistoryScreen, ChatScreen, SettingsScreen all imported; routes at lines 142, 167, 171, 179 |
| `frontend/src/screens/OnboardingScreen.tsx` | Full onboarding interview | VERIFIED | Imported and routed at /onboarding; reachable |
| `frontend/src/screens/HistoryScreen.tsx` | History with FIT upload | VERIFIED | Imported and routed at /history; reachable |
| `frontend/src/screens/ChatScreen.tsx` | SSE chat screen | VERIFIED | Imported and routed at /chat; reachable |
| `frontend/src/screens/SettingsScreen.tsx` | Settings with calendar | VERIFIED | Imported and routed at /settings; reachable |
| `api/routes/sessions.py` | PATCH endpoint added | VERIFIED | Line 221: @router.patch with validate_uuid, dual ownership filter, 404 on miss |
| `api/routes/rides.py` | compliance_pct fix | VERIFIED | Line 300: sessions table, tss_target + type columns |
| `api/routes/onboarding.py` | conversation_id preserved | VERIFIED | Lines 243-267: create_conversation captured, load_conversation called |
| `api/routes/calendar.py` | OAuth routes | VERIFIED | auth-redirect-url, auth, callback, settings, disconnect all present; HMAC state; Fernet encryption |
| `frontend/src/tests/today.test.tsx` | Unit tests pass | FAILED | 4/31 fail — sentence-case label mismatch after TsbChip.tsx update |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `router.tsx` | `OnboardingScreen.tsx` | import | WIRED | Line 13; rendered at /onboarding route (line 142) |
| `router.tsx` | `HistoryScreen.tsx` | import | WIRED | Line 14; rendered at /history route (line 167) |
| `router.tsx` | `ChatScreen.tsx` | import | WIRED | Line 15; rendered at /chat route (line 171) |
| `router.tsx` | `SettingsScreen.tsx` | import | WIRED | Line 16; rendered at /settings route (line 179) |
| `SessionCard.tsx` | `PATCH /sessions/{id}` | markSessionDone | WIRED | api.ts line 189: PATCH /sessions/${sessionId}; backend endpoint confirmed at sessions.py line 221 |
| `api/routes/adaptations.py` | `api/calendar_sync.py` | BackgroundTasks | WIRED | Unchanged from initial; lines 667, 730 |
| `api/main.py` | `api/routes/calendar.py` | include_router | WIRED | Unchanged from initial |
| `api/routes/rides.py` | `sessions` table | supabase.table('sessions') | WIRED | Line 300 fixed; was 'training_sessions' |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| router.tsx imports all 6 real screens | `grep "import.*screens" frontend/src/router.tsx` | 7 lines: DuringSessionScreen, TodayScreen, AgendaScreen, OnboardingScreen, HistoryScreen, ChatScreen, SettingsScreen | PASS |
| PATCH /sessions/{id} exists in backend | `grep -n "router.patch" api/routes/sessions.py` | Line 221: `@router.patch("/sessions/{session_id}")` | PASS |
| compliance table name fixed | `grep -n "sessions\|training_sessions" api/routes/rides.py` | Line 300: `supabase.table("sessions")` — no training_sessions references | PASS |
| conversation_id captured in onboarding | `grep -n "conversation_id" api/routes/onboarding.py` | Lines 243, 251, 265-267: captured, loaded, emitted | PASS |
| Vitest unit tests | `cd frontend && npm test -- --run` | 27/31 pass; 4 fail in today.test.tsx (TSB label case mismatch) | FAIL |
| Playwright E2E 34/34 | last-run artifact | frontend/test-results/.last-run.json: status=passed, failedTests=[] (timestamped 2026-06-20 21:42) | PASS |
| No inline screen stubs in router.tsx | `grep -n "return <div>.*</div>" frontend/src/router.tsx` | No match | PASS |
| No pure black in CSS | `grep "#000000" frontend/src/index.css` | No match | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|---------|
| CAL-01 | 04-07 | Sessions pushed to Google Calendar with full detail | VERIFIED | push_all_sessions_to_calendar wired; conversation_id fix (gap 4 closed) unblocks onboarding flow to reach calendar sync |
| CAL-02 | 04-07 | Plan changes update/delete calendar events | VERIFIED | BackgroundTasks wired in adaptations.py unchanged; E2E mocked tests pass |
| CAL-03 | 04-07 | Production OAuth credentials; tokens encrypted; never in browser storage | FAILED | Code: Fernet encryption confirmed; HMAC state confirmed. Infrastructure: Railway not deployed; Google verification not submitted. REQUIREMENTS.md marks CAL-03 complete but Phase 4 roadmap SC #3 requires production credentials |
| CAL-04 | 04-07 | Sync failures graceful, non-blocking | VERIFIED | Exception swallowing + BackgroundTasks unchanged; compliance_pct now populated correctly |
| UI-01 | 04-06 | Onboarding conversational flow | VERIFIED | OnboardingScreen.tsx imported and routed; Playwright T15 passes |
| UI-02 | 04-05 | Today screen with 4 actions; TSB chip gated | VERIFIED | PATCH endpoint added; all 4 actions wired; Playwright T06, T07, T09 pass |
| UI-03 | 04-05 | Agenda grouped by week with zone colors | VERIFIED | AgendaScreen.tsx wired; Playwright T10 passes |
| UI-04 | 04-06 | History with FIT upload and compliance | VERIFIED | HistoryScreen.tsx routed; compliance_pct fix applied; Playwright T12, T13 pass |
| UI-05 | 04-08 | During-Session static stepper | VERIFIED | DuringSessionScreen wired; Playwright T18 passes |
| UI-06 | 04-06 | Chat with SSE streaming | VERIFIED | ChatScreen.tsx routed; Playwright T14 passes |
| UI-07 | 04-05 | Mobile bottom tab bar; desktop left sidebar | VERIFIED | BottomTabBar, DesktopSidebar, AppLayout unchanged; Playwright T05 passes |
| UI-08 | 04-03 | Design system tokens | VERIFIED | index.css unchanged; no #000000; no em dashes |
| UI-09 | 04-08 | PWA installable; offline during-session; iOS banner | VERIFIED | vite-plugin-pwa; IOSInstallBanner unchanged |
| UI-10 | 04-03 | Light mode only | VERIFIED | No dark: variant classes; no pure black |

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `frontend/src/tests/today.test.tsx` | 100, 105, 110, 126-128, 137 | Unit test assertions use lowercase TSB labels ('fresh', 'balanced', 'fatigued') but TsbChip renders sentence-case since commit 8666c20 | BLOCKER | 4 Vitest unit tests fail; test suite reports 27/31 pass |

### Human Verification Required

#### 1. Google Calendar OAuth production flow (CAL-03)

**Test:** With Railway backend deployed and Google OAuth verification approved, complete the OAuth flow with a real Google account, trigger onboarding and plan generation, then open Google Calendar.
**Expected:** Sessions appear as events with full detail (objective, structure, targets, duration) in the event body; when a plan adaptation fires, the events update or delete correspondingly.
**Why human:** Requires Railway deployment (not yet done), live BACKEND_BASE_URL, and Google approval of the calendar.events scope verification submission.

#### 2. Onboarding multi-turn interview context (smoke test after Railway deploy)

**Test:** After Railway deploy, complete at least 3 turns of the onboarding interview and then disconnect / reconnect (resume with same conversation_id).
**Expected:** Prior turns are preserved; the agent does not re-ask questions already answered.
**Why human:** Multi-turn SSE context fix (gap 4) is in code but cannot be verified without a live SSE backend.

### Gaps Summary

Two gaps remain blocking the phase goal:

1. **BLOCKER: CAL-03 -- Production OAuth not verifiable** (infrastructure gap). The Phase 4 ROADMAP success criterion #3 explicitly requires "Calendar OAuth uses production credentials, not Testing mode." Railway backend is not deployed (no live callback URL). Google verification has not been submitted to the Verification Centre (required for the `calendar.events` sensitive scope). The `calendar.py` implementation is complete; only the external infrastructure and Google review are missing. No later ROADMAP phase covers this — Phase 5 is scoped to ZWO/iOS only. This gap cannot be deferred; it belongs to Phase 4's goal.

2. **BLOCKER: 4 unit tests regressed by 04-10 TsbChip label fix**. `today.test.tsx` asserts lowercase TSB labels (`fresh`, `balanced`, `fatigued`). `TsbChip.tsx` commit 8666c20 changed labels to sentence case (`Fresh`, `Balanced`, `Fatigued`) for Playwright compatibility. The unit tests were not updated. Fix: change 5 `getByText`/`queryByText` assertions in `today.test.tsx` to sentence case. This is a one-line-per-assertion fix.

**What closed (summary):** All four previously-blocked code gaps are now closed. Screen routing is fully wired. PATCH endpoint exists. Compliance table name is correct. Onboarding multi-turn context is preserved. 34/34 Playwright E2E tests pass. The core UI is functional end-to-end in the browser.

---

_Verified: 2026-06-20T22:15:00Z_
_Verifier: Claude (gsd-verifier)_
