# Phase 5: During-Session and ZWO Export - Context

**Gathered:** 2026-06-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire real behavior into the two Phase 4 stubs: (1) the during-session stepper gets a live `Date.now()` delta timer, auto-advance logic, wake lock + NoSleep.js iOS fallback, and an iOS Safari acceptance test; (2) the "Export to Zwift" button gets a FastAPI `.zwo` file generator with a two-step modal preview, validated against a real Zwift import.

**In scope:** Live timer with auto-advance and manual skip; wake lock + NoSleep.js fallback; "Session complete" screen; ZWO FastAPI endpoint with modal preview download; pre-FTP ZWO with FreeRide + TextEvents; rest-day "Ride anyway" duration picker; iOS Safari testing.

**Out of scope:** Interval sub-structure in the plan generator (future phase); ZWO for non-today sessions; dark mode; Web Bluetooth; Strava; Telegram bot.

</domain>

<decisions>
## Implementation Decisions

### Step Advance Behavior

- **D-01:** Timer auto-advances when it hits 0. A 3-second countdown warning is shown before advancing to the next step ("Starting [next step] in 3...").
- **D-02:** Users can manually tap to advance (skip) to the next step before the timer expires. A visible "Skip" affordance on the current step card.
- **D-03:** When the last step auto-advances, show a "Session complete" screen: total elapsed time, number of steps completed, and a "Done" button that navigates back to Today.

### ZWO Export Flow

- **D-04:** "Export to Zwift" button on Today triggers a two-step modal: shows session name, FTP used (or "assumed 100W" for pre-FTP), and step summary. A "Download" button inside the modal calls the backend endpoint and triggers a browser file download.
- **D-05:** File naming: `{YYYY-MM-DD}-{type}.zwo` — e.g. `2026-06-21-endurance.zwo`. Type comes from the session `type` field.
- **D-06:** ZWO generation lives in the FastAPI backend: `GET /sessions/{id}/export.zwo`. Python generates the XML via stdlib `xml.etree.ElementTree`; returns `Content-Disposition: attachment`. Frontend does not generate XML.
- **D-07:** Export errors (session not found, generation failure) return a structured JSON error; the modal shows a sonner error toast and stays open so the user can retry.

### Pre-FTP ZWO Handling

- **D-08:** When no FTP estimate exists (profile `ftp` is null), use 100W as the assumed FTP. This is conservative and ensures all generated power fractions stay well within the 0.0-2.0 ZWO-02 limit.
- **D-09:** Pre-FTP sessions use `<FreeRide>` segments in the .zwo file rather than `<SteadyState>` power blocks. `<TextEvent>` elements carry the RPE cue (e.g. "Zone 2 effort — conversational pace") at the start of each segment. This is accurate to the intent of early sessions.

### Session Data Routing

- **D-10:** `DuringSessionScreen` calls `getSessionToday()` independently on mount. No session ID is passed via URL param. The "Start Session" button on Today navigates to `/session` only when a session exists (button is disabled when session is null).
- **D-11:** Rest-day "Ride anyway" path: Today's rest-day empty state includes a secondary "Ride anyway" button. Tapping it opens a duration picker modal with preset options (30 / 45 / 60 min) and a custom input. Selecting a duration navigates to `/session` with the chosen duration stored in a Zustand store slice; `DuringSessionScreen` reads the store to generate 3 generic placeholder steps (warm-up 10% / free ride 80% / cool-down 10% of total duration).
- **D-12:** Session structure maps to exactly 3 steps for Phase 5: warmup → main_set → cooldown. Label = segment `description`; duration = segment `duration_minutes`. Interval sub-structure deferred to a future phase.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Requirements

- `.planning/REQUIREMENTS.md` — ZWO-01..05 and IOS-01..03 requirements (all Phase 5 scope). Read before planning to understand acceptance criteria, especially ZWO-02 (power fraction bounds 0.0-2.0), ZWO-04 (sportType, cadence omission), IOS-01 (Wake Lock + NoSleep.js), IOS-02 (Date.now() delta timer + visibilitychange).
- `.planning/ROADMAP.md` §"Phase 5: During-Session and ZWO Export" — Phase goal, success criteria (4 criteria including real Zwift import acceptance test).

### Phase Boundary and Prior Context

- `.planning/phases/04-ui-and-calendar/04-CONTEXT.md` — Phase 4 implementation decisions. D-09: DuringSessionScreen static layout described. D-10: "Export to Zwift" disabled in Phase 4, Phase 5 enables it. D-11/D-12/D-13: design system tokens.

### Existing Source Files to Read Before Implementing

- `frontend/src/screens/DuringSessionScreen.tsx` — Static Phase 4 stub to be replaced with live timer behavior.
- `frontend/src/components/session/SessionStepList.tsx` — Existing step hierarchy component (current/next/remaining). Reuse as-is; wire `currentIndex` state.
- `frontend/src/screens/TodayScreen.tsx` — "Start Session" button navigation and session data loading pattern.
- `frontend/src/lib/api.ts` — `getSessionToday()`, `apiFetch` pattern for the new export endpoint call.
- `api/sports_science/plan.py` — Session `structure` dict shape: `{warmup: {duration_minutes, description}, main_set: {...}, cooldown: {...}}` — the 3-step parse target.
- `api/routes/sessions.py` — Existing session endpoint patterns; new ZWO export route follows same auth/user-id pattern.

### ZWO File Format Reference

- `.claude/CLAUDE.md` §"Integrations" — ZWO format note: community-reverse-engineered reference (h4l/zwift-workout-file-reference); no official Zwift schema. Use stdlib `xml.etree.ElementTree`; no library needed.

### Design System

- `prd.md` — Design system tokens (colors, typography). Design decisions carried forward from Phase 4 apply to the "Session complete" screen and the ZWO export modal.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- `frontend/src/components/session/SessionStepList.tsx` — Renders current (40px bold), next (20px semibold), remaining (16px muted) steps with zone color strip. Accepts `steps: SessionStep[]` and `currentIndex: number`. Phase 5 adds state to drive `currentIndex`.
- `frontend/src/stores/uiStore.ts` — Existing Zustand store for UI state. Add a `freeRideDurationMins` slice here for the "Ride anyway" picker → session screen handoff.
- `frontend/src/lib/api.ts` — `apiFetch` wrapper with JWT injection. Use for the ZWO export modal's download trigger (`GET /sessions/{id}/export.zwo` with `Accept: application/octet-stream`).
- `api/routes/sessions.py` — Auth pattern, `get_current_user` dependency, `validate_uuid` utility. ZWO export route should follow the same structure.
- `api/auth.py` — `get_current_user` FastAPI dependency for JWT verification.

### Established Patterns

- SSE streaming is used only for chat; session/ZWO operations use standard REST.
- All API routes use `async def` handlers with `Depends(get_current_user)`. User ID always comes from the JWT sub claim, never from request body.
- Sonner toasts (`import { toast } from 'sonner'`) for success/error feedback. Used on FIT upload; same pattern for ZWO export.
- TanStack Query (`useQuery`) for server state. `getSessionToday()` is already defined and cached under `['session', 'today']`.
- `xml.etree.ElementTree` is stdlib — no new Python dependency needed for ZWO generation.

### Integration Points

- DuringSessionScreen reads today's session via `useQuery(['session', 'today'])` — same query key as TodayScreen so the cache is shared, no extra fetch.
- "Export to Zwift" button in `SessionCard.tsx` (today card) calls the new export endpoint; modal shown inline.
- ZWO endpoint: `router.get('/sessions/{id}/export.zwo')` mounted in `api/main.py` alongside existing session routes.
- Wake Lock API: `navigator.wakeLock.request('screen')` — feature-detect and fall back to `nosleep.js` for iOS < 18.4. `nosleep.js` is a small npm package (no significant bundle impact).
- `visibilitychange` listener: attach on component mount, detach on unmount. When `document.hidden` becomes false, resync timer from `Date.now()` minus stored start timestamp.

</code_context>

<specifics>
## Specific Ideas

- The "Session complete" screen is a lightweight full-screen overlay (same background as DuringSessionScreen), not a new route. It replaces the step list when `currentIndex >= steps.length`.
- The ZWO export modal previews: workout name (session type + date), FTP used (actual value or "assumed 100W (no FTP estimate yet)"), and a step summary list (warmup / main set / cool-down with durations). Download button triggers the file fetch.
- FreeRide TextEvent timing: place the RPE cue TextEvent at `timeOffset=0` (start of each segment) inside each `<FreeRide>` block.
- The "Ride anyway" free-ride duration generates steps proportionally: 10% warmup / 80% main / 10% cooldown, rounded to nearest minute with minimum 3 min per segment.
- iOS Safari: test the timer and wake lock on a physical device, not iOS Simulator. The acceptance criterion (IOS-03) explicitly requires iOS Safari verification.

</specifics>

<deferred>
## Deferred Ideas

- Interval sub-structure in the plan generator (plan.py): expanding main_set into multiple timed intervals (e.g. 4x5min at threshold + rest) deferred to a future phase when session types grow beyond aerobic base.
- ZWO export for historical/upcoming sessions from Agenda screen (only today's session in Phase 5).
- Full three-line CTL/ATL/TSB PMC chart (Phase 2 post-MVP).
- Dark mode (Phase 2 post-MVP).
- Web Bluetooth live power echo (Phase 2 post-MVP).
- Telegram bot (Phase 2 post-MVP).

</deferred>

---

*Phase: 05-during-session-and-zwo-export*
*Context gathered: 2026-06-21*
