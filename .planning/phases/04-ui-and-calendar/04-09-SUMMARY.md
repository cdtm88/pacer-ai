---
phase: 04-ui-and-calendar
plan: "09"
subsystem: ui
tags: [react, router, fastapi, supabase, google-oauth, sse, onboarding]

requires:
  - phase: 04-ui-and-calendar
    provides: All six real screen implementations, Google Calendar OAuth flow, SSE onboarding and chat endpoints

provides:
  - "router.tsx imports four real screens (OnboardingScreen, HistoryScreen, ChatScreen, SettingsScreen) replacing inline stubs"
  - "PATCH /sessions/{session_id} endpoint marking a session completed with user-scoped auth guard"
  - "Compliance lookup in rides.py queries the real 'sessions' table with correct columns (tss_target, type)"
  - "Onboarding conversation_id captured and used to seed multi-turn SSE context via load_conversation"
  - "Google OAuth consent screen confirmed in-production; calendar.events scope added (Google verification pending)"

affects: [05-during-session-zwo-export]

tech-stack:
  added: []
  patterns:
    - "Gap-closure plan pattern: no new files, only wiring/correctness defects fixed in existing implementations"
    - "PATCH endpoint follows existing GET handler pattern: user_id from Depends(get_current_user), both id+user_id filter for ownership"
    - "SSE conversation context pattern: conversation_id captured from create_conversation, prior turns loaded via load_conversation (mirrors chat.py)"

key-files:
  created: []
  modified:
    - frontend/src/router.tsx
    - api/routes/sessions.py
    - api/routes/rides.py
    - api/routes/onboarding.py

key-decisions:
  - "CAL-03 partial: consent screen is In production with calendar.events scope added; Google OAuth verification (submission to Verification Centre) is an operational task outside code scope; documented as known blocker"
  - "compliance_pct reads tss_target (not tss) and type (not session_type) matching _SESSION_COLUMNS in sessions.py"
  - "onboarding.py follows chat.py pattern exactly: no new parameter on sse_generator; context flows through messages list only"

patterns-established:
  - "User-scoped PATCH: always filter on both id AND user_id to prevent cross-user mutation"
  - "SSE multi-turn: capture create_conversation return value, load prior turns, pass as messages list; never add conversation_id param to sse_generator"

requirements-completed: [UI-01, UI-02, UI-04, UI-06, UI-07, CAL-01, CAL-03, CAL-04]

duration: ~15min
completed: 2026-06-20
status: complete
---

# Phase 04 Plan 09: Gap Closure — Screens, Mark Done, Compliance, Onboarding Context Summary

**Four code wiring gaps closed: router stubs replaced with real screen imports, PATCH /sessions/{id} added, compliance table name fixed, onboarding conversation context preserved; Google OAuth confirmed in-production with pending Google verification documented**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-06-20
- **Completed:** 2026-06-20
- **Tasks:** 5 (4 auto + 1 human-verify)
- **Files modified:** 4

## Accomplishments

- Replaced four inline stub screen functions in router.tsx with real ES imports from `./screens/`; /onboarding, /history, /chat, and /settings now render their actual implementations
- Added `PATCH /sessions/{session_id}` to sessions.py with dual-filter ownership guard (id + user_id), resolving the Mark Done 404
- Fixed compliance lookup in rides.py: table name changed from non-existent `training_sessions` to real `sessions`; select updated to `tss_target, type` matching `_SESSION_COLUMNS`
- Captured `conversation_id` from `create_conversation` in onboarding.py and seeded `sse_generator` messages from `load_conversation`, matching the chat.py multi-turn pattern

## Task Commits

1. **Task 1: Wire four real screens into router.tsx** - `1c7ee6b` (feat)
2. **Task 2: Add PATCH /sessions/{session_id} endpoint** - `6064c66` (feat)
3. **Task 3: Fix compliance table name in rides.py** - `bdae60c` (fix)
4. **Task 4: Preserve onboarding conversation context** - `8e5715e` (fix)
5. **Task 5: Human verify Google OAuth production status** - human checkpoint (no code commit)

## Files Created/Modified

- `frontend/src/router.tsx` - Removed four inline stub components; added imports from `./screens/OnboardingScreen`, `./screens/HistoryScreen`, `./screens/ChatScreen`, `./screens/SettingsScreen`
- `api/routes/sessions.py` - Added `PATCH /sessions/{session_id}` with `validate_uuid`, ownership filter, 404 on no-match
- `api/routes/rides.py` - Changed compliance table from `training_sessions` to `sessions`; updated select to `tss_target,type`; updated TSS read to `tss_target`
- `api/routes/onboarding.py` - Captured `conversation_id` from `create_conversation`; called `load_conversation` to build messages list for `sse_generator`

## Decisions Made

- **CAL-03 partial resolution:** The OAuth consent screen is confirmed "In production" (External) with `calendar.events` scope added. Google's OAuth verification process (submission to Verification Centre with demo video and scope justification) is an operational/business task, not a code task. Until submitted and approved, users will see an "unverified app" warning and the app is subject to a 100-authorization cap. Documented as a known operational blocker for production launch; no code gap remains.
- **compliance_pct column names:** Used `tss_target` and `type` as confirmed in `_SESSION_COLUMNS` in sessions.py, not the stale `tss`/`session_type` names that were in the broken query.
- **sse_generator signature unchanged:** Multi-turn context flows through the messages list only; no new parameter added to `sse_generator`, following the established chat.py pattern.

## Deviations from Plan

None — plan executed exactly as written. All four code gaps were addressed as specified. Task 5 (human-verify) confirmed CAL-03 partially met with operational blocker documented.

## Issues Encountered

**Google OAuth verification gap (operational, not code):** The `calendar.events` scope has been added and the consent screen is In production, but Google's verification process has not been submitted. This results in:
- "Unverified app" warning for all users during OAuth flow
- Hard 100-authorization cap until Google approves the verification submission

**Resolution:** This is outside the scope of code execution. The developer must submit to the Google Verification Centre with a demo video and scope justification. Documented here for Phase 5 / launch readiness tracking.

## Known Stubs

None — all four screen imports connect to fully implemented screen components. No placeholder data or empty return stubs remain.

## Threat Flags

None — no new network endpoints or auth paths introduced beyond the PATCH endpoint, which is guarded by the same `get_current_user` dependency and user-scoped filter as all existing session routes.

## User Setup Required

**Google OAuth Verification (operational):**
To remove the "unverified app" warning and lift the 100-user cap:
1. Go to Google Auth Platform -> OAuth consent screen -> Publish App -> Submit for Verification
2. Provide a justification for `calendar.events` scope (creating/updating calendar events for scheduled training sessions)
3. Record a demo video showing the OAuth flow and calendar event creation
4. Submit via the Google Verification Centre

Until verified, real users can still authorize (no test-user whitelist blocking them) but will see the warning screen.

## Next Phase Readiness

- All Phase 4 gaps are closed; Phase 4 is complete (9/9 plans executed)
- Phase 5 (During-Session and ZWO Export) can begin; no Phase 4 blockers remain in code
- Google OAuth verification is a launch-readiness item that runs in parallel and does not block Phase 5 development

## Self-Check

- `frontend/src/router.tsx` — modified in commit `1c7ee6b`
- `api/routes/sessions.py` — modified in commit `6064c66`
- `api/routes/rides.py` — modified in commit `bdae60c`
- `api/routes/onboarding.py` — modified in commit `8e5715e`

## Self-Check: PASSED

All four task commits verified present. Task 5 was a human-verify checkpoint with no code output — confirmed documented.

---
*Phase: 04-ui-and-calendar*
*Completed: 2026-06-20*
