# PacerAI

## What This Is

PacerAI is an evidence-based, adaptive AI cycling coach for a beginner returning to fitness (general fitness and weight loss; no event or competition). It interviews the user from zero knowledge, builds a structured training plan, and re-plans intelligently as real ride data arrives as .FIT files. Web-first, mobile-responsive PWA with an in-app chat interface.

## Core Value

A new user with no FTP and no fitness history can complete an interview and immediately receive a safe, structured, periodised cycling plan with explicit per-session targets — and that plan adapts automatically as real ride data arrives.

## Non-Negotiable Architecture (Trust Model)

The LLM owns judgement; a validated tool library owns numbers.

- Every physiological figure (training zones, TSS, IF, NP, FTP estimates, CTL/ATL/TSB, load-progression targets) must come from a deterministic, unit-tested function in the sports-science tool library. That function also returns the named methodology it used.
- The LLM is forbidden from emitting any such number from its own reasoning. If a needed calculation has no tool, the agent logs a structured capability-gap entry, tells the user in chat, and falls back gracefully — never fabricating a number.
- Any code path where the model could place a self-derived physiological number into a plan is a defect, regardless of how plausible it looks.

## Business Context

- **Customer**: Individual beginner cyclist (single-user, personal tool for now)
- **Revenue model**: None for MVP — personal project
- **Success metric**: User completes interview → receives plan → uploads first .FIT → plan adapts
- **Strategy notes**: Phase 2 Telegram bot reuses the agent layer as the top priority post-MVP

## Requirements

### Validated

- Sports-science tool library: calculate_power_zones, calculate_hr_zones, estimate_ftp_from_rides, compute_tss, update_pmc, progress_load, validate_session_vs_actual — Phase 01 (64 tests)
- Agent trust-model enforcement: all physiological numbers traceable to tool-library calls — Phase 02 (trust scanner, attribution, corpus proof)
- Runtime capability-gap logging when a needed calculation has no tool — Phase 02 (handle_violation + async Supabase write)
- Conversational LLM-led onboarding interview producing a persisted user profile — Phase 03
- Cold-start handling: sessions prescribed by RPE/HR with no FTP; FTP estimated passively from ride data — Phase 03
- Structured, periodised plan generation (aerobic-base emphasis, back-protective constraints) — Phase 03
- Manual .FIT file ingestion: parse power/HR/cadence/duration, compute TSS/IF/NP, update PMC — Phase 03 (Zwift .FIT acceptance test)
- Adaptive re-planning based on missed sessions, holidays, actual performance, and training load — Phase 03 (micro/macro distinction, 30% guard)
- Adaptation transparency: agent explains every re-plan in chat with data and principle cited; changes logged — Phase 03
- Web UI: onboarding, Today/Home, Agenda, History, Chat screens and during-session scaffold; mobile bottom tabs / desktop sidebar — Phase 04
- ZWO export: export structured session as valid .zwo file for Zwift import — Phase 05 (Zwift acceptance test passed)
- During-session stepper: iOS-safe timer with wake lock, auto-advance, free-ride path — Phase 05 (IOS-03 kill-to-root fix committed; physical device retest pending)
- Ride Analysis Dashboard: per-second power/HR/cadence/speed/elevation charts with lap markers, synced hover readout, and server-computed time-in-HR-zone breakdown, served parse-on-demand via `GET /api/rides/{id}/stream` (no persistence, no migration); channels render only when present — Phase 11 (21/21 must-haves verified; 359 backend + 140 frontend tests green; human-verified via live browser walkthrough)
- Athletic visual redesign (Zwift/Strava register): dark cockpit DuringSessionScreen with watt-hero and session profile rail, display-face hero numerals, Today hub with stat tiles and fat Start CTA, zone-color identity everywhere, unified button/token/zone-map component system across all screens — Phase 12 (12/12 must-haves verified; 149 frontend + 359 backend tests green; live UAT found and closed a Settings-card token gap via gap-closure plan 12-09, re-verified against compiled CSS output)

### Active

None. All v1.0 requirements shipped.

### Out of Scope

- Strava integration — explicitly out of scope, not on roadmap
- Social, sharing, or community features — not on roadmap
- Garmin/Zwift direct auto-pull — manual .FIT upload only
- Telegram bot (Phase 2 — top priority post-MVP, not v1)
- Web Bluetooth live power echo (Phase 2 — Chromium-only, conflicts with Zwift trainer control)
- Dark mode (Phase 2 — light mode only for MVP)
- Full three-line CTL/ATL/TSB PMC screen (Phase 2)

## Context

- Primary user: beginner cyclist returning to fitness; goals are general fitness and weight loss; no event or competition. System starts with zero knowledge.
- Hardware: Wahoo Kickr Core 2 smart trainer plus Zwift — real power data from day one.
- Cold-start reality: no FTP, cannot do a 20-min or ramp test yet. This is a first-class supported case.
- Injury/back status established through interview, never assumed. Back-protective constraints apply when flagged: cap initial volume, avoid prolonged standing and sprint efforts early, flag load ramping too fast.
- Methodology sources: Coggan/Allen power zones, TrainingPeaks PMC (Banister), ACSM training-load guidance, Seiler polarized-training research.

## Constraints

- **Architecture**: LLM never emits physiological numbers directly — tool library is the only authoritative source for all sports-science calculations. Enforced at code level, verifiable in logs.
- **Tech Stack**: React + Vite + Tailwind (frontend), Python FastAPI (backend), Anthropic API with native tool use, Postgres/Supabase, fitdecode for FIT parsing, Vercel (frontend + backend, sole deploy target since Phase 07)
- **PWA**: Web-first, mobile-responsive; During-session view must work on iOS Safari
- **Light mode only**: No pure blacks anywhere for MVP; design system from PRD applies
- **No em dashes**: In any generated content or copy — use commas, semicolons, colons, or separate sentences

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Sports-science tool library built first | Trust anchor; all other phases depend on verified calculations | Validated Phase 01: 64 unit tests, zero downstream defects traced to bad calculations |
| FastAPI over Node backend | Eases FIT parsing (fitdecode) and sports-science maths (numpy/scipy) | Validated Phase 03: fitdecode pipeline and PMC calculations all Python-native, no cross-process friction |
| Supabase for Postgres | Managed Postgres with auth, storage, and real-time; simplifies hosting | Validated Phase 01: schema migrations, JWT auth, and storage all used without issue |
| Passive FTP estimation, no forced test | Cold-start reality: beginner cannot do a 20-min test; CP modelling from ride data | Validated Phase 03: RPE/HR sessions for cold-start, FTP estimate emerges after 4+ quality efforts |
| LLM capability-gap log is a runtime artefact | Distinct from GSD build planning; application logs gaps it cannot compute | Validated Phase 02: log entries appear in capability_gaps table; trust scanner intercepts violations before frontend |
| Raw anthropic SDK, not claude-agent-sdk | Agent SDK executes tools autonomously, violating trust model | Validated Phase 02: tool dispatch is explicitly controlled; LLM cannot self-execute physiological calculations |
| ZWO generated server-side only | Frontend must never build XML with unsourced power fractions | Validated Phase 05: POWER_BY_SEGMENT constants are the only source; LLM never touches power values |
| Date.now() delta timer, not tick counter | visibilitychange on iOS resets the interval; only wall-clock diff survives backgrounding | Phase 05: IOS-03 kill-to-root fix committed; physical device retest pending |
| Vercel as sole deploy target, Railway abandoned | Dual-target maintenance cost and vercel.json/api routing conflict outweighed any benefit; Vercel's `services` model natively supports the Python+static split | Validated Phase 07: vercel.json restructured, BackgroundTasks moved to inline-await (Vercel freezes functions post-response), live preview verified (routing, SSE, env parity), Railway service decommissioned |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? Move to Out of Scope with reason
2. Requirements validated? Move to Validated with phase reference
3. New requirements emerged? Add to Active
4. Decisions to log? Add to Key Decisions
5. "What This Is" still accurate? Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-07-10. Phase 12 (Athletic Redesign) complete: closed the final gap-closure plan (12-09) fixing SettingsScreen's shadcn Card sections, which rendered with a transparent background and a near-black border because `index.css` never defined `--color-card`/`--color-card-foreground`. Re-verification traced the fix through the actual compiled production CSS (not just source), confirming the full token chain resolves to a white surface with a light hairline border. Full regression suite green (149 frontend + 359 backend). This was the last phase on the v1.0 roadmap — the physical-device iOS wake-lock/safe-area check (IOS-03) remains a standing, explicitly non-blocking follow-up. Prior update: Phase 11 (Ride Analysis Dashboard) complete: added a parse-on-demand `GET /api/rides/{id}/stream` endpoint (sibling FIT parser, no persistence/migration), a `time_in_hr_zones` sports-science tool reusing `calculate_hr_zones` (TRUST-01), and a new Analysis tab/screen with per-channel Recharts visualisation, cross-chart hover sync, lap markers, and a time-in-zone breakdown. All 7 plans executed test-first where applicable (TDD gate: 0 violations across 3 TDD plans); phase verification scored 21/21 must-haves; human-verify checkpoint resolved via a genuine live-browser walkthrough (mocked auth/API against the real response contract), not an auto-approval. Prior update: Phase 3 (Coaching Loop) gap closure complete (plan 03-06): fixed a live-reproduced data-integrity BLOCKER (CR-01) where `_resolve_all_scheduled_dates` failed to de-collide session dates whenever a user's `preferred_days` count didn't evenly divide their weekly session count (an ordinary onboarding answer), silently breaking ride-to-session matching and missed-session detection; also fixed a chat-transparency reliability gap (WR-06) where the SSE generator could persist partial assistant text as complete on abnormal turn termination. Phase 3 re-verified 23/23 must-haves (up from 22/23). Prior update: Phase 8 (Trust Model Integrity) complete: audit log persisted, tool-input laundering closed (dispatch_tool server-injection, extended post-review to hr_zones/lthr_estimate), attribution rewritten to numeric-tolerance matching, cross-turn seeding via audit_log, HR zones corrected to true Coggan/Allen, generate_plan wired to current_ctl/load_targets/preferred_days. Live UAT caught and fixed a real gap: onboarding's direct-LTHR branch was rejecting the user's own self-reported number as unattributed — fixed via a new self-reported-values channel in the trust scanner (plan 08-08), verified live against the real backend + model.*

