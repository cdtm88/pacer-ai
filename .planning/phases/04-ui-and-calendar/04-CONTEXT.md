# Phase 4: UI and Calendar - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the complete React PWA frontend for PacerAI: all six screens (Onboarding, Today/Home, Agenda, History, During-Session stub, Chat) plus navigation (mobile bottom tab bar and desktop left sidebar), Supabase Auth with magic link, Google Calendar OAuth2 push/sync, FIT file upload UX, Settings page, and Vercel deployment. The FastAPI backend from Phases 1-3 is fully built; Phase 4 wires the frontend to it.

**In scope:** React + Vite + Tailwind + shadcn/ui frontend, Supabase Auth (magic link), all 6 screens, mobile and desktop nav, Google Calendar OAuth2 connect flow + push/sync, FIT upload drop zone on History, Settings/Profile page, PWA manifest + service worker, Vercel deploy.

**Out of scope:** ZWO file generation (Phase 5), live During-Session timer + wake lock (Phase 5), Web Bluetooth, Strava, dark mode, Telegram bot, full PMC chart.

</domain>

<decisions>
## Implementation Decisions

### Auth and User Identity

- **D-01:** Supabase Auth with magic link (passwordless email). No password signup/login. User enters email, receives a magic link, clicks it to authenticate. Frontend uses `@supabase/supabase-js` client to handle the auth callback and session.
- **D-02:** On app load, check if the user has a profile row. If no profile exists, auto-redirect to `/onboarding`. After the interview completes and profile is saved, redirect to Today (`/`). This is the first-run gate.
- **D-03:** FastAPI JWT middleware (deferred from Phase 3) ships in Phase 4. Supabase JWT is verified on every API request using `python-jose`. The Supabase user_id flows through all API calls as the authenticated identity.

### Google Calendar Integration

- **D-04:** Google Calendar connect lives on a dedicated Settings / Profile page, accessible from the nav (a settings icon or profile link). No inline prompt on Today.
- **D-05:** OAuth2 flow is server-side redirect: frontend links to `GET /calendar/auth` (FastAPI) which builds the Google authorization URL and redirects. Google returns to `GET /calendar/callback` (FastAPI), which stores the tokens encrypted in the DB, then redirects back to the frontend settings page.
- **D-06:** Settings page shows a "Google Calendar: Connected" chip with a disconnect button when connected. Sync failures show a non-blocking sonner toast; they do not disrupt the plan or chat.

### FIT File Upload UX

- **D-07:** FIT upload lives on the History screen as a persistent drop zone or "Upload ride" button at the top of the list. Supports drag-and-drop and click-to-select. Calls the Phase 3 endpoint `POST /rides/upload`.
- **D-08:** After a successful upload: sonner success toast + History list auto-refetches to show the new ride row. No redirect; user stays on History.

### Phase 4 / Phase 5 Boundary

- **D-09:** During-Session screen ships as a full visual layout (large-font current step, next step queued below, smaller later steps) with a static/non-ticking placeholder timer. "Start Session" on the Today screen navigates to `/session`. Phase 5 wires the real `Date.now()` delta timer, auto-advance logic, wake lock, and iOS Safari behavior.
- **D-10:** "Export to Zwift" button appears on the Today session card but is visually disabled with a tooltip ("Coming soon"). Phase 5 adds ZWO file generation and enables the button.

### Design System (locked from PRD)

- **D-11:** Inter for all UI text and headings. Blue-6 (#228BE6) for fills, buttons, and large text only (not small body text). Small blue text uses blue-7 (#1B73C0). Body copy uses --ink (#1A2230) or --ink-2 (#5F646E). Zone colors: recovery #2B8A5B, endurance #228BE6, tempo #F0A030, threshold #E8590C, vo2 #C92A2A.
- **D-12:** Light mode only, no pure blacks anywhere. Neutrals use a faint blue undertone (--bg #F9F9FA, --surface #FFFFFF, --line #DFE0E2).
- **D-13:** No em dashes in any copy or generated text. Use commas, semicolons, colons, or separate sentences.
- **D-14:** TSB form chip (fresh/balanced/fatigued) and CTL sparkline on History are rendered only after 28+ days of PMC data. Show nothing (no placeholder) before that threshold.

### Navigation

- **D-15:** Mobile bottom tab bar with 4 tabs: Today / Agenda / History / Chat. Settings accessible via a gear or profile icon (not a fifth tab).
- **D-16:** Desktop layout: left sidebar with the same 4 destinations; wider multi-column layouts for Today and Agenda.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Product Requirements and Design System
- `prd.md` — Full PRD including design system (color palette, tone, typography) and UI screen descriptions (sections: "Design system" and "MVP capabilities" #12). Primary source for screen content, zone colors, and design conventions.

### Requirements
- `.planning/REQUIREMENTS.md` — All requirements including CAL-01..04 (Google Calendar) and UI-01..07 (all screens). Agent must read to understand acceptance criteria.
- `.planning/ROADMAP.md` §"Phase 4: UI and Calendar" — Phase goal, success criteria, and phase-to-phase boundary with Phase 5.

### Prior Phase Context
- `.planning/phases/03-coaching-loop/03-CONTEXT.md` — Phase 3 implementation decisions including conversation endpoints, SSE streaming at `GET /chat/stream`, FIT upload at `POST /rides/upload`, onboarding at `POST /onboarding/start`, adaptation at `POST /sessions/{id}/missed`.

### Backend Entry Points (for frontend wiring)
- `api/main.py` — FastAPI app with mounted routers (chat, onboarding, rides, adaptations).
- `api/routes/chat.py` — SSE streaming endpoint.
- `api/routes/onboarding.py` — Onboarding start and profile endpoints.
- `api/routes/rides.py` — FIT upload endpoint.
- `api/routes/adaptations.py` — Adaptation endpoints.

### Tech Stack Reference
- `.claude/CLAUDE.md` §"Technology Stack" — Full frontend stack table (React 19, Vite 6, Tailwind 4, shadcn/ui, Recharts, React Router 7, Zustand 5, TanStack Query 5, vite-plugin-pwa, sonner).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `agent/loop.py` — The `run_turn` async function; frontend connects via SSE, not direct import.
- `api/routes/_sse.py` — SSE utilities used by the chat route; frontend reads from EventSource.
- Sports-science tool results include `methodology` string — surface this in History ride detail and adaptation explanations in Chat.

### Established Patterns
- All API routes use async FastAPI handlers; frontend uses TanStack Query for server state.
- Supabase is the DB (Postgres); frontend uses `@supabase/supabase-js` for auth session management only; all other data goes through FastAPI.
- SSE for streaming responses: frontend EventSource reads from `GET /chat/stream?conversation_id=X`.
- Phase 3 D-21: conversations have `context_type: onboarding | coaching | ride_debrief`; Chat screen shows coaching conversations.

### Integration Points
- Auth: Supabase magic link on the frontend; JWT verification middleware in FastAPI (to be added in Phase 4).
- Google Calendar: new routes `GET /calendar/auth` and `GET /calendar/callback` needed in FastAPI.
- FIT upload: `POST /rides/upload` already exists in Phase 3; frontend drop zone calls it with multipart/form-data.
- Onboarding completion: `POST /onboarding/start` opens SSE conversation; profile save triggers redirect to Today.

</code_context>

<specifics>
## Specific Ideas

- The TSB form chip wording from the PRD: "fresh / balanced / fatigued" (derived from TSB). Only show after 28+ days; not a placeholder before that.
- Today screen actions (from PRD): "Start Session", "Export to Zwift" (disabled in Phase 4), "Mark Done", "Mark Missed".
- Agenda intensity zone colors must match the PRD zone color tokens (recovery/endurance/tempo/threshold/vo2).
- History ride detail includes power/HR data and planned-vs-actual compliance (from `validate_session_vs_actual` result).
- PWA: `apple-touch-icon.png` (180x180) in `/public/`. iOS install instructional banner (Share > Add to Home Screen) appears on first visit via a custom component (iOS has no install prompt API).
- During-Session screen step hierarchy: current step in large font, next step below, remaining steps smaller. Static in Phase 4.

</specifics>

<deferred>
## Deferred Ideas

- ZWO file generation and Zwift import acceptance test (Phase 5)
- Live During-Session timer with `Date.now()` deltas, auto-advance, and wake lock (Phase 5)
- NoSleep.js fallback for iOS before 18.4 (Phase 5)
- Full PMC three-line CTL/ATL/TSB chart (Phase 2 post-MVP)
- Dark mode (Phase 2 post-MVP)
- Web Bluetooth live power echo (Phase 2 post-MVP)
- Telegram bot (Phase 2 post-MVP)

</deferred>

---

*Phase: 04-ui-and-calendar*
*Context gathered: 2026-06-20*
