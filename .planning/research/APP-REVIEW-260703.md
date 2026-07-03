# Full App Review — 2026-07-03

Source: four parallel review agents (sports-science library, backend agent/routes, frontend, config/deploy/schema) plus test-suite runs. Key claims spot-verified in code. This document feeds phase planning for Phases 6-10.

Test status at review time: frontend 79/79 pass; backend 212 pass / 9 fail (8 SSE tests stale, written pre-auth on /chat/stream, now 401; 1 capability-gap test fails only in full run, test-order state leak). June e2e report: 33 Playwright failures, mostly stale mocks (.planning/e2e-test-report.md).

## Phase 6 — Core Loop Persistence

Deploy context (see Phase 7 decision): the app runs on Vercel serverless only. The ride processing pipeline currently runs via FastAPI BackgroundTasks, which Vercel freezes post-response — any Phase 6 rework of process_ride_background should make it inline-awaited (or durable) rather than deepening the BackgroundTasks dependency.

Critical:
- Generated plans never persisted. plan.py:207-215 returns sessions with plan_id None; zero inserts into `sessions` anywhere (grep-verified). Today/Agenda/ZWO/calendar/adaptations read an empty table. Core product loop broken end-to-end.
- FTP key mismatch: rides.py:236 reads `ftp_value.get("ftp_watts", ...)` but estimate_ftp_from_rides returns key `"ftp"` (ftp.py:100). Estimated FTP silently discarded; users stay at 150W placeholder with is_estimated=False.
- PMC: no zero-TSS gap fill (update_pmc is single EWMA step, one step per upload) so CTL/ATL never decay on rest days; dated by date.today() not ride start_time (rides.py:326,368); same-day second upload double-steps decay, double-increments days_of_data, overwrites tss instead of summing (rides.py:286-379); duplicate FIT re-upload creates second ride row (no content-hash dedup, rides.py:505-515).
- Adaptations non-idempotent: missed sessions stay status='planned' after signal consumed, so every POST /adaptations/check re-applies 20% cuts (0.8^n) and +1-day shifts, plus new log row (adaptations.py:140-181,362-373,497-507).
- POST /adaptations/sessions/{id}/missed self-defeats: sets status='missed' but detect_signals only scans status='planned' (adaptations.py:685 vs 116).
- Ride-session link never written: compliance matches "first session today" ignoring status; rides.session_id never set; session never marked completed → later counted missed (rides.py:318-357).
- Schema: sessions.py:328 selects profiles.ftp — no migration creates it; frontend Profile interface expects display_name/ftp/lthr/weight_kg/onboarding_complete/updated_at, none exist.

Major/minor to fold in:
- compliance.py:17 TypeError when actual={"tss": None} (shape produced by short rides).
- Macro replan writes non-atomic (adaptations.py:533-538); log row written after, snapshot can lie.
- Macro shift generator moves all sessions exactly +1 day while 30% guard counts only >1-day moves → guard mathematically dead (adaptations.py:497-510).
- No confirm endpoint for macro replan needs_confirmation (D-19 dead-end).
- ride_debrief conversations inserted (rides.py:399-415) but never read.
- Ride processing failure log-only; ride stuck "processing", no status endpoint (rides.py:420-423).
- plans table dead; adaptations.py selects plan_id that is always null.
- adaptations dual columns duration_mins/duration_minutes hand-synced; one update path already omits one (adaptations.py:370-378).

## Phase 7 — Deploy Consolidation

**DECISION (2026-07-03, user): Vercel is the sole deploy target. Railway is abandoned.** The Railway findings below are resolved by deletion, not repair. Same-origin BASE='' in api.ts is correct for Vercel and stays.

Resolve by removal:
- Dockerfile (broken anyway: CMD targets nonexistent api.main:app, never copies backend/) — delete.
- railway.toml — delete.
- Railway references in README (deploy section, `uvicorn api.main:app` commands) and CLAUDE.md stack table — update to Vercel.
- VITE_API_URL: no longer needed for prod (same-origin). Either remove from docs/vite-env.d.ts or keep as optional local-dev override; pick one and make code+docs agree.

Must fix for Vercel to be correct:
- BackgroundTasks are unreliable on serverless (function frozen post-response): ride TSS/PMC pipeline (rides.py:556), calendar pushes, adaptation calendar sync. Move inline-awaited (acceptable latency for single-user) or to a durable mechanism (Vercel Queues / cron). This is a data-loss class bug on the chosen platform.
- SSE streaming on /chat/stream and /onboarding/*: verify function duration limits and streaming behavior on the deployed Python function (Fluid Compute; default 300s cap). Add keepalive frames.
- Two conflicting vercel.json: root routes /api/* → api/index.py; frontend/vercel.json rewrites everything incl. /api/* to index.html. Determine actual Vercel project root and delete the dead config.
- api/index.py serves SPA from gitignored frontend/dist (503 risk) and duplicates root vercel.json's rewrite — serve the SPA as Vercel static build output instead and strip the fallback.
- README env table: documents SUPABASE_SERVICE_KEY, code requires SUPABASE_SERVICE_ROLE_KEY; missing SUPABASE_JWT_SECRET, CALENDAR_FERNET_KEY, BACKEND_BASE_URL, ANTHROPIC_MODEL. Document Vercel env setup (vercel env).
- Zero CREATE INDEX in migrations; unindexed user_id/FK on sessions, rides, conversations, messages, plans, adaptations, capability_gaps, oauth_states.
- Storage bucket `fits` (rides.py:508) not provisioned as code; fresh env 404s on upload.

Also: requirements.txt mixed pinning, no lockfile (gunicorn can be dropped with Railway); oauth_states no TTL/cleanup; docstrings still say api/main.py etc. (rename evidence); README `ruff check api/` checks nothing; backend/main.py FRONTEND_URL comma-list used raw as redirect base in calendar.py:279,362.

Env inventory (backend): SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_JWT_SECRET, ANTHROPIC_API_KEY, ANTHROPIC_MODEL, FRONTEND_URL, BACKEND_BASE_URL, GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, CALENDAR_FERNET_KEY, PORT. Frontend: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY (+VITE_API_URL once wired).

## Phase 8 — Trust Model Integrity

- Audit log built per request (_sse.py:75) but never persisted — TRUST-04 "verifiable in logs" unverifiable.
- Tool inputs unscanned: LLM supplies target_ctl/ftp_watts/current_ctl/max_hr_or_lthr as inputs; invented numbers laundered through tools come back "attributed".
- Bare-number attribution is substring match against any tool-result JSON (trust.py:127-131,151-156): "250" matches "2500", "0.250", timestamps. Near-bypass once any tool has run.
- Cross-turn false positives: tool_result_values per-HTTP-request (loop.py:85, chat.py:96); model echoing last turn's legit "FTP is 190W" triggers violation → retries → max_retries error.
- Unit gaps in scanner: kJ, W/kg, km/h, "% of FTP", LTHR/NP/IF, spelled-out numbers (trust.py:44); Pattern B FPs on "improve your FTP over 12 weeks".
- LTHR/max HR never collected in onboarding (onboarding.py:63-71) yet D-08 order requires calculate_hr_zones — LLM must invent LTHR.
- HR zone constants are Friel-style (81/90/94/100% LTHR) but methodology string claims Coggan/Allen (Coggan: 68/83/94/105) — constants.py:27-33. plan.py targets Zone 2 at 81-90% LTHR: too hot for returning beginner with back issues.
- generate_plan accepts but ignores current_ctl and load_targets (plan.py:176-205) — D-09 back-protective CTL caps constrain nothing; preferred_days ignored (always Tue/Thu/Sat/Sun).
- CP model fed whole-ride duration+avg power, not mean-max efforts (rides.py:223-231); quality filter dead code (best_ftp_estimate always None, ftp.py:46); no duration-diversity requirement (ill-conditioned fits still return numbers); FTP=CP with no 0.95 discount (overestimates, unsafe direction).
- ZWO exports fixed 0.65 FTP for main_set regardless of session type/power_targets (zwo.py:22-26,97) — recovery session exports as 65% steady state.
- NaN propagation in metrics (np.clip passes NaN; NP/IF/TSS become NaN, breaks JSON); hard 1Hz assumption (smart recording distorts NP + TSS).
- Misc: zones no input validation; plan.py 0.56 vs 0.55 zone boundary duplication; week-4 segments can exceed duration; weekly_hours=0 still schedules sessions; load.py mild/moderate back distinction erased; zwo.py None duration_minutes TypeError.

## Phase 9 — Frontend Resilience

Critical:
- Stale session hijack: PersistedSession has no session id/date (sessionPersistence.ts:14-20); stale record redirects Today→/session, fast-forwards to complete, "Back to today" marks TODAY'S unrelated session done (TodayScreen.tsx:39-43, DuringSessionScreen.tsx:139-146).
- Chat SSE error bricks input: on error activeStreamUrl never cleared, isStreaming stuck, "Reconnecting..." with no reconnect logic (ChatScreen.tsx:87-106,128-132; useSSEStream.ts:74-87).
- Empty-done swallow: `if (isDone && content)` — tool-only turn never clears activeStreamUrl; handleSend silently returns forever (ChatScreen.tsx:87-99,110).
- No history reload + new conversation per cache miss (['active-conversation'] GC'd at 5min) — new DB conversation row per revisit, coaching context resets (ChatScreen.tsx:62-70).

Major:
- Ride field mismatch: backend returns duration_secs/avg_power; frontend reads duration_seconds/avg_power_watts/file_name → History shows "--" always (api.ts:82-95 vs rides.py:567-596).
- ZWO export error shape: FastAPI wraps {detail:{error}}, frontend reads err.error → session_not_found branch unreachable (api.ts:246-252).
- iOS ZWO export: window.open(blobUrl) after await → popup-blocked on iOS Safari (api.ts:263-267).
- Live-resume overshoot: multi-step background suspension advances one step and restarts it at full duration; reload path fast-forwards correctly, live path contradicts it (DuringSessionScreen.tsx:175-190,219-221).
- AppLayout min-h-screen breaks inner scroll panes; chat input not pinned; auto-scroll no-op (AppLayout.tsx:21,41-44).
- Query cache not user-scoped; SIGNED_IN (account switch) doesn't clear → previous user's data renders (router.tsx:30-37).
- Auth callback double-exchange: detectSessionInUrl:true auto-consumes code, manual exchangeCodeForSession then fails → bounce to /login despite valid session (AuthCallbackScreen.tsx:29-47, supabase.ts:9-13).
- No error boundary anywhere; white screen on any render exception.
- Onboarding confirm-stream: only token/done handled; server error event or early close → spinner stuck forever (OnboardingScreen.tsx:329-360; also 166-229).
- Upload: no progress; drag-drop skips .fit validation; success invalidates only ['rides'] — pmc/session queries stale (FitUploadZone.tsx, api.ts:286-318).

Minor: wake-lock NoSleep stacking + gesture requirement (useWakeLock.ts:18-29); chat message as GET query param (URL limits, logs); profile double cache key; AuthError retried 3x before redirect; SW runtime cache pattern matches no real route + no update UX; "No session steps" dead-end screen; Session TS interface mismatch (double as-unknown casts); 100vh not dvh in onboarding; touch targets <44px (settings gear, send button); StrictMode double POST /onboarding/start; dead App.tsx scaffold; calendar=connected param ignored by Settings.

Functionality gaps: no chat retry button/cancel; no password reset; /login no authed redirect; Agenda renders unreachable completed/missed icons, no past view; no completed-state confirmation on Today; adaptation log fetched but never rendered (TRANSP feature has no UI); SessionCard never passed ftp (ZwoExportModal always "FTP: not yet estimated"); SessionStepList dead code; no pull-to-refresh despite copy claiming it.

## Phase 10 — Hygiene and Safety Nets

- 8 stale SSE tests (tests/agent/test_sse.py) expect unauthenticated /chat/stream → 401; authenticate or mock auth dependency.
- tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields passes alone, fails in full run — test-order state leak (module-level Supabase singleton/monkeypatch bleed).
- Playwright: 33 failures per .planning/e2e-test-report.md — mock shape bugs (rides {rides:[]} wrapper, LIFO route shadowing), stale tests.
- Missing test coverage (high-value): plan.py and profile.py entirely untested; process_ride_background integration; cross-user IDOR; repeated /adaptations/check idempotency; duplicate-upload PMC; trust bypass/cross-turn FP corpus; SSE client disconnect; calendar duplicate push; api/index.py; ZWO endpoint; sessionPersistence/computeRestoredState; frontend-backend contract shapes (Ride/Profile/Session/error envelopes).
- Security/ops: JWT via ?token= accepted on ALL endpoints (auth.py:70) — replace with short-lived SSE token exchange (WR-006); conversation_id ownership never verified before save_messages; rate limiting absent on /chat/stream and /onboarding/start; no structured logging config; no error monitoring; no CI (.github/workflows absent); calendar duplicate event push (calendar_sync.py:243-261 no calendar_event_id filter); refreshed Google tokens never persisted; legacy /calendar/auth endpoint superseded but exposed; oauth_states no on_conflict/TTL; auth.py 500s (missing JWT secret → 500 not 401; sub-less token KeyError); PyJWKClient sync fetch in async dep; SSE no keepalive frames; AsyncAnthropic client never closed; on client disconnect save_messages never runs (turn lost); loop.py max_tokens stop → unexpected_stop error (4096 cap, plan narration can hit); db singleton race x3 modules.
- Repo: root node_modules/ (stray vite cache — delete, add to root .gitignore), test-ride.fit → tests/fixtures/ or delete, docs/Pace Wireframes (standalone).html decide, .gitignore `.env*` unanchored trap.
