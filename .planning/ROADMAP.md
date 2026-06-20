# Roadmap: PacerAI

## Overview

PacerAI builds trust outward from a single anchor: a deterministic, unit-tested sports-science tool library. No downstream layer can be credible until that anchor is verified. From there, the agent wiring proves the trust model holds under real LLM calls. Then the coaching loop assembles around real ride data. Then the UI is built on working endpoints. Finally, the iOS-specific during-session view and ZWO export ship as a self-contained integration layer.

## Phases

**Phase Numbering:**

- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Sports-Science Foundation** - Tool library, DB schema, and Supabase setup — the trust anchor everything else depends on (completed 2026-06-19)
- [ ] **Phase 2: Agent Core** - Agent loop, tool registry, SSE streaming, and trust-model enforcement proven end-to-end
- [ ] **Phase 3: Coaching Loop** - FIT ingestion, plan generation, onboarding interview, and adaptive re-planning
- [ ] **Phase 4: UI and Calendar** - React PWA, all screens, Google Calendar integration, Vercel deployment
- [ ] **Phase 5: During-Session and ZWO Export** - iOS-safe session stepper with wake lock, ZWO file generator with Zwift acceptance test

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

**Plans**: 5/6 plans executed

Plans:

- [x] 02-01-PLAN.md — Wave 1: backend deps (no claude-agent-sdk), agent/ + api/ scaffolding, async capability_gap upgrade
- [x] 02-02-PLAN.md — Wave 2: tool registry + dispatcher and the raw-SDK agent loop (dedup, parallel gather, retry, audit)
- [x] 02-03-PLAN.md — Wave 3: trust-model response scanner and FastAPI SSE chat endpoint
- [x] 02-04-PLAN.md — Wave 4: tests/agent/ compliance suite proving AGENT-01..06 and TRUST-03/04/05
- [x] 02-05-PLAN.md — Wave 5: offline anthropic SDK contract-conformance test (closes A1/A2/Open Question 1 — loop's assumed SDK shape verified against the real installed package)
- [ ] 02-06-PLAN.md — Wave 5: trust scanner representative-corpus characterization (Success Criterion 5; zero false-negative/false-positive rates; answers Open Question 2)

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

**Plans**: TBD
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

**Plans**: TBD
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

**Plans**: TBD
**UI hint**: yes

## Progress Table

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Sports-Science Foundation | 5/5 | Complete   | 2026-06-19 |
| 2. Agent Core | 5/6 | In Progress|  |
| 3. Coaching Loop | 0/0 | Not started | - |
| 4. UI and Calendar | 0/0 | Not started | - |
| 5. During-Session and ZWO Export | 0/0 | Not started | - |
