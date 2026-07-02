---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 04
current_phase_name: ui-and-calendar
status: executing
stopped_at: context exhaustion at 75% (2026-06-28)
last_updated: "2026-07-02T20:28:10.079Z"
last_activity: 2026-07-02
last_activity_desc: Quick task 260702-tth — fixed /api/health routing regression; SPA root still 404 pending follow-up
progress:
  total_phases: 5
  completed_phases: 5
  total_plans: 42
  completed_plans: 42
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-21)

**Core value:** A beginner with no FTP and no history completes an interview and immediately receives a safe, structured cycling plan with explicit targets — that plan adapts automatically as real ride data arrives.
**Current focus:** Phase 04 — ui-and-calendar

## Current Position

Phase: 04 (ui-and-calendar) — EXECUTING
Plan: 1 of 21
Status: Executing Phase 04
Last activity: 2026-06-21 — Phase 04 execution started

Progress: [████████████████████] 32/32 plans (100%)

## Performance Metrics

**Velocity:**

- Total plans completed: 27
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 02 | 6 | - | - |
| 03 | 5 | - | - |
| 04 | 11 | - | - |
| 05 | 5 | - | - |

**Recent Trend:**

- Last 5 plans: -
- Trend: -

*Updated after each plan completion*
| Phase 01 P03 | 2 | 1 tasks | 4 files |
| Phase 01 P04 | 2min | 1 tasks | 7 files |
| Phase 01 P05 | 2min | 4 tasks | 6 files |
| Phase 02 P01 | 3min | 3 tasks | 8 files |
| Phase 02 P02 | 4min | 2 tasks | 2 files |
| Phase 02 P04 | 5 | 2 tasks | 5 files |
| Phase 02 P05 | 4 | 1 tasks | 1 files |
| Phase 02 P06 | 3 | 1 tasks | 3 files |
| Phase 03 P01 | 5min | 2 tasks | 1 files |
| Phase 03 P02 | 7min | 3 tasks | 11 files |
| Phase 03 P03 | 6min | 3 tasks | 6 files |
| Phase 03 P04 | 8min | 2 tasks | 3 files |
| Phase 03 P05 | 5min | 2 tasks | 4 files |
| Phase 04 P09 | 15min | 5 tasks | 4 files |
| Phase 04 P10 | 3min | 2 tasks | 3 files |
| Phase 05 P01 | 2min | 2 tasks | 3 files |
| Phase 05 P02 | 8min | 2 tasks | 7 files |
| Phase 05 P03 | 4min | 3 tasks | 5 files |
| Phase 05 P04 | 3min | 3 tasks | 5 files |
| Phase 05 P05 | 1min | 2 tasks | 0 files |
| Phase 04 P14 | 2min | 3 tasks | 3 files |
| Phase 04 P12 | 2min | 2 tasks | 2 files |
| Phase 04 P16 | 8min | 2 tasks | 3 files |
| Phase 04 P15 | 1min | 2 tasks | 11 files |
| Phase 04 P13 | 1min | 1 tasks | 1 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Project init]: Sports-science tool library built first as trust anchor; all other phases depend on verified calculations
- [Project init]: FastAPI over Node backend for FIT parsing and sports-science maths (fitdecode, numpy/scipy)
- [Project init]: Supabase for managed Postgres with auth, storage, and real-time
- [Project init]: Passive FTP estimation only; no forced ramp or 20-min test for cold-start users
- [Project init]: Raw `anthropic` SDK, not `claude-agent-sdk`; agent SDK executes tools autonomously, violating trust model
- [Phase ?]: metrics.py and pmc.py implemented test-first
- [Phase ?]: cold-start guard in update_pmc
- [Phase ?]: Confidence threshold at 12 maps to high: n<12=medium, n>=12=high (D-03 boundary clarification)
- [Phase ?]: FTP equals CP directly in 2-param Morton CP model
- [Phase ?]: 01-05
- [Phase ?]: 01-05
- [Phase ?]: 01-05
- [Phase ?]: 01-05
- [Phase ?]: Manual Anthropic tool schema dicts; TRUST-02 invariant asserted at import
- [Phase ?]: dispatch_tool: iscoroutinefunction branch; never raises out (D-14)
- [Phase ?]: Trust scanner injected; violating assistant message not appended (Pitfall 5)
- [Phase ?]: _MockStream class for async iteration
- [Phase ?]: Token emission post-scan
- [Phase ?]: get_final_message on AsyncMessageStream (entered stream), not AsyncMessageStreamManager; two-stage SDK stream pattern confirmed from installed package
- [Phase ?]: SDK contract gate installed: RESEARCH.md A1/A2/Open Question 1 converted from LOW/ASSUMED to VERIFIED offline assertions in test_sdk_contract.py
- [Phase ?]: Migration applied via supabase db push --linked (non-interactive with --yes flag)
- [Phase ?]: sse_generator _run_turn param
- [Phase ?]: Pydantic model for JSON body
- [Phase ?]: Use Pydantic body model instead of raw Body(str) for JSON object bodies
- [Phase ?]: detect_signals underperformance threshold comes from tool compliance_pct not a hardcoded literal
- [Phase ?]: CAL-03 partial: consent screen In production; Google verification submission is operational task
- [Phase ?]: compliance_pct reads tss_target/type matching _SESSION_COLUMNS; training_sessions table ref removed
- [Phase ?]: onboarding SSE multi-turn: capture create_conversation return, load prior turns via load_conversation, no new sse_generator param
- [Phase ?]: Playwright LIFO: specific route handlers registered after general ones to win the match
- [Phase ?]: Real-device verification required
- [Phase ?]: getSession() seeds auth store on mount; onAuthStateChange ignores transient null except SIGNED_OUT (04-14 auth redirect fix)
- [Phase ?]: 04-12
- [Phase ?]: 04-12
- [Phase ?]: timestamp-based FIT duration (last_record_ts - first_record_ts + 1); fallback to sample count for legacy files
- [Phase ?]: uploadRide surfaces backend detail.detail string on error; falls back to bare status code
- [Phase ?]: 04-13: chat_stream reads message param, appends to history, persists turns via save_messages + assistant_sink (UAT GAP 5 closed)

### Pending Todos

None yet.

### Blockers/Concerns

- Production SPA down: https://www.pacer.moorelabs.uk/ returns 404. Root cause: Vercel Project Framework Preset is `fastapi`, which routes all non-exact-static-match requests to the Python function regardless of vercel.json rewrites. `/api/health` is fixed (200). Fix requires either FastAPI serving `frontend/dist` directly with an SPA-fallback route (recommended — keeps working preset), trimming the Python function bundle so a non-fastapi preset stays under Vercel's 500MB limit, or splitting into two Vercel projects. Blocks the pending production E2E test.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260702-tth | Fix broken production Vercel routing (partial — /api/health fixed, / still 404, see blockers) | 2026-07-02 | 54c899b | [260702-tth-fix-broken-production-vercel-routing-rev](./quick/260702-tth-fix-broken-production-vercel-routing-rev/) |

## Deferred Items

- Telegram bot (Phase 2 post-MVP): reuses agent layer via webhook
- Full three-line CTL/ATL/TSB PMC chart (Phase 2): shown only after 28+ days of data
- Dark mode (Phase 2): light mode only for MVP
- Web Bluetooth live power echo (Phase 2): Chromium-only, conflicts with Zwift trainer control

## Session Continuity

**Stopped at:** context exhaustion at 75% (2026-06-28)
**Resume file:** None

Last session: 2026-06-28T21:10:49.059Z
Next action: `/gsd-complete-milestone v1.0`
