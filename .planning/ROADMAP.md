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
- [ ] **Phase 6: Core Loop Persistence** - Persist generated plans as sessions rows, fix FTP/PMC correctness, link rides to sessions, idempotent adaptations
- [ ] **Phase 7: Deploy Consolidation** - Vercel is the sole deploy target: remove Railway artifacts, make SSE and background FIT processing serverless-safe, resolve config conflicts, env docs, DB indexes
- [ ] **Phase 8: Trust Model Integrity** - Persist audit log, scan tool inputs, tighten attribution, collect LTHR, correct HR zones and load constraints
- [ ] **Phase 9: Frontend Resilience** - Chat SSE recovery and history reload, session persistence staleness, iOS export/auth fixes, contract mismatches, error boundary
- [ ] **Phase 10: Hygiene and Safety Nets** - Repair stale tests, contract tests, SSE token exchange, rate limiting, CI, repo cleanup

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

**Plans**: 5/5 plans complete
**Wave 1**

- [x] 01-01-PLAN.md — Wave 0: test infra, deps, venv, Supabase CLI, ToolResult contract + constants
- [x] 01-02-PLAN.md — Wave 1: power and HR zones (TOOL-01, TOOL-02)
- [x] 01-03-PLAN.md — Wave 1: TSS/NP/IF metrics and Banister PMC (TOOL-04, TOOL-05)
- [x] 01-04-PLAN.md — Wave 1: FTP CP model, load progression, compliance (TOOL-03, TOOL-06, TOOL-07)

**Wave 2** *(blocked on Wave 1 completion)*

- [x] 01-05-PLAN.md — Wave 2: Supabase schema + db push, log_capability_gap, package exports (TOOL-08, GAP-01/02/03, TRUST-02)

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

**Plans**: 5/5 plans complete

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
**Plans:** 4/5 plans executed

Plans:
**Wave 1** *(schema foundation, blocking)*

- [x] 06-01-PLAN.md — Migration 0005 (pmc_history tss/days_of_data, sessions 'missed', profiles ftp/lthr, rides content_hash+UNIQUE, adaptations trigger_session_ids/status) + [BLOCKING] supabase db push

**Wave 2** *(parallel, depend on 06-01)*

- [x] 06-02-PLAN.md — Plan persistence: dispatch_tool generate_plan hook writes plans+sessions rows, rewrites plan_id; save_profile lthr write-back
- [x] 06-03-PLAN.md — PMC recompute-from-scratch day-series module (gap-day decay, same-day sum, calendar days_of_data)
- [x] 06-04-PLAN.md — Adaptation idempotency (trigger_session_ids + missed status flip), live 30% shift guard, POST /adaptations/{id}/confirm, compliance None-guard

**Wave 3** *(depends on 06-01 + 06-03)*

- [ ] 06-05-PLAN.md — Rides pipeline: FTP key fix + profiles.ftp write-back, content-hash dedup, ride-session link, inline-await (Vercel), recompute_pmc_for_user

### Phase 7: Deploy Consolidation

**Goal:** Vercel is the sole, fully working deploy target (decision 2026-07-03: Railway abandoned). Remove Railway artifacts (Dockerfile, railway.toml, Railway references in README/CLAUDE.md); resolve the conflicting root vs frontend `vercel.json` so `/api/*` reliably reaches the Python function and the SPA is served as static build (drop the api/index.py frontend/dist fallback); make the serverless path correct: SSE streaming on `/chat/stream` and `/onboarding/*` verified within Vercel function limits, and all post-response BackgroundTasks work (ride TSS/PMC pipeline, calendar pushes, adaptation sync) moved inline-awaited or to a durable mechanism since Vercel freezes functions after the response; README env-var table corrected and completed (SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, CALENDAR_FERNET_KEY, BACKEND_BASE_URL, ANTHROPIC_MODEL) with Vercel env setup documented; indexes added on all user_id/FK columns; `fits` storage bucket provisioned as config.
**Requirements**: TBD
**Depends on:** Phase 6
**Plans:** 0 plans

Plans:

- [ ] TBD (run /gsd-plan-phase 7 to break down)

### Phase 8: Trust Model Integrity

**Goal:** The trust model is airtight and verifiable: audit log persisted per turn (TRUST-04), tool inputs scanned so invented numbers cannot launder through tool calls, bare-number attribution uses word-boundary and tolerance matching instead of substring, prior-turn numbers seeded to kill cross-turn false positives, LTHR (or explicit RPE-only fallback) collected in onboarding, HR zone constants match the claimed Coggan methodology, Zone 2 targets safe for a returning beginner, and generate_plan consumes current_ctl/load_targets/preferred_days so back-protective caps actually constrain sessions.
**Requirements**: TBD
**Depends on:** Phase 7
**Plans:** 0 plans

Plans:

- [ ] TBD (run /gsd-plan-phase 8 to break down)

### Phase 9: Frontend Resilience

**Goal:** The UI survives real-world failure modes: chat recovers from SSE errors and empty tool-only turns (no more bricked input), conversation history reloads instead of creating new conversations, persisted sessions carry id+date so stale records cannot hijack Today or mark the wrong session done, iOS ZWO export works within the user-gesture window, auth callback no longer double-exchanges the code, Ride/Profile field names match the backend, upload invalidates PMC/session queries, and a router error boundary replaces white-screen crashes.
**Requirements**: TBD
**Depends on:** Phase 8
**Plans:** 0 plans

Plans:

- [ ] TBD (run /gsd-plan-phase 9 to break down)

### Phase 10: Hygiene and Safety Nets

**Goal:** The test suite is green and guards the seams: 8 stale SSE tests authenticate properly, capability-gap test-order leak fixed, Playwright mocks match real response shapes, frontend-backend contract tests added (would have caught the Ride/Profile/FTP-key mismatches), short-lived SSE token exchange removes JWTs from query strings, LLM endpoints rate-limited, CI runs pytest+vitest+ruff, repo cleaned (root node_modules, test-ride.fit, root .gitignore).
**Requirements**: TBD
**Depends on:** Phase 9
**Plans:** 0 plans

Plans:

- [ ] TBD (run /gsd-plan-phase 10 to break down)

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Sports-Science Foundation | 5/5 | Complete   | 2026-06-19 |
| 2. Agent Core | 6/6 | Complete    | 2026-06-20 |
| 3. Coaching Loop | 5/5 | Complete    | 2026-06-20 |
| 4. UI and Calendar | 21/21 | Complete   | 2026-06-21 |
| 5. During-Session and ZWO Export | 5/5 | Complete    | 2026-06-21 |
| 6. Core Loop Persistence | 4/5 | In Progress|  |
| 7. Deploy Consolidation | 0/? | Not planned | - |
| 8. Trust Model Integrity | 0/? | Not planned | - |
| 9. Frontend Resilience | 0/? | Not planned | - |
| 10. Hygiene and Safety Nets | 0/? | Not planned | - |
