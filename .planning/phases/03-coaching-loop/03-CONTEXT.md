# Phase 3: Coaching Loop - Context

**Gathered:** 2026-06-20
**Status:** Ready for planning

<domain>
## Phase Boundary

Build the full coaching loop: conversational onboarding interview that persists a user profile, cold-start plan generation with RPE/HR targets (no FTP), .FIT file ingestion pipeline (fitdecode + TSS/NP/IF + PMC update), and adaptive re-planning with cited sports-science explanations. The agent drives all logic through Phase 2's tool registry and SSE endpoint. No UI — API and agent layer only (UI is Phase 4).

**In scope:** onboarding interview, profile persistence, plan generation (structured JSON → DB), FIT file ingestion endpoint, fitdecode parsing, PMC update, missed-session detection, adaptive re-planning, adaptation log, transparency explanations in chat.

**Out of scope:** React UI, Google Calendar, ZWO export, Telegram bot, Strava, Web Bluetooth.

</domain>

<decisions>
## Implementation Decisions

### Onboarding Interview Flow

- **D-01:** The interview is driven by the agent loop (Phase 2's `run_turn`). Claude asks structured questions in natural language; the agent collects answers over multiple turns. A dedicated `POST /onboarding/start` endpoint creates the conversation and returns the initial SSE stream.
- **D-02:** The interview collects: fitness goals, available weekly hours, preferred days, injury/back status (binary: yes/no, then severity if yes), current equipment (trainer confirmed as Wahoo Kickr Core + Zwift), RPE self-assessment baseline. Exactly these fields — no more.
- **D-03:** After data collection the agent presents a plain-text confirmation summary ("Here is what I have...") and waits for explicit user approval before calling `generate_plan`. This is the ONBD-04 gate.
- **D-04:** Profile data is persisted to the `profiles` table via a `save_profile` tool registered in the tool registry. Claude calls it; it never fabricates profile fields.
- **D-05:** Back status is a first-class field: `back_status: "none" | "mild" | "moderate"`. When `moderate`, `progress_load` enforces the back-protective constraints (already in Phase 1 tool — just pass the flag).

### Plan Generation

- **D-06:** The plan is represented as a list of weekly `sessions` in a `plans` table row (JSON column). Each session has: `day`, `duration_minutes`, `type` (endurance/recovery/strength), `zone_targets` (HR zones or RPE scale), `power_targets` (null until FTP confidence >= medium).
- **D-07:** Cold-start sessions use HR zones only (Friel 5-zone). Power targets are added automatically once `estimate_ftp_from_rides` returns confidence >= "medium" (4+ quality efforts). The agent re-calls `calculate_power_zones` and patches the open sessions.
- **D-08:** Plan generation calls tools in this order: `progress_load` (sets weekly TSS targets), `calculate_hr_zones` (LTHR from interview or estimated), then emits the session list. Every number in the plan traces to a tool result.
- **D-09:** The plan covers 4 weeks (mesocycle). Week 1 is always conservative: zone 2 aerobic, short durations, no threshold. Week 4 is a recovery week (volume -40%). This is hardcoded policy, not LLM judgment.
- **D-10:** `generate_plan` is a new tool registered in the tool registry that takes profile + load targets and returns a structured plan. The LLM calls it; it never emits plan numbers from its own reasoning.

### FIT Ingestion Pipeline

- **D-11:** FIT ingestion endpoint: `POST /rides/upload` accepts `multipart/form-data` with the `.FIT` file and `user_id`. It is a standard async FastAPI endpoint, not SSE.
- **D-12:** fitdecode (not fitparse) parses the file. The pipeline: `fitdecode.FitReader` → extract records → numpy array for power/HR/cadence → `compute_tss`, `update_pmc`, `validate_session_vs_actual` → persist to `rides` and `pmc_history`. All runs in `asyncio.to_thread` (CPU-bound).
- **D-13:** The acceptance test uses a real Zwift .FIT file checked into `tests/fixtures/sample_zwift.fit`. The test is integration-level: upload → parse → assert TSS > 0, CTL updated, ride row in DB.
- **D-14:** FIT parsing errors (corrupt file, missing power stream) return a structured error response: `{"error": "fit_parse_failed", "detail": "..."}` with HTTP 422. Never silently succeed with zeros.
- **D-15:** After successful FIT ingestion, the agent is triggered asynchronously (background task) to assess whether the ride warrants an adaptation signal. It calls `validate_session_vs_actual` and `update_pmc`, then posts a brief chat message to the conversation.

### Adaptive Re-planning

- **D-16:** A "missed session" is detected when a scheduled session has no matching ride within ±1 day of its date and the session date has passed. Checked lazily when the user next opens a conversation or explicitly via `POST /sessions/{id}/missed`.
- **D-17:** Micro-adjustment (1-3 session shifts): triggered by a single missed session or a single under-performance signal (actual TSS < 60% of target). The agent adjusts the next 1-3 sessions inline, no new plan generated.
- **D-18:** Macro re-plan (full restructure): requires 2+ signals in a rolling 7-day window (e.g., 2 missed sessions, or 1 missed + 1 significant underperformance). Calls `progress_load` with updated weekly capacity. The agent presents a change summary before applying — never silently replaces sessions.
- **D-19:** No macro replan shifts more than 30% of upcoming sessions without surfacing a change summary to the user. This is enforced by the `validate_session_vs_actual` tool return value check.
- **D-20:** Every adaptation is logged to an `adaptations` table: `user_id`, `trigger` (missed/underperformance/overreaching), `signal_count`, `scope` (micro/macro), `before_snapshot`, `after_snapshot`, `explanation_text`, `timestamp`.

### Conversation Continuity

- **D-21:** Each conversation is stored in the `conversations` table with a `context_type` field: `onboarding | coaching | ride_debrief`. The SSE endpoint (`GET /chat/stream?conversation_id=X`) rehydrates conversation history from the `messages` table (last 20 messages) before the next `run_turn` call.
- **D-22:** The system prompt passed to Claude is dynamic: it includes the user's profile summary, current FTP confidence level, and the current plan's week number. This context is injected fresh on every `run_turn` call (no stale cache).
- **D-23:** Ride debrief conversations are triggered automatically after FIT ingestion. The agent's opening message cites the actual TSS vs target, notes any capability-gap logs, and asks one focused question.

### Sports-Science Constraints (Non-negotiable, from Phase 1)

- **D-24:** The `back_status: "moderate"` flag is forwarded to `progress_load` on every plan generation and adaptation. Never omitted.
- **D-25:** FTP confidence thresholds from Phase 1 apply: `n < 4` = none (RPE/HR only), `4 <= n < 12` = medium (power zones appear), `n >= 12` = high (full power training). These are read from `estimate_ftp_from_rides` return value, never hardcoded in agent text.

</decisions>

<open_questions>
## Open Questions — RESOLVED (answered during implementation)

1. **fitdecode async pattern** — RESOLVED: `parse_fit_file` runs synchronously under `asyncio.to_thread`; no chunking needed for typical Zwift ride sizes (03-04-SUMMARY.md).
2. **Supabase real-time for ride triggers** — RESOLVED: FastAPI `BackgroundTasks` used; supabase-py-async real-time not required (03-04-SUMMARY.md).
3. **Zwift .FIT power stream field name** — RESOLVED: `get_value('power', fallback=None)` confirmed against real Zwift fixture (sample_zwift.fit, 8228 bytes, 900s); first-record field logging added as debug aid (03-04-SUMMARY.md).
4. **`generate_plan` tool complexity** — RESOLVED: single `generate_plan` tool sufficient; `progress_load` output feeds TSS targets inline (03-02-SUMMARY.md).
5. **Conversation history truncation** — DEFERRED: token-count truncation deferred to Phase 4 TODO in `load_conversation` docstring (03-03-SUMMARY.md).
</open_questions>

<phase_summary>
## What Phase 3 Delivers

At the end of Phase 3, a developer can:
1. POST to `/onboarding/start`, complete the interview in a chat loop, and see a plan saved to the DB
2. Upload a real Zwift .FIT file and see TSS/CTL/ATL updated, with a ride debrief message in the conversation
3. Trigger a missed-session micro-adjustment and see 1-3 sessions shifted with an explanation
4. Observe that every plan number traces to a sports-science tool call in the audit log

No UI is required. The API is the deliverable.
</phase_summary>
