# Phase 4: UI and Calendar - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-20
**Phase:** 04-ui-and-calendar
**Areas discussed:** Auth and user identity, Google Calendar connect UX, FIT upload placement, Phase 5 boundary and stubs

---

## Auth and User Identity

| Option | Description | Selected |
|--------|-------------|----------|
| Real Supabase Auth (Recommended) | Email+password with Supabase Auth; JWT flows from frontend to FastAPI middleware; onboarding gates on profile existence | |
| Hardcoded test user | Single hardcoded user_id in all API calls; no login screen; fastest path to seeing all screens | |

**User's choice:** Real Supabase Auth

---

| Option | Description | Selected |
|--------|-------------|----------|
| Email + password | Standard signup/login forms; works offline after first auth | |
| Magic link (passwordless) | User enters email, receives a link; no password to manage | ✓ |

**User's choice:** Magic link (passwordless)

---

| Option | Description | Selected |
|--------|-------------|----------|
| Auto-redirect to Onboarding (Recommended) | Check profile on app load; if null redirect to /onboarding; after interview redirect to Today | ✓ |
| Show Today with onboarding banner | Land on Today with a prominent 'Complete setup' prompt | |

**User's choice:** Auto-redirect to Onboarding

---

## Google Calendar Connect UX

| Option | Description | Selected |
|--------|-------------|----------|
| Profile / Settings page (Recommended) | Dedicated settings screen with 'Connect Google Calendar' button | ✓ |
| Prompted inline on Today screen | Banner prompt first time Today loads with a plan; no separate settings page | |

**User's choice:** Profile / Settings page

---

| Option | Description | Selected |
|--------|-------------|----------|
| Server-side redirect via FastAPI (Recommended) | Frontend links to GET /calendar/auth; Google returns to GET /calendar/callback on backend; stores token; redirects to frontend | ✓ |
| Frontend-initiated with popup | React opens popup to Google OAuth; popup posts token to parent | |

**User's choice:** Server-side redirect via FastAPI

---

| Option | Description | Selected |
|--------|-------------|----------|
| Connected chip + manual disconnect + toast on failure (Recommended) | Settings shows 'Google Calendar: Connected' chip with disconnect button; sync failures show sonner toast; non-blocking | ✓ |
| Sync status on every session row | Each Agenda row shows calendar sync icon (synced/pending/failed) | |

**User's choice:** Connected chip + manual disconnect + toast on failure

---

## FIT Upload Placement

| Option | Description | Selected |
|--------|-------------|----------|
| History screen drop zone (Recommended) | Persistent drop zone or 'Upload ride' button at top of History; accepts drag-and-drop and click-to-select | ✓ |
| Floating action button on Today | Prominent + FAB on Today that opens file picker | |
| Both History and Today | History has drop zone; Today shows quick-upload prompt after session date passes | |

**User's choice:** History screen drop zone

---

| Option | Description | Selected |
|--------|-------------|----------|
| Toast + auto-refresh History list (Recommended) | Success toast via sonner + History list re-fetches to show new ride row | ✓ |
| Navigate to ride detail | After upload, navigate directly to parsed ride detail screen | |
| Trigger chat debrief | Open Chat tab with agent's automatic ride debrief message | |

**User's choice:** Toast + auto-refresh History list

---

## Phase 5 Boundary and Stubs

| Option | Description | Selected |
|--------|-------------|----------|
| Full screen layout, no timer (Recommended) | Complete During-Session UI (large-font step display, step list, next-step queue) with static placeholder timer | ✓ |
| Navigation placeholder only | Simple 'Coming in Phase 5' stub with screen title | |
| Skip entirely | No During-Session screen in Phase 4 | |

**User's choice:** Full screen layout, no timer

---

| Option | Description | Selected |
|--------|-------------|----------|
| Visible but disabled with tooltip (Recommended) | Export to Zwift button visible, disabled with 'Coming soon' tooltip | ✓ |
| Hide entirely in Phase 4 | Don't render the button; Phase 5 adds it | |

**User's choice:** Visible but disabled with tooltip

---

| Option | Description | Selected |
|--------|-------------|----------|
| Navigates to the static During-Session screen (Recommended) | Start Session navigates to /session showing full layout with static step list and placeholder timer | ✓ |
| Disabled button with tooltip | Start Session disabled like Export to Zwift | |

**User's choice:** Navigates to the static During-Session screen

---

## Claude's Discretion

No areas were delegated to Claude's discretion — user made explicit decisions on all questions.

## Deferred Ideas

- ZWO file generation (Phase 5)
- Live session timer with Date.now() deltas and auto-advance (Phase 5)
- Wake Lock API + NoSleep.js fallback for iOS (Phase 5)
- Full PMC CTL/ATL/TSB chart (Phase 2 post-MVP)
- Dark mode (Phase 2 post-MVP)
- Web Bluetooth live power echo (Phase 2 post-MVP)
- Telegram bot (Phase 2 post-MVP)
