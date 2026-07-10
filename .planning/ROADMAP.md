# Roadmap: PacerAI

## Overview

PacerAI builds trust outward from a single anchor: a deterministic, unit-tested sports-science tool library. No downstream layer can be credible until that anchor is verified. From there, the agent wiring proves the trust model holds under real LLM calls. Then the coaching loop assembles around real ride data. Then the UI is built on working endpoints. Finally, the iOS-specific during-session view and ZWO export ship as a self-contained integration layer.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Sports-Science Foundation** - Tool library, DB schema, and Supabase setup — the trust anchor everything else depends on (completed 2026-06-19)
- [x] **Phase 2: Agent Core** - Agent loop, tool registry, SSE streaming, and trust-model enforcement proven end-to-end (completed 2026-06-20)
- [x] **Phase 3: Coaching Loop** - FIT ingestion, plan generation, onboarding interview, and adaptive re-planning (completed 2026-06-20)
- [x] **Phase 4: UI and Calendar** - React PWA, all screens, Google Calendar integration, Vercel deployment (completed 2026-06-20)
- [x] **Phase 5: During-Session and ZWO Export** - iOS-safe session stepper with wake lock, ZWO file generator with Zwift acceptance test (completed 2026-06-21)
- [x] **Phase 6: Core Loop Persistence** - Persist generated plans as sessions rows, fix FTP/PMC correctness, link rides to sessions, idempotent adaptations (completed 2026-07-03)
- [x] **Phase 7: Deploy Consolidation** - Vercel is the sole deploy target: remove Railway artifacts, make SSE and background FIT processing serverless-safe, resolve config conflicts, env docs, DB indexes (completed 2026-07-03)
- [x] **Phase 8: Trust Model Integrity** - Persist audit log, scan tool inputs, tighten attribution, collect LTHR, correct HR zones and load constraints (completed 2026-07-04)
- [x] **Phase 9: Frontend Resilience** - Chat SSE recovery and history reload, session persistence staleness, iOS export/auth fixes, contract mismatches, error boundary (completed 2026-07-07)
- [x] **Phase 10: Hygiene and Safety Nets** - Repair stale tests, contract tests, SSE token exchange, rate limiting, CI, repo cleanup (completed 2026-07-08)
- [x] **Phase 11: Ride Analysis Dashboard** - Per-second ride visualisation (power, HR, cadence, speed, elevation) with lap markers, synced hover readout, and a server-computed time-in-HR-zone breakdown; charts appear only for channels present in the file (completed 2026-07-09)
- [x] **Phase 12: Athletic Redesign** - Zwift/Strava-grade visual overhaul: dark ride cockpit with hero watt target and session profile rail, display numerals, Today hub with stat tiles and fat Start CTA, zone-color commitment, unified component system (buttons, tokens, shared zone map), Progress/Agenda/Settings polish (completed 2026-07-09)

## Phase Details

### Phase 1: Sports-Science Foundation

**Goal**: A complete, unit-tested sports-science tool library and database schema exist; every physiological function is verified correct before any other layer depends on it
**Depends on**: Nothing (first phase)
**Requirements**: TOOL-01, TOOL-02, TOOL-03, TOOL-04, TOOL-05, TOOL-06, TOOL-07, TOOL-08, TOOL-09, TOOL-10, TRUST-01, TRUST-02, GAP-01, GAP-02, GAP-03
**Success Criteria** (what must be TRUE):

  1. All tool-library functions return a structured result with value, unit, methodology name, and inputs; every function passes its unit tests including edge cases (zeros in NP, spike filter, cold-start guard, back-protective constraints, sparse data)
  2. The CP model rejects any FTP estimate derived from fewer than 4 quality efforts; `update_pmc` does not emit TSB values until 28+ days of data are present
  3. The `sports_science/` module has zero Anthropic SDK imports; no import path connects it to the agent layer
  4. The `log_capability_gap` function appends a structured entry to the `capability_gaps` table and returns a user-facing fallback message; it is registered as an Anthropic tool schema in TRUST-02 and only the tool registry maps sports_science functions to tool schemas
  5. The 8-table Supabase schema (users, profiles, sessions, rides, pmc_history, conversations, messages, capability_gaps) is migrated and accessible

**Plans**: 6/6 plans complete
**Wave 1**

- [x] 01-01-PLAN.md — Wave 0: test infra, deps, venv, Supabase CLI, ToolResult contract + constants
- [x] 01-02-PLAN.md — Wave 1: power and HR zones (TOOL-01, TOOL-02)
- [x] 01-03-PLAN.md — Wave 1: TSS/NP/IF metrics and Banister PMC (TOOL-04, TOOL-05)
- [x] 01-04-PLAN.md — Wave 1: FTP CP model, load progression, compliance (TOOL-03, TOOL-06, TOOL-07)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-05-PLAN.md — Wave 2: Supabase schema + db push, log_capability_gap, package exports (TOOL-08, GAP-01/02/03, TRUST-02)

**Wave 1 (gap closure)** *(from 01-VERIFICATION.md — 2/5 must-haves; three fixes)*

- [x] 01-06-PLAN.md — Gap closure: enforce vacuous TRUST-01 boundary test, reachable FTP two-pass filter for the beginner persona, observable capability-gap DB failures (TRUST-01, TOOL-03/06/08/10, GAP-01)

### Phase 2: Agent Core

**Goal**: The agent loop completes multi-turn conversations, dispatches tool calls in parallel, and provably never emits an unsourced physiological number
**Depends on**: Phase 1
**Requirements**: AGENT-01, AGENT-02, AGENT-03, AGENT-04, AGENT-05, AGENT-06, TRUST-03, TRUST-04, TRUST-05
**Success Criteria** (what must be TRUE):

  1. The agent loop uses the raw `anthropic` SDK with an explicit `stop_reason == "tool_use"` check; `claude-agent-sdk` is absent from the dependency tree
  2. A multi-turn conversation with parallel tool_use blocks completes without errors; tool retry (max 3) and deduplication by `(name, args_hash)` per turn are verified in tests
  3. The response-parsing trust layer catches an injected unsourced physiological number (watts, zones, TSS, FTP, CTL/ATL/TSB), triggers a retry, and logs a capability-gap entry; unsourced numbers never reach the frontend
  4. Chat responses stream correctly to the frontend via SSE using EventSource; the SSE endpoint is functional
  5. The compliance test suite passes: the agent does not emit unsourced physiological numbers across a representative set of scenarios

**Plans**: 6/6 plans complete

Plans:

- [x] 02-01-PLAN.md — Wave 1: backend deps (no claude-agent-sdk), agent/ + api/ scaffolding, async capability_gap upgrade
- [x] 02-02-PLAN.md — Wave 2: tool registry + dispatcher and the raw-SDK agent loop (dedup, parallel gather, retry, audit)
- [x] 02-03-PLAN.md — Wave 3: trust-model response scanner and FastAPI SSE chat endpoint
- [x] 02-04-PLAN.md — Wave 4: tests/agent/ compliance suite proving AGENT-01..06 and TRUST-03/04/05
- [x] 02-05-PLAN.md — Wave 5: offline anthropic SDK contract-conformance test (closes A1/A2/Open Question 1 — loop's assumed SDK shape verified against the real installed package)
- [x] 02-06-PLAN.md — Wave 5: trust scanner representative-corpus characterization (Success Criterion 5; zero false-negative/false-positive rates; answers Open Question 2)

### Phase 3: Coaching Loop

**Goal**: A new user completes the onboarding interview, receives a safe plan with RPE/HR targets (no FTP required), uploads a real .FIT file that updates the PMC, and sees the plan adapt with a cited sports-science explanation
**Depends on**: Phase 2
**Requirements**: ONBD-01, ONBD-02, ONBD-03, ONBD-04, PLAN-01, PLAN-02, PLAN-03, PLAN-04, PLAN-05, PLAN-06, FIT-01, FIT-02, FIT-03, FIT-04, FIT-05, FIT-06, ADAPT-01, ADAPT-02, ADAPT-03, ADAPT-04, ADAPT-05, TRANSP-01, TRANSP-02, TRANSP-03
**Success Criteria** (what must be TRUE):

  1. A new user with zero prior data completes the interview; the persisted profile includes injury/back status, schedule, goals, and equipment; the user sees a confirmation summary before plan generation
  2. The generated plan prescribes RPE/HR targets for early sessions with no power targets; power targets appear only after FTP confidence reaches medium (4+ quality efforts); every physiological number in the plan traces to a tool-library call
  3. Uploading a real Zwift .FIT file parses power, HR, cadence, and duration; `compute_tss` and `update_pmc` run on the parsed data; results persist to `rides` and `pmc_history`; the acceptance test against a real Zwift .FIT passes
  4. A missed session causes the agent to re-plan; micro-adjustments (1-3 sessions) are distinguished from macro replanning (2+ signals required); no macro replan shifts more than 30% of upcoming sessions without surfacing a change summary
  5. Every plan change is explained in chat with specific TSS/CTL/ATL/TSB values cited from tool calls and a named sports-science principle; every change is persisted to the adaptation log

**Plans**: 6/6 plans complete

Plans:
**Wave 1**

- [x] 03-01-PLAN.md — Wave 1: DB migration (plans/adaptations + column additions) and [BLOCKING] supabase db push
- [x] 03-02-PLAN.md — Wave 1: fitdecode dep, save_profile + generate_plan tools (atomic TRUST-02), Wave 0 test stubs + Zwift fixture

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 03-03-PLAN.md — Wave 2: onboarding interview endpoint, dynamic system prompt, DB-backed conversations (ONBD-01..04)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 03-04-PLAN.md — Wave 3: FIT ingestion pipeline, TSS/PMC background task, real Zwift acceptance test (FIT-01..06)

**Wave 4** *(blocked on Wave 3 completion)*

- [x] 03-05-PLAN.md — Wave 4: adaptive re-planning, micro/macro + 30% guard, adaptation log, transparency (ADAPT-01..05, TRANSP-01..03)

**Wave 5 (gap closure)** *(from 03-VERIFICATION.md — CR-01 blocker + WR-06)*

- [x] 03-06-PLAN.md — Collision-aware scheduled_date resolution (CR-01) + regression test; SSE done-gated assistant persistence (WR-06) (PLAN-01, FIT-04, FIT-05, ADAPT-01, TRANSP-01)

**UI hint**: yes

### Phase 4: UI and Calendar

**Goal**: The app is usable and clean on both phone and desktop; all screens are functional; Google Calendar events are created, updated, and deleted in sync with plan changes
**Depends on**: Phase 3
**Requirements**: CAL-01, CAL-02, CAL-03, CAL-04, UI-01, UI-02, UI-03, UI-04, UI-05, UI-06, UI-07, UI-08, UI-09, UI-10
**Success Criteria** (what must be TRUE):

  1. All six screens (Onboarding, Today/Home, Agenda, History, During-Session, Chat) are implemented and navigable; mobile bottom tab bar and desktop left sidebar both work
  2. The Today screen shows today's session card with Start Session, Export to Zwift, Mark Done, and Mark Missed actions; the TSB form chip appears only after 28+ days of data
  3. Google Calendar events are created for planned sessions with full detail in the event body; when the plan changes, corresponding events update, move, or delete; Calendar OAuth uses production credentials, not Testing mode
  4. Calendar sync failures surface gracefully to the user without disrupting the plan or chat
  5. The app is installable as a PWA on iOS and Android; it works offline for the during-session view; the iOS install instructional banner appears on first visit; light mode only with no pure blacks and no em dashes in any copy

**Plans**: 21/21 plans complete

Plans:

- [x] 04-09-PLAN.md
- [x] 04-10-PLAN.md — Commit E2E test fixes and verify 34/34 Playwright tests pass
- [x] 04-11-PLAN.md — Human confirmation: Google Cloud OAuth consent screen published (CAL-03)

**Wave 6** *(UAT gap closure, parallel)*

- [x] 04-12-PLAN.md — Onboarding loop fix: call save_messages so multi-turn context persists (UAT GAP 6)
- [x] 04-14-PLAN.md — Auth redirect loop fix: persist Supabase session, seed from getSession (UAT GAP 1)
- [x] 04-16-PLAN.md — FIT upload 422 fix: accurate duration parse + surfaced error reason (UAT GAP 4)

**Wave 7** *(UAT gap closure, depends on Wave 6)*

- [x] 04-13-PLAN.md — Chat no-response fix: read message param + persist turns (UAT GAP 5)
- [x] 04-15-PLAN.md — Session actions fix: Mark Done / Mark Missed diagnosis + visible failures (UAT GAPs 2, 3)

**Wave 8** *(UAT gap closure round 2, parallel — re-run UAT still failing)*

- [x] 04-17-PLAN.md — Auth callback race fix: skip null getSession seed on /auth/callback (UAT GAP 1)
- [x] 04-18-PLAN.md — Mark Missed dialog: replace inline block with shadcn AlertDialog (UAT GAP 2)
- [x] 04-19-PLAN.md — Mark Done .select() fix + onboarding save_messages verify (UAT GAPs 3, 6)
- [x] 04-20-PLAN.md — Chat fix: map conversation_id to id + sseUrl query-string join (UAT GAP 5)
- [x] 04-21-PLAN.md — FIT upload e2e LIFO fix: register /rides/ before /rides/upload (UAT GAP 4)

**Wave 1** *(foundation, parallel)*

- [x] 04-02-PLAN.md — api/auth.py JWT dependency + JWT middleware across all existing routes + auth tests
- [x] 04-03-PLAN.md — Frontend scaffold (Vite/React 19/Tailwind v4/shadcn), design tokens, PWA config, router skeleton

**Wave 2** *(data layer)*

- [x] 04-01-PLAN.md — DB migration 0003 + [BLOCKING] supabase db push, new backend read/create endpoints (consume api/auth.py)

**Wave 3** *(auth shell)*

- [x] 04-04-PLAN.md — Supabase magic-link auth, API client, stores, AuthGate + FirstRunGate

**Wave 4** *(core screens, parallel)*

- [x] 04-05-PLAN.md — Navigation shell + Today + Agenda screens
- [x] 04-06-PLAN.md — History (FIT upload + CTL sparkline) + Chat + Onboarding (SSE)

**Wave 5** *(calendar + during-session/PWA, parallel)*

- [x] 04-07-PLAN.md — Google Calendar OAuth2 + sync hooks (initial + replan push) + Settings screen
- [x] 04-08-PLAN.md — During-Session static screen + iOS install banner + PWA icons + Vercel deploy

**UI hint**: yes

### Phase 5: During-Session and ZWO Export

**Goal**: The during-session stepper works reliably on iOS Safari with the timer surviving tab switches; a generated .zwo file imports cleanly in Zwift
**Depends on**: Phase 4
**Requirements**: ZWO-01, ZWO-02, ZWO-03, ZWO-04, ZWO-05, IOS-01, IOS-02, IOS-03
**Success Criteria** (what must be TRUE):

  1. The during-session stepper shows the current step (target + duration) in large font with next step queued; the timer auto-advances; the screen stays on via Wake Lock API with NoSleep.js fallback for iOS before 18.4
  2. The session timer uses `Date.now()` deltas; a `visibilitychange` event resyncs the timer correctly after returning from a background tab; verified on iOS Safari (not only Chromium)
  3. A planned structured session exports as a valid .zwo file; Power values are FTP fractions between 0.0 and 2.0; pre-FTP sessions use a conservative assumed FTP with RPE text segments; `<sportType>bike</sportType>` is present; Cadence is omitted when not specified
  4. The generated .zwo file imports cleanly in Zwift; the acceptance test against a real Zwift import passes before ZWO export is considered production-ready

**Plans**: 5/5 plans complete

Plans:
**Wave 1** *(backend + hooks, parallel)*

- [x] 05-01-PLAN.md — ZWO XML generator (api/sports_science/zwo.py) + GET /sessions/{id}/export.zwo endpoint + unit tests (ZWO-01..04)
- [x] 05-02-PLAN.md — nosleep.js + useSessionTimer (Date.now delta) + useWakeLock hooks + hook tests (IOS-01, IOS-02)

**Wave 2** *(frontend wiring, parallel)*

- [x] 05-03-PLAN.md — DuringSessionScreen rewrite (timer, auto-advance, wake lock, complete overlay) + DurationPickerModal + Ride-anyway flow
- [x] 05-04-PLAN.md — exportSessionZwo + ZwoExportModal + enable "Export to Zwift" in SessionCard

**Wave 3** *(manual acceptance, blocking)*

- [x] 05-05-PLAN.md — Human checkpoints: real Zwift import (ZWO-05) + physical iOS Safari timer/wake-lock verification (IOS-03)

**UI hint**: yes

### Phase 6: Core Loop Persistence

**Goal:** A generated plan becomes real database state and ride data flows through it correctly: plan confirmation writes `plans` and `sessions` rows; Today/Agenda/ZWO/calendar read real sessions; estimated FTP is actually used (fix `ftp_watts` vs `ftp` key mismatch, add missing `profiles.ftp`/`lthr` columns); PMC uses ride date not upload date, decays through zero-TSS gap days, sums same-day rides, and dedups re-uploaded FIT files; rides link to sessions and mark them completed; adaptation checks are idempotent (signals consumed once, `/missed` endpoint works, macro-replan confirm endpoint exists).
**Requirements**: No new IDs; repairs existing FIT-04, FIT-05, TOOL-03, TOOL-05, PLAN-01, PLAN-04, ONBD-04, ADAPT-01, ADAPT-02, ADAPT-03, ADAPT-04, TRANSP-02 (all marked complete but broken in APP-REVIEW-260703)
**Depends on:** Phase 5
**Plans:** 6/6 plans complete

Plans:
**Wave 1** *(schema foundation, blocking)*

- [x] 06-01-PLAN.md — Migration 0005 (pmc_history tss/days_of_data, sessions 'missed', profiles ftp/lthr, rides content_hash+UNIQUE, adaptations trigger_session_ids/status) + [BLOCKING] supabase db push

**Wave 2** *(parallel, depend on 06-01)*

- [x] 06-02-PLAN.md — Plan persistence: dispatch_tool generate_plan hook writes plans+sessions rows, rewrites plan_id; save_profile lthr write-back
- [x] 06-03-PLAN.md — PMC recompute-from-scratch day-series module (gap-day decay, same-day sum, calendar days_of_data)
- [x] 06-04-PLAN.md — Adaptation idempotency (trigger_session_ids + missed status flip), live 30% shift guard, POST /adaptations/{id}/confirm, compliance None-guard

**Wave 3** *(depends on 06-01 + 06-03)*

- [x] 06-05-PLAN.md — Rides pipeline: FTP key fix + profiles.ftp write-back, content-hash dedup, ride-session link, inline-await (Vercel), recompute_pmc_for_user

### Phase 7: Deploy Consolidation

**Goal:** Vercel is the sole, fully working deploy target (decision 2026-07-03: Railway abandoned). Remove Railway artifacts (Dockerfile, railway.toml, Railway references in README/CLAUDE.md); resolve the conflicting root vs frontend `vercel.json` so `/api/*` reliably reaches the Python function and the SPA is served as static build (drop the api/index.py frontend/dist fallback); make the serverless path correct: SSE streaming on `/chat/stream` and `/onboarding/*` verified within Vercel function limits, and all post-response BackgroundTasks work (ride TSS/PMC pipeline, calendar pushes, adaptation sync) moved inline-awaited or to a durable mechanism since Vercel freezes functions after the response; README env-var table corrected and completed (SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, CALENDAR_FERNET_KEY, BACKEND_BASE_URL, ANTHROPIC_MODEL) with Vercel env setup documented; indexes added on all user_id/FK columns; `fits` storage bucket provisioned as config.
**Requirements**: TBD
**Depends on:** Phase 6
**Plans:** 4/4 plans complete

Plans:

- [x] 07-01-PLAN.md — Remove Railway/Docker artifacts; correct README + .claude/CLAUDE.md to Vercel-only with accurate env-var table
- [x] 07-02-PLAN.md — Convert the 3 remaining BackgroundTasks call sites (onboarding + 2 adaptation calendar syncs) to inline-await
- [x] 07-03-PLAN.md — Add FK/user_id index migration (0007) + push to linked Supabase; verify fits bucket present
- [x] 07-04-PLAN.md — Restructure vercel.json routing + strip api/index.py SPA fallback; verify preview deploy (routing + SSE) and decommission Railway

### Phase 8: Trust Model Integrity

**Goal:** The trust model is airtight and verifiable: audit log persisted per turn (TRUST-04), tool inputs scanned so invented numbers cannot launder through tool calls, bare-number attribution uses word-boundary and tolerance matching instead of substring, prior-turn numbers seeded to kill cross-turn false positives, LTHR (or explicit RPE-only fallback) collected in onboarding, HR zone constants match the claimed Coggan methodology, Zone 2 targets safe for a returning beginner, and generate_plan consumes current_ctl/load_targets/preferred_days so back-protective caps actually constrain sessions.
**Requirements**: TRUST-06, TRUST-07, TRUST-08, TRUST-09, ONBD-05, PLAN-07, TOOL-02 (amend); re-verifies TRUST-03, TRUST-04, TRUST-05, PLAN-06
**Depends on:** Phase 7
**Plans:** 8/8 plans complete

Plans:
**Wave 1**

- [x] 08-01-PLAN.md — Audit storage layer: audit_log migration + audit.py (write/reload) + schema push (TRUST-06 storage)
- [x] 08-02-PLAN.md — Attribution matching rewrite: numeric-token + tolerance replaces substring (TRUST-08)
- [x] 08-03-PLAN.md — HR zone constants fix + Zone 2 safety + estimate_lthr_from_max_hr tool (TOOL-02 amend, ONBD-05 estimator)
- [x] 08-04-PLAN.md — generate_plan CTL-gap progression + preferred_days computation (PLAN-07)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 08-05-PLAN.md — conversation_id threading + durable audit writes + cross-turn seeding (TRUST-06 wiring, TRUST-09)

**Wave 3** *(blocked on Wave 2 completion)*

- [x] 08-06-PLAN.md — generate_plan server-side value injection (TRUST-07)
- [x] 08-07-PLAN.md — onboarding LTHR collection + hr_zones_available flag (ONBD-05)

**Wave 1 (gap closure)** *(from 08-UAT.md Test 1 blocker)*

- [x] 08-08-PLAN.md — self-reported attribution channel: user-stated LTHR echo passes scan_buffer without a tool call (ONBD-05 Branch A fix, TRUST-03)

### Phase 9: Frontend Resilience

**Goal:** The UI survives real-world failure modes across the full 14-item Critical+Major app-review list (D-01, not just the original 8): chat recovers from SSE errors and empty tool-only turns (no more bricked input); onboarding streams recover the same way; conversation history reloads the existing conversation instead of creating a new row; persisted sessions carry id+date so stale records cannot hijack Today or mark the wrong session done; live-session resume fast-forwards correctly through multiple elapsed steps; iOS ZWO export works within the user-gesture window and surfaces the real backend error; auth callback no longer double-exchanges the PKCE code; a new sign-in clears cross-account cached data; Ride field names match the backend; upload shows progress, validates drag-drop, and invalidates PMC/session queries; AppLayout uses h-dvh so the chat input stays pinned; and a per-route error boundary replaces white-screen crashes while keeping the nav shell mounted.
**Requirements**: TBD (phase predates REQ-ID mapping; tracked by the 14 bug-item numbers from 09-RESEARCH.md / 09-CONTEXT.md)
**Depends on:** Phase 8
**Plans:** 7/7 plans complete

Plans:
**Wave 1**

- [x] 09-01-PLAN.md — Chat SSE resilience + shared StreamErrorBanner (items 2, 3)
- [x] 09-02-PLAN.md — Stale-session guard + live-resume fast-forward (items 1, 8)
- [x] 09-03-PLAN.md — Ride field contract + ZWO export error-shape/iOS (items 5, 6, 7)
- [x] 09-04-PLAN.md — Auth + router resilience: cache clear, single-exchange, error boundary (items 10, 11, 12)
- [x] 09-05-PLAN.md — Upload progress/drag-drop/invalidation + AppLayout h-dvh (items 14, 9)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 09-06-PLAN.md — Onboarding stream resilience, wave 2 (item 13)
- [x] 09-07-PLAN.md — History reload on cache miss, backend read endpoint + frontend, wave 2 (item 4)

### Phase 10: Hygiene and Safety Nets

**Goal:** The test suite is green and guards the seams: 8 stale SSE tests authenticate properly, capability-gap test-order leak fixed, Playwright mocks match real response shapes, frontend-backend contract tests added (would have caught the Ride/Profile/FTP-key mismatches), short-lived SSE token exchange removes JWTs from query strings, LLM endpoints rate-limited, CI runs pytest+vitest+ruff, repo cleaned (root node_modules, test-ride.fit, root .gitignore).
**Requirements**: TBD (phase predates REQ-ID mapping; tracked by the 8 scope items in the goal line, covered as ITEM-01..ITEM-08)
**Depends on:** Phase 9
**Plans:** 6/6 plans complete

Plans:
**Wave 1** *(parallel — no file conflicts)*

- [x] 10-01-PLAN.md — Backend test hygiene: fix 8 stale SSE tests, profile.py reset seam, contract tests (items 1, 2, 4; D-01)
- [x] 10-02-PLAN.md — Playwright e2e mock field-name fixes to match the real Ride contract (item 3)
- [x] 10-03-PLAN.md — Short-lived SSE token exchange, POST /chat/token, removes full JWT from ?token= (item 5; D-04)

**Wave 2** *(blocked on 10-03 — shared chat.py)*

- [x] 10-04-PLAN.md — In-process per-user_id rate limiting on LLM endpoints + rate-limit banner (item 6; D-02, D-03)

**Wave 3** *(blocked on 10-01/10-03/10-04 — CI guards a green suite)*

- [x] 10-05-PLAN.md — Report-only GitHub Actions CI (ruff+pytest+vitest) + repo cleanup (items 7, 8; D-05)

**Gap Closure** *(item 7 failed real-CI verification — e2e job out of D-05 scope + pre-existing frontend flake)*

- [x] 10-06-PLAN.md — Revert out-of-scope e2e job to restore D-05 scope, guard session.test.tsx flake, confirm green on a REAL GitHub Actions run (item 7; D-05)

### Phase 11: Ride Analysis Dashboard

**Goal:** A Ride Analysis tab renders a per-second visualisation of any uploaded ride (power, HR, cadence, speed, elevation) with lap markers, a synced hover readout, and a time-in-HR-zone breakdown. Time series is served parse-on-demand via a new `GET /api/rides/{id}/stream` (re-parses the stored .fit, no persistence, no migration). Channels appear only when present, so indoor Zwift rides with no elevation or GPS render cleanly. All zone maths are computed server-side in a `time_in_hr_zones` ToolResult that reuses `calculate_hr_zones` (TRUST-01).
**Requirements**: RIDE-01..RIDE-12 (see 11-CONTEXT.md)
**Decisions**: D-11-01..D-11-07 | **Threats**: T-11-01..T-11-03
**Depends on:** Phase 1 (sports-science tools), Phase 6 (rides + Storage persistence)
**Context seeded:** `.planning/phases/11-ride-analysis-dashboard/11-CONTEXT.md` (from author PRD `docs/phase-11-ride-analysis-roadmap.html`)
**Plans:** 7/7 plans complete

Plans (waves; TDD — tests written test-first within each backend/frontend feature plan, RIDE-12 distributed across them + gated in 11-07):

**Wave 0** *(backend data layer, parallel — disjoint files)*

- [x] 11-01-PLAN.md — [tdd] Sibling `parse_fit_stream` + `_stream_utils` (presence, downsample) + backend parser tests (BE; RIDE-01/02/03/12) — wave 0
- [x] 11-02-PLAN.md — [tdd] `time_in_hr_zones` ToolResult reusing `calculate_hr_zones` + hand-checked tests (BE; RIDE-04/12) — wave 0

**Wave 1** *(stream endpoint, depends on 11-01 + 11-02)*

- [x] 11-03-PLAN.md — [tdd] `GET /rides/{id}/stream` endpoint + integration tests (BE; RIDE-05/12; T-11-01/02/03) — wave 1

**Wave 2** *(frontend contract, depends on 11-03)*

- [x] 11-04-PLAN.md — `RideStream` type + `getRideStream` fetcher (FE; RIDE-06) — wave 2

**Wave 3** *(chart component, depends on 11-04)*

- [x] 11-05-PLAN.md — `RideChart`: per-present-channel charts, syncId hover, lap lines, backend-sourced zone bar + frontend test (FE; RIDE-07/08/09/12) — wave 3

**Wave 4** *(screen + routing + nav, depends on 11-04 + 11-05)*

- [x] 11-06-PLAN.md — `AnalysisScreen` + `/analysis` and `/rides/:rideId` routes + Analysis nav tab (both navs) + RideRow "View analysis" link + AppLayout title (FE; RIDE-10/11) — wave 4

**Wave 5** *(phase gate, depends on 11-05 + 11-06)*

- [x] 11-07-PLAN.md — Full-suite green (fixtures already placed) + blocking human visual/interaction smoke-check (BE+FE; RIDE-12) — wave 5

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Sports-Science Foundation | 6/6 | Complete    | 2026-06-19 |
| 2. Agent Core | 6/6 | Complete    | 2026-06-20 |
| 3. Coaching Loop | 6/6 | Complete    | 2026-06-20 |
| 4. UI and Calendar | 21/21 | Complete   | 2026-06-21 |
| 5. During-Session and ZWO Export | 5/5 | Complete    | 2026-06-21 |
| 6. Core Loop Persistence | 5/5 | Complete    | 2026-07-03 |
| 7. Deploy Consolidation | 4/4 | Complete    | 2026-07-03 |
| 8. Trust Model Integrity | 8/8 | Complete    | 2026-07-04 |
| 9. Frontend Resilience | 7/7 | Complete    | 2026-07-07 |
| 10. Hygiene and Safety Nets | 6/6 | Complete    | 2026-07-08 |
| 11. Ride Analysis Dashboard | 7/7 | Complete    | 2026-07-09 |
| 12. Athletic Redesign | 9/9 | Complete    | 2026-07-09 |

### Phase 12: Athletic Redesign

**Goal:** The app feels like a sports product (Zwift/Strava register), not a SaaS dashboard: the during-ride view becomes a dark cockpit with the watt target as an arm's-length hero and a session profile rail; hero numerals get a display treatment; Today becomes the hub with stat tiles (duration/est TSS/IF) and one fat Start CTA; zone colors carry intensity everywhere; all buttons/tokens/zone maps unify into one component system.
**Requirements**: TBD (visual overhaul of existing screens; no new product capabilities. Readiness check-in flow and generation limits are explicitly deferred to a later phase)
**Depends on:** Phase 10 (independent of Phase 11; if Phase 11 lands first, its Analysis screen adopts this spec)
**Reference:** ref-wireframes-full.png (repo root) for structure and flow of the on-bike, pre-ride, and progress states. Design review 2026-07-09 identified: light-tinted during-session screen with timer as hero (should be dark, watts-hero), Inter 800 requested but not loaded, shadcn button tokens disconnected from palette, duplicated zone maps and PromptChip, off-token colors in Settings, HTML table in RideRow.
**Constraint amendments (user-approved direction):** during-session is a dark cockpit surface (exception to light-mode-only MVP; still no pure blacks); one display face (condensed) permitted for hero numerals only.
**Decisions:** D-1..D-12 (12-CONTEXT.md) used as requirement IDs — no REQUIREMENTS.md entries (visual overhaul, no new capabilities).
**Plans:** 9/9 plans complete

Plans (delivery order A->E; Wave 1 Foundation is a hard prerequisite for Wave 2):

**Wave 1** *(Foundation — Slice A, parallel; disjoint files)*

- [x] 12-01-PLAN.md — Fonts (Barlow Condensed) + @theme button tokens + --cockpit-* + .stat-num split (D-5, D-8, D-1)
- [x] 12-02-PLAN.md — [tdd] Consolidate zone map into lib/zones.ts + re-export shim + drift-guard smoke test (D-8, D-7)
- [x] 12-03-PLAN.md — Shared PromptChip extract + shadcn card add + delete dead SessionStepList (D-8, D-12)

**Wave 2** *(Slices B-E, parallel; disjoint files, all depend on Wave 1)*

- [x] 12-04-PLAN.md — Ride cockpit rebuild: dark surface, watts-hero, no-FTP RPE hero, profile rail, achieve CTA (D-1, D-2, D-3, D-4, D-7, D-11)
- [x] 12-05-PLAN.md — Today hub: SessionCard stat tiles + Start ride/Export .zwo rename (+test) + TodayScreen mini-bars (D-6, D-7, D-8)
- [x] 12-06-PLAN.md — Progress + Agenda: WeeklyLoadChart two-tone, RideRow paired bars, Agenda mini-bars (D-9, D-8, D-7)
- [x] 12-07-PLAN.md — Shell chrome: 28px display titles + date eyebrow, filled-pill navs, sidebar brand mark (D-10, D-8)
- [x] 12-08-PLAN.md — Secondary surfaces: Settings card redesign + smoke test, ZoneChip + Onboarding/Chat migration (D-12, D-8)

**Gap Closure** *(from 12-UAT.md Test 4 — major: Settings cards render transparent with near-black borders)*

- [x] 12-09-PLAN.md — Add missing --color-card / --color-card-foreground @theme tokens + explicit border-border on the Card primitive so SettingsScreen cards resolve to white --color-surface fills with light --color-line borders (D-8, D-12)

### Phase 13: Close gap: ADAPT-04/TRANSP-03 — wire weekly adaptation check + adaptation log UI

**Goal:** The two integration gaps found in the v1.0 milestone audit are closed: a client-initiated weekly adaptation check fires once per 7 days from AppLayout (giving ADAPT-04's `POST /adaptations/check` its first real caller, fire-and-forget, retried on failure), and a readable "Adaptations" log section on ProgressScreen renders past adaptation decisions (giving TRANSP-03's `getAdaptations()` its first UI consumer). Frontend-only wiring for already-built, already-tested backend behavior; also fixes the stale `Adaptation` TypeScript interface so the log renders real schema fields.
**Requirements**: ADAPT-04, TRANSP-03
**Depends on:** Phase 12
**Plans:** 4 plans

Plans:
**Wave 1** *(foundation + docs, parallel — disjoint files)*

- [ ] 13-01-PLAN.md — Fix `Adaptation` interface to real schema + `checkAdaptations()` (api.ts) + `triggerLabel`/`formatDate` (format.ts, extracted from RideRow) + format.test.ts (ADAPT-04, TRANSP-03)
- [ ] 13-04-PLAN.md — Docs: correct REQUIREMENTS.md traceability (ADAPT-04/TRANSP-03 → Phase 13) + finalize ROADMAP Phase 13 fields (ADAPT-04, TRANSP-03)

**Wave 2** *(feature slices, parallel; disjoint files, both depend on 13-01)*

- [ ] 13-02-PLAN.md — [tdd] `useAdaptationCheck` hook (7-day throttle, D-05 silent-failure) + AppLayout wiring + useAdaptationCheck.test.ts (ADAPT-04)
- [ ] 13-03-PLAN.md — Adaptations log section in ProgressScreen (humanized trigger + explanation_text + date, empty/error/loading states) + progress.test.tsx (TRANSP-03)
