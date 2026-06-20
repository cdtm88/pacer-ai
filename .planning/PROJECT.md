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

- Sports-science tool library: calculate_power_zones, calculate_hr_zones, estimate_ftp_from_rides, compute_tss, update_pmc, progress_load, validate_session_vs_actual — Validated in Phase 01 (64 tests)
- Agent trust-model enforcement: all physiological numbers traceable to tool-library calls — Validated in Phase 02 (trust scanner, attribution, corpus proof)
- Runtime capability-gap logging when a needed calculation has no tool — Validated in Phase 02 (handle_violation + async Supabase write)

### Active

- [ ] Conversational LLM-led onboarding interview producing a persisted user profile
- [ ] Cold-start handling: sessions prescribed by RPE/HR with no FTP; FTP estimated passively from ride data
- [ ] Structured, periodised plan generation (aerobic-base emphasis, back-protective constraints)
- [ ] Sports-science tool library: calculate_power_zones, calculate_hr_zones, estimate_ftp_from_rides, compute_tss, update_pmc, progress_load, validate_session_vs_actual
- [ ] Agent trust-model enforcement: all physiological numbers traceable to tool-library calls
- [ ] Runtime capability-gap logging when a needed calculation has no tool
- [ ] Manual .FIT file ingestion: parse power/HR/cadence/duration, compute TSS/IF/NP, update PMC
- [ ] Adaptive re-planning based on missed sessions, holidays, actual performance, and training load
- [ ] Adaptation transparency: agent explains every re-plan in chat with data and principle cited; changes logged
- [ ] Google Calendar integration: push and sync planned sessions as calendar events
- [ ] ZWO export: export structured session as valid .zwo file for Zwift import
- [ ] Web UI: onboarding, Today/Home, Agenda, History, During-session, Chat screens; mobile bottom tabs / desktop sidebar

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
- **Tech Stack**: React + Vite + Tailwind (frontend), Python FastAPI (backend), Anthropic API with native tool use, Postgres/Supabase, fitparse/fitdecode for FIT parsing, Vercel (frontend) + Railway (API/DB)
- **PWA**: Web-first, mobile-responsive; During-session view must work on iOS Safari
- **Light mode only**: No pure blacks anywhere for MVP; design system from PRD applies
- **No em dashes**: In any generated content or copy — use commas, semicolons, colons, or separate sentences
- **Calendar**: Google Calendar API (OAuth2) for push/sync

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Sports-science tool library built first | Trust anchor — all other phases depend on verified calculations | — Pending |
| FastAPI over Node backend | Eases FIT parsing (fitparse) and sports-science maths (numpy/scipy) | — Pending |
| Supabase for Postgres | Managed Postgres with auth, storage, and real-time; simplifies hosting | — Pending |
| Passive FTP estimation, no forced test | Cold-start reality: beginner cannot do a 20-min test; CP modelling from ride data | — Pending |
| LLM capability-gap log is a runtime artefact | Distinct from GSD build planning; application logs gaps it cannot compute | — Pending |

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
*Last updated: 2026-06-20 — Phase 02 (agent-core) complete: FastAPI backend, agent loop, tool registry, SSE streaming, trust enforcement all shipped and verified (159 tests)*
