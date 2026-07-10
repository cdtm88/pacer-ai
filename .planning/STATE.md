---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 12
status: executing
stopped_at: Phase 11 UI-SPEC approved
last_updated: "2026-07-10T15:31:50.551Z"
last_activity: 2026-07-10
last_activity_desc: Phase 12 complete
progress:
  total_phases: 12
  completed_phases: 12
  total_plans: 90
  completed_plans: 90
  percent: 100
current_phase_name: athletic-redesign
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-06-21)

**Core value:** A beginner with no FTP and no history completes an interview and immediately receives a safe, structured cycling plan with explicit targets — that plan adapts automatically as real ride data arrives.
**Current focus:** Phase 12 — athletic-redesign

## Current Position

Phase: 12
Plan: Not started
Status: Executing Phase 12
Last activity: 2026-07-10 — Phase 12 complete

Progress: [████████████████████] 32/32 plans (100%)

## Performance Metrics

**Velocity:**

- Total plans completed: 80
- Average duration: -
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 02 | 6 | - | - |
| 03 | 6 | - | - |
| 04 | 11 | - | - |
| 05 | 5 | - | - |
| 6 | 5 | - | - |
| 07 | 4 | - | - |
| 8 | 8 | - | - |
| 01 | 6 | - | - |
| 09 | 7 | - | - |
| 10 | 6 | - | - |
| 11 | 7 | - | - |
| 12 | 9 | - | - |

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

### Roadmap Evolution

- Phases 6-10 added 2026-07-03 from full app review (4 parallel review agents; findings in .planning/research/APP-REVIEW-260703.md):
  - Phase 6: Core Loop Persistence (plans/sessions never persisted, FTP key mismatch, PMC date/gap/dedup)
  - Phase 7: Deploy Consolidation (DECISION 2026-07-03: Vercel sole target, Railway abandoned; delete Dockerfile/railway.toml, fix serverless BackgroundTasks + SSE, vercel.json conflicts)
  - Phase 8: Trust Model Integrity (audit log dropped, tool inputs unscanned, LTHR never collected)
  - Phase 9: Frontend Resilience (chat SSE brick, stale session hijack, iOS export, contract mismatches)
  - Phase 10: Hygiene and Safety Nets (stale tests, contract tests, token exchange, rate limit, CI)
- Phase 11 (later renumbered to Phase 12) added 2026-07-07: Google Calendar Production Verification — formalizes the CAL-03b gap left open in 04-VERIFICATION.md (Google OAuth consent screen still in Testing mode). Deferred from Phase 4, re-confirmed deferred in Phase 7 pending a live backend URL (now satisfied by the Vercel deploy); no privacy policy/ToS page exists yet, so the Google verification submission has not started.
- Phase 11 inserted 2026-07-09 as Ride Analysis Dashboard (from author PRD `docs/phase-11-ride-analysis-roadmap.html`; context seeded in `.planning/phases/11-ride-analysis-dashboard/11-CONTEXT.md`). Google Calendar Production Verification renumbered 11 → 12 (was unplanned, empty dir, so the renumber was clean). Ride Analysis takes slot 11 to keep the PRD's `11-*` plan/decision/threat IDs consistent. Delivers the deferred ride-analysis viz work noted in project-ui-followups (per-ride power/HR trace + zone distribution), now via a parse-on-demand `GET /api/rides/{id}/stream`. Two fixtures placed in `tests/fixtures/` (zwift_ride_30min.fit, hilly_ride_30min.fit).
- Google Calendar integration removed entirely 2026-07-09 (quick task 260709-pxu): no longer a requirement. Deleted backend calendar_sync.py + routes/calendar.py + the /calendar router, the /onboarding/plan-calendar-sync endpoint, and all adaptations.py calendar-sync blocks + calendar_event_id selects; removed the frontend CalendarStatus + Settings section + api.ts fetchers; dropped the google-*/cryptography deps; scrubbed CAL-01..04 from REQUIREMENTS, the Phase 12 gcal entry from ROADMAP, and Google Calendar from CLAUDE.md/PROJECT/README/prd. LEFT AS-IS: applied Supabase migrations (oauth_states table + calendar_event_id column remain, unused; a drop migration is a follow-up), the completed Phase 4 "UI and Calendar" historical record, and .env.example (GOOGLE_*/CALENDAR_FERNET_KEY vars need manual removal, file is permission-protected).
- Phase 13 added 2026-07-10: Close gap: ADAPT-04/TRANSP-03 — wire weekly adaptation check + adaptation log UI. Surfaced by the v1.0 milestone audit (`.planning/v1.0-MILESTONE-AUDIT.md`, status gaps_found): both requirements were marked SATISFIED in 03-VERIFICATION.md/06-VERIFICATION.md on endpoint + unit test alone, but cross-phase integration tracing found `POST /adaptations/check` (ADAPT-04) has no caller anywhere (no cron, no scheduler, no frontend trigger, no lazy in-conversation check) and `getAdaptations()` (TRANSP-03) has no frontend consumer. Reasoning-in-chat (TRANSP-01/02) is unaffected and correctly wired.

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

None yet.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260702-tth | Fix broken production Vercel routing (partial — /api/health fixed, / still 404, see 260702-ulq) | 2026-07-02 | 54c899b | [260702-tth-fix-broken-production-vercel-routing-rev](./quick/260702-tth-fix-broken-production-vercel-routing-rev/) |
| 260702-ulq | Production SPA restored — FastAPI serves frontend/dist directly (StaticFiles + SPA-fallback catch-all) under the retained fastapi Vercel preset; also removed a stale duplicate root index.py that Vercel was silently deploying instead of api/index.py | 2026-07-02 | 3fb1da5 | [260702-ulq-fix-production-spa-404-have-fastapi-serv](./quick/260702-ulq-fix-production-spa-404-have-fastapi-serv/) |
| 260702-v8z | Fixed onboarding chat 405 — OnboardingScreen.tsx referenced unset VITE_API_URL env var (resolved to literal "undefined/onboarding/start"); both SSE POST call sites now use same-origin /api/onboarding/start, found live via Playwright E2E testing | 2026-07-02 | 2a7b196 | [260702-v8z-fix-onboarding-chat-405-in-production-on](./quick/260702-v8z-fix-onboarding-chat-405-in-production-on/) |
| 260702-vj2 | Added public.users auto-provisioning trigger (SECURITY DEFINER, handle_new_user pattern) + backfill for 2 orphaned auth.users rows — fixes silent 409 FK violation on conversations insert that was resetting onboarding to the opening question every turn for new signups; found live via Playwright E2E testing | 2026-07-02 | db81032 | [260702-vj2-add-supabase-trigger-to-auto-provision-p](./quick/260702-vj2-add-supabase-trigger-to-auto-provision-p/) |
| 260702-vs6 | Fixed save_profile PGRST204 — upsert used nonexistent "fitness_goals" column, real column is "goals"; every onboarding profile save was silently failing in production | 2026-07-02 | b619864 | [260702-vs6-fix-save-profile-column-mismatch-profile](./quick/260702-vs6-fix-save-profile-column-mismatch-profile/) |
| 260702-vsp | Fixed trust-scanner Pattern A false positive — number+unit attribution (e.g. "134 bpm") required an exact substring match against tool JSON, which never phrases numbers adjacent to units; added bare-number fallback mirroring Pattern B, with regression + safety negative-control tests. Was blocking every onboarding confirmation with trust_violation/max_retries | 2026-07-02 | e1b6d88 | [260702-vsp-fix-trust-scanner-pattern-a-false-positi](./quick/260702-vsp-fix-trust-scanner-pattern-a-false-positi/) |
| 260702-w52 | Fixed the actual dominant root cause of onboarding trust_violation failures — loop.py's tool_result_values reset every while-loop iteration instead of accumulating across a whole turn, so a later round's summary text could never attribute numbers from an earlier round's tool call. Discovered when 260702-vsp's correct attribution fix still failed live E2E testing | 2026-07-02 | 1773f6a | [260702-w52-fix-loop-py-tool-result-values-resets-ev](./quick/260702-w52-fix-loop-py-tool-result-values-resets-ev/) |
| 260702-wev | Injected authenticated user_id server-side into save_profile/generate_plan tool calls (removed user_id from LLM tool schemas entirely) — the LLM had no way to know the real user UUID and guessed placeholders ("new_user", "user_001", ...) that failed uuid/FK checks on every call, so no onboarding profile had ever been persisted in production. Also fixed the identical latent bug in chat.py's coaching path | 2026-07-02 | b3fcf39 | [260702-wev-inject-authenticated-user-id-server-side](./quick/260702-wev-inject-authenticated-user-id-server-side/) |
| 260709-qw0 | Fixed CI ruff F401 failure — removed two unused imports (get_current_user in backend/routes/onboarding.py, inspect in tests/api/test_adaptations.py) orphaned by the Google Calendar removal (a174e47); ruff check . now exits 0 | 2026-07-09 | a83932d | [260709-qw0-fix-ruff-unused-imports-ci-failure](./quick/260709-qw0-fix-ruff-unused-imports-ci-failure/) |

## Deferred Items

- Telegram bot (Phase 2 post-MVP): reuses agent layer via webhook
- Full three-line CTL/ATL/TSB PMC chart (Phase 2): shown only after 28+ days of data
- Dark mode (Phase 2): light mode only for MVP
- Web Bluetooth live power echo (Phase 2): Chromium-only, conflicts with Zwift trainer control

## Session Continuity

**Stopped at:** Phase 11 UI-SPEC approved
**Resume file:** .planning/phases/11-ride-analysis-dashboard/11-UI-SPEC.md

Last session: 2026-07-09T16:17:21.821Z
Next action: `/gsd-plan-phase 10`
