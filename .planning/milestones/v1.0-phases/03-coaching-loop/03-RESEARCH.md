# Phase 03: Coaching Loop - Research

**Researched:** 2026-06-20
**Domain:** FastAPI + Anthropic tool use + fitdecode + Supabase + PMC math
**Confidence:** HIGH (codebase read directly; decisions locked in CONTEXT.md)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- D-01: Interview driven by Phase 2's `run_turn`; `POST /onboarding/start` creates conversation and returns initial SSE stream
- D-02: Interview collects: fitness goals, weekly hours, preferred days, injury/back status (binary then severity), equipment (confirmed Wahoo Kickr Core + Zwift), RPE self-assessment. Exactly these fields.
- D-03: Agent presents plain-text confirmation summary and waits for explicit user approval before calling `generate_plan` (ONBD-04 gate)
- D-04: Profile persisted to `profiles` table via `save_profile` tool in tool registry
- D-05: `back_status: "none" | "mild" | "moderate"` -- when moderate, `progress_load` enforces back-protective constraints
- D-06: Plan stored as `plans` table row with JSON `sessions` column. Each session: `day`, `duration_minutes`, `type`, `zone_targets`, `power_targets` (null until FTP confidence >= medium)
- D-07: Cold-start uses Friel 5-zone HR only. Power targets added automatically once `estimate_ftp_from_rides` returns confidence >= "medium" (4+ quality efforts). Agent re-calls `calculate_power_zones` and patches open sessions.
- D-08: Plan generation tool call order: `progress_load` -> `calculate_hr_zones` -> emit session list. Every number traces to a tool result.
- D-09: 4-week mesocycle. Week 1 always conservative (zone 2, short, no threshold). Week 4 recovery (-40% volume). Hardcoded policy, not LLM judgment.
- D-10: `generate_plan` is a new tool in the tool registry. Takes profile + load targets, returns structured plan.
- D-11: FIT ingestion endpoint: `POST /rides/upload`, multipart/form-data, fields: `.FIT` file + `user_id`. Standard async FastAPI, not SSE.
- D-12: fitdecode (not fitparse) parses the file. Pipeline: `fitdecode.FitReader` -> records -> numpy array -> `compute_tss`, `update_pmc`, `validate_session_vs_actual` -> persist to `rides` and `pmc_history`. Runs in `asyncio.to_thread`.
- D-13: Acceptance test uses real Zwift .FIT file in `tests/fixtures/sample_zwift.fit`. Integration-level: upload -> parse -> assert TSS > 0, CTL updated, ride row in DB.
- D-14: FIT parse errors return `{"error": "fit_parse_failed", "detail": "..."}` with HTTP 422. Never silently succeed with zeros.
- D-15: After FIT ingestion, agent triggered asynchronously (FastAPI BackgroundTasks) to call `validate_session_vs_actual` and `update_pmc`, then posts brief chat message to conversation.
- D-16: Missed session = scheduled session with no matching ride within ±1 day and session date has passed. Checked lazily on conversation open or via `POST /sessions/{id}/missed`.
- D-17: Micro-adjustment: single missed session or single under-performance (actual TSS < 60% of target). Adjusts next 1-3 sessions inline, no new plan.
- D-18: Macro re-plan: 2+ signals in rolling 7-day window. Calls `progress_load` with updated weekly capacity. Agent presents change summary before applying.
- D-19: No macro replan shifts more than 30% of upcoming sessions without surfacing change summary. Enforced by `validate_session_vs_actual` return value check.
- D-20: Every adaptation logged to `adaptations` table: `user_id`, `trigger`, `signal_count`, `scope`, `before_snapshot`, `after_snapshot`, `explanation_text`, `timestamp`.
- D-21: Conversations stored in `conversations` table with `context_type` field: `onboarding | coaching | ride_debrief`. SSE endpoint rehydrates last 20 messages from `messages` table.
- D-22: System prompt is dynamic per `run_turn` call: includes user profile summary, FTP confidence level, current plan week number.
- D-23: Ride debrief conversation triggered automatically after FIT ingestion. Opening message cites actual TSS vs target, notes capability-gap logs, asks one focused question.
- D-24: `back_status: "moderate"` forwarded to `progress_load` on every plan generation and adaptation. Never omitted.
- D-25: FTP confidence thresholds read from `estimate_ftp_from_rides` return value. Never hardcoded in agent text.

### Claude's Discretion

None specified in CONTEXT.md for this phase.

### Deferred Ideas (OUT OF SCOPE)

- React UI (Phase 4)
- Google Calendar integration (Phase 4)
- ZWO export (Phase 5)
- Telegram bot (v2)
- Web Bluetooth (v2)
- Strava integration (excluded)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ONBD-01 | Conversational LLM-led interview: baseline fitness, injury/back status, equipment, weekly time, goals | D-01/D-02 define fields; `run_turn` from Phase 2 drives conversation |
| ONBD-02 | Injury/back status persisted and applied as back-protective plan constraints; never assumed | D-05 `back_status` field; D-24 always forwarded to `progress_load` |
| ONBD-03 | Interview output is persisted structured user profile in DB | `profiles` table already exists in migration 0001; `save_profile` tool (D-04) |
| ONBD-04 | User sees confirmation summary before plan is generated | D-03 gate in system prompt/agent flow |
| PLAN-01 | Structured periodised plan appropriate to returning beginner | D-09 4-week mesocycle with Week 1 conservative |
| PLAN-02 | Cold-start: RPE/HR targets, not power | D-07 Friel 5-zone HR until FTP confidence >= medium |
| PLAN-03 | Power targets only after FTP confidence >= medium (4+ quality efforts) | D-25 reads from `estimate_ftp_from_rides`; D-07 patches open sessions |
| PLAN-04 | Every session has objective, structure, targets, duration | D-06 session JSON schema |
| PLAN-05 | Back-protective constraints reflected in plan | D-05, D-24, existing `progress_load` back constraints already implemented |
| PLAN-06 | Every physiological number traceable to tool-library call | D-08 tool call order enforces this |
| FIT-01 | User can upload .FIT file | `POST /rides/upload` endpoint (D-11); FIT-01 is UI-layer; backend only in Phase 3 |
| FIT-02 | fitdecode with ErrorHandling.WARN; get_value with fallback; GPS not required | D-12 fitdecode pipeline |
| FIT-03 | Extract power, HR, cadence, duration; missing fields handled gracefully | D-12 numpy array extraction |
| FIT-04 | compute_tss called; update_pmc called; results persisted to rides and pmc_history | D-12, D-15 background task |
| FIT-05 | Parsed ride feeds validate_session_vs_actual | D-15 background task |
| FIT-06 | Real Zwift .FIT file acceptance test | D-13 `tests/fixtures/sample_zwift.fit` |
| ADAPT-01 | Plan adapts based on missed sessions, performance, training load | D-16/D-17/D-18 detection and response logic |
| ADAPT-02 | Micro vs macro adaptation distinguished; macro requires 2+ signals | D-17 vs D-18 |
| ADAPT-03 | No macro replan shifts >30% without change summary | D-19 enforced via validate_session_vs_actual |
| ADAPT-04 | Weekly automated check independent of upload events | Needs background scheduler or cron endpoint |
| ADAPT-05 | Intensity/session type decided dynamically using tool-library results | D-18 calls `progress_load`; agent decides based on tool results |
| TRANSP-01 | Agent cites TSS/CTL/TSB/ATL values and sports-science principle in chat | Dynamic system prompt (D-22); agent references tool results |
| TRANSP-02 | Every plan change persisted to adaptation log | D-20 `adaptations` table |
| TRANSP-03 | Adaptation log readable by user | New endpoint needed: `GET /adaptations` |
</phase_requirements>

---

## Overview

Phase 3 builds the complete coaching loop on top of Phase 2's agent infrastructure. The primary deliverable is a working API (no UI) that lets a developer: complete a multi-turn onboarding interview to produce a persisted training plan, upload a Zwift .FIT file and see TSS/CTL/ATL updated, trigger a missed-session micro-adjustment, and observe that every plan number is traced to a sports-science tool call.

The foundation is solid: `run_turn`, `TOOL_REGISTRY`, `TOOL_SCHEMAS`, `dispatch_tool`, `scan_buffer`, and the 8 original sports-science tools are all production-ready from Phase 2. Phase 3 extends rather than replaces this foundation with: 2 new tools (`save_profile`, `generate_plan`), 3 new API routers (`onboarding`, `rides`, `adaptations`), a FIT parsing pipeline, background task dispatch, and 4 new DB tables (via a second migration).

---

## Phase 2 Foundation (What Already Exists)

### Agent Layer [VERIFIED: codebase]

| File | What It Does | Phase 3 Relevance |
|------|-------------|-------------------|
| `agent/loop.py` | `run_turn` async generator; SSE events; trust scan; tool dispatch; retry cap (MAX_RETRIES=3) | Called unchanged by new onboarding and coaching routers |
| `agent/tools.py` | `TOOL_REGISTRY`, `TOOL_SCHEMAS`, `dispatch_tool`, `dedup_key` | Phase 3 adds `save_profile` and `generate_plan` to both dicts; TRUST-02 import-time assertion will catch mismatches |
| `agent/trust.py` | `scan_buffer`, `handle_violation`, `TrustViolation` | Unchanged; new tools must return `ToolResult` so trust attribution works |

### Sports-Science Library [VERIFIED: codebase]

All 8 tools are implemented, tested, and returning `ToolResult(value, unit, methodology, inputs)`:

| Tool | Signature | Key Output Fields |
|------|-----------|------------------|
| `calculate_power_zones(ftp)` | `-> ToolResult` | `value = [{zone, name, lower_watts, upper_watts}, ...]` |
| `calculate_hr_zones(max_hr_or_lthr)` | `-> ToolResult` | `value = [{zone, name, lower_bpm, upper_bpm}, ...]` |
| `estimate_ftp_from_rides(rides)` | `-> ToolResult` | `value = {ftp, cp, wprime, confidence}` or `None` |
| `compute_tss(power_array, duration_secs, ftp)` | `-> ToolResult` | `value = {tss, np_watts, intensity_factor, warnings}` |
| `update_pmc(prev_ctl, prev_atl, tss, days_of_data)` | `-> ToolResult` | `value = {ctl, atl, tsb, tss_display_ready}` |
| `progress_load(current_ctl, target_ctl, constraints)` | `-> ToolResult` | `value = {recommended_ctl_target, max_weekly_increase, back_constraints_applied}` |
| `validate_session_vs_actual(planned, actual)` | `-> ToolResult` | `value = {compliance_pct, delta_tss, flags: [under_performed|over_performed]}` |
| `log_capability_gap(method_name, context)` | `async -> ToolResult` | `value = {status: "logged", message: <user-safe text>}` |

**Critical constraint:** `compute_tss` requires `ftp > 0`. For cold-start users, FTP is unknown. The FIT pipeline must handle the case where FTP is not yet estimated: use a placeholder FTP (e.g., 150W tagged as estimated) or skip TSS calculation and store NP only. This is an open question (see below).

### API Layer [VERIFIED: codebase]

`api/main.py` mounts `chat_router` at `/chat`. The existing `GET /chat/stream?conversation_id=X` endpoint uses in-memory messages (Phase 2 placeholder). Phase 3 replaces the placeholder with a real DB load.

### Database Schema [VERIFIED: codebase - supabase/migrations/0001_initial_schema.sql]

Tables already in production migration:

| Table | Key Columns | Phase 3 Use |
|-------|-------------|-------------|
| `users` | `id uuid PK`, `email`, `google_tokens jsonb`, `created_at` | Auth anchor; user_id FK for all other tables |
| `profiles` | `id uuid`, `user_id FK`, `constraints jsonb`, `fitness_level`, `equipment jsonb`, `goals jsonb` | `save_profile` tool writes here; **missing `back_status`, `weekly_hours`, `preferred_days`, `rpe_baseline`** |
| `sessions` | `id uuid`, `user_id FK`, `objective`, `structure jsonb`, `targets jsonb`, `duration_mins`, `status`, `scheduled_date` | Plan sessions stored here; **missing `plan_id`, `type`, `zone_targets`, `power_targets`, `week_num`** |
| `rides` | `id uuid`, `user_id FK`, `tss`, `np_watts`, `intensity_factor`, `duration_secs`, `raw_fit_path`, `created_at` | FIT ingestion writes here; **missing `session_id`, `ride_date`, `avg_power`, `avg_hr`, `avg_cadence`, `ftp_used`** |
| `pmc_history` | `id uuid`, `user_id FK`, `date`, `ctl`, `atl`, `tsb`, `tss_display_ready` | `update_pmc` pipeline writes here; **complete for Phase 3 use** |
| `conversations` | `id uuid`, `user_id FK`, `created_at` | **Missing `context_type` field (D-21: onboarding\|coaching\|ride_debrief)** |
| `messages` | `id uuid`, `conversation_id FK`, `user_id FK`, `role`, `content text`, `created_at` | Conversation history persistence; **role enum may need 'system' for dynamic prompts** |
| `capability_gaps` | `id uuid`, `user_id`, `method_name`, `description`, `context jsonb`, `conversation_id`, `created_at` | Already fully functional from Phase 1/2 |

**Tables NOT YET CREATED (need new migration):**
- `plans` -- stores the 4-week plan JSON
- `adaptations` -- adaptation log (D-20)

---

## New Tools Required

Phase 3 adds exactly 2 new tools to `TOOL_REGISTRY` and `TOOL_SCHEMAS`. The TRUST-02 import-time assertion checks that these sets match exactly -- any mismatch raises `RuntimeError` at startup.

### Tool: `save_profile`

**Purpose:** Persist the collected interview data to the `profiles` table. Claude calls this once the user approves their profile summary (D-03 gate).

**Signature:**
```python
async def save_profile(
    user_id: str,
    fitness_goals: str,
    weekly_hours: float,
    preferred_days: list[str],
    back_status: str,          # "none" | "mild" | "moderate"
    equipment: dict,           # {"trainer": "Wahoo Kickr Core", "platform": "Zwift"}
    rpe_baseline: str,         # e.g. "beginner", "moderate"
    lthr_estimate: float | None,  # from interview RPE assessment, or None
) -> ToolResult
```

**Implementation notes:**
- Uses `supabase-py-async` `acreate_client` singleton pattern (same as `log_capability_gap`)
- Upserts into `profiles` (in case of re-interview): `ON CONFLICT (user_id) DO UPDATE`
- Maps `back_status` to `constraints` JSONB: `moderate` -> `{"back_issues": true, "load_ramp_flag_threshold_pct": 10}`
- Returns `ToolResult(value={"profile_id": str, "saved": True}, unit="", methodology="profile_persistence", inputs={...})`
- Must be `async` (DB write); `dispatch_tool` routes async functions via `asyncio.iscoroutinefunction` branch

**Schema requirement:** `profiles` table needs new columns: `back_status text`, `weekly_hours numeric`, `preferred_days text[]`, `rpe_baseline text`, `lthr_estimate numeric`.

### Tool: `generate_plan`

**Purpose:** Take profile data + load targets from `progress_load` and produce a structured 4-week session list. Returns structured plan data that is then persisted to `plans` table.

**Signature:**
```python
def generate_plan(
    user_id: str,
    weekly_hours: float,
    back_status: str,
    current_ctl: float,
    load_targets: dict,        # output of progress_load: {recommended_ctl_target, max_weekly_increase}
    hr_zones: list[dict],      # output of calculate_hr_zones: [{zone, name, lower_bpm, upper_bpm}]
    ftp_confidence: str,       # "insufficient_data" | "low" | "medium" | "high"
    ftp_watts: float | None,   # None for cold-start; non-null when confidence >= medium
) -> ToolResult
```

**Implementation notes:**
- Sync function (pure computation); no DB write -- agent does DB write after receiving the plan
- Output shape in `ToolResult.value`:
  ```python
  {
    "plan_id": None,  # assigned by DB insert; tool returns the template
    "mesocycle_weeks": 4,
    "sessions": [
      {
        "week": 1,
        "day": "Monday",
        "type": "endurance",
        "objective": "Zone 2 aerobic base",
        "duration_minutes": 45,
        "zone_targets": {"hr_zone": 2, "lower_bpm": 130, "upper_bpm": 150},
        "power_targets": None,  # null until FTP confidence >= medium
        "rpe_target": 3,        # 1-10 Borg scale
      },
      ...
    ],
    "week4_volume_reduction_pct": 40,
    "constraints_applied": ["back_protective", "beginner_cap"],
    "methodology": "4-week base mesocycle; Week 1 conservative; Week 4 -40% recovery"
  }
  ```
- Week 1 policy (hardcoded, not LLM): zone 2 aerobic only, max 45-min sessions, no intervals, no threshold
- Week 4 policy: all session durations multiplied by 0.6 (40% volume reduction)
- Session count derived from `weekly_hours`: 1h/week -> 2 sessions/week, 2-3h/week -> 3 sessions/week, 4h+/week -> 4 sessions/week
- Back status `moderate`: cap first 2 weeks at 30-minute sessions max; no standing efforts; no sprint efforts
- `ftp_confidence` drives `zone_targets`: if "insufficient_data" or "low", zone_targets use HR zones only; if "medium" or "high", also include power_targets
- The function must not call any other sports-science function directly (trust model: LLM must call tools in sequence via the agent loop)

**TRUST-02 invariant:** After adding `save_profile` and `generate_plan` to `TOOL_REGISTRY` and `TOOL_SCHEMAS`, the set sizes must match. Current: 8 tools each. New: 10 tools each.

---

## DB Schema Changes

A second migration is required. The plan is to keep it in one file: `supabase/migrations/0002_phase3_schema.sql`.

### Modifications to Existing Tables

```sql
-- profiles: add interview-collected fields
ALTER TABLE public.profiles
  ADD COLUMN back_status      text NOT NULL DEFAULT 'none'
                              CHECK (back_status IN ('none', 'mild', 'moderate')),
  ADD COLUMN weekly_hours     numeric,
  ADD COLUMN preferred_days   text[],
  ADD COLUMN rpe_baseline     text,
  ADD COLUMN lthr_estimate    numeric;

-- profiles: unique constraint so save_profile can upsert
ALTER TABLE public.profiles
  ADD CONSTRAINT profiles_user_id_unique UNIQUE (user_id);

-- sessions: add plan linkage and richer schema
ALTER TABLE public.sessions
  ADD COLUMN plan_id      uuid REFERENCES public.plans ON DELETE CASCADE,
  ADD COLUMN type         text CHECK (type IN ('endurance', 'recovery', 'strength', 'interval')),
  ADD COLUMN zone_targets jsonb,
  ADD COLUMN power_targets jsonb,
  ADD COLUMN week_num     int,
  ADD COLUMN rpe_target   int;

-- rides: add session linkage and raw metrics
ALTER TABLE public.rides
  ADD COLUMN session_id   uuid REFERENCES public.sessions ON DELETE SET NULL,
  ADD COLUMN ride_date    date,
  ADD COLUMN avg_power    numeric,
  ADD COLUMN avg_hr       numeric,
  ADD COLUMN avg_cadence  numeric,
  ADD COLUMN ftp_used     numeric;  -- FTP value used for TSS calc (audit trail)

-- conversations: add context_type (D-21)
ALTER TABLE public.conversations
  ADD COLUMN context_type text NOT NULL DEFAULT 'coaching'
             CHECK (context_type IN ('onboarding', 'coaching', 'ride_debrief'));
```

### New Tables

```sql
-- plans: stores the 4-week plan as returned by generate_plan
CREATE TABLE public.plans (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    sessions        jsonb NOT NULL,         -- array of session objects from generate_plan
    mesocycle_weeks int NOT NULL DEFAULT 4,
    ftp_confidence  text,                   -- confidence at plan generation time
    status          text NOT NULL DEFAULT 'active'
                    CHECK (status IN ('active', 'completed', 'superseded')),
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.plans ENABLE ROW LEVEL SECURITY;
CREATE POLICY "plans: own row" ON public.plans USING (user_id = auth.uid());

-- adaptations: audit trail for every plan change (D-20, TRANSP-02)
CREATE TABLE public.adaptations (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid NOT NULL REFERENCES public.users ON DELETE CASCADE,
    trigger         text NOT NULL CHECK (trigger IN ('missed', 'underperformance', 'overreaching')),
    signal_count    int NOT NULL DEFAULT 1,
    scope           text NOT NULL CHECK (scope IN ('micro', 'macro')),
    before_snapshot jsonb,       -- sessions before change
    after_snapshot  jsonb,       -- sessions after change
    explanation_text text,       -- user-facing explanation cited in chat
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.adaptations ENABLE ROW LEVEL SECURITY;
CREATE POLICY "adaptations: own row" ON public.adaptations USING (user_id = auth.uid());
```

**RLS pattern:** All new table inserts from the backend use `SUPABASE_SERVICE_ROLE_KEY` (same pattern as `capability_gaps`). Read access for users goes through RLS with JWT.

---

## Onboarding Interview Implementation

### Endpoint: `POST /onboarding/start`

```python
# api/routes/onboarding.py
@router.post("/start")
async def onboarding_start(user_id: str = Body(...)):
    # 1. Create conversation row with context_type='onboarding'
    # 2. Insert opening user message: "I'd like to start my training interview."
    # 3. Build initial messages list with dynamic system prompt
    # 4. Return StreamingResponse via sse_generator (same pattern as GET /chat/stream)
```

The router reuses `sse_generator` from `api/routes/chat.py` (or extracts it to a shared helper).

### Dynamic System Prompt (D-22)

The system prompt passed to `run_turn` must be assembled fresh per request:

```python
ONBOARDING_SYSTEM_PROMPT = """
You are PacerAI, an evidence-based adaptive cycling coach conducting an onboarding interview.

Your goal is to collect EXACTLY these fields through natural conversation:
1. fitness_goals (short text)
2. weekly_hours (numeric, available training hours per week)
3. preferred_days (list of days: Monday, Tuesday, etc.)
4. back_status ("none", "mild", or "moderate") -- ask if they have any back issues and severity
5. equipment (already known: Wahoo Kickr Core + Zwift; confirm with user)
6. rpe_baseline (how they'd describe their current fitness: beginner/moderate/fit)

After collecting all fields, present a plain-text summary ("Here is what I have:...") and wait for 
the user to say something like "yes", "that's correct", or "looks good" before calling save_profile 
and then generate_plan.

RULES:
- Call save_profile only after receiving explicit user approval of the summary.
- Call generate_plan only after save_profile succeeds.
- Call progress_load and calculate_hr_zones BEFORE emitting any session from generate_plan.
- Never emit a physiological number without calling the appropriate tool.
- If the user has back_status="moderate", pass back_issues=true to progress_load.
"""
```

### Tool Call Sequence for Plan Generation

```
User approves summary
  -> Claude calls save_profile(user_id, ...) -- persists profile
  -> Tool result: {profile_id: "...", saved: True}
  -> Claude calls progress_load(current_ctl=0, target_ctl=20, constraints={...})
  -> Tool result: {recommended_ctl_target: 8.0, max_weekly_increase: 8.0, ...}
  -> Claude calls calculate_hr_zones(max_hr_or_lthr=lthr_estimate or 160)
  -> Tool result: [{zone: 1, lower_bpm: ..., upper_bpm: ...}, ...]
  -> Claude calls generate_plan(user_id, weekly_hours, back_status, current_ctl=0, 
                                load_targets={...}, hr_zones=[...], 
                                ftp_confidence="insufficient_data", ftp_watts=None)
  -> Tool result: {sessions: [...], mesocycle_weeks: 4, ...}
  -> Claude persists plan (via save_plan tool OR direct DB write in generate_plan)
  -> Claude presents plan to user in natural language
```

**Note on LTHR cold-start:** When no LTHR is known (cold start), use 160 bpm as a conservative placeholder and tell the user. This produces zone boundaries that are slightly conservative for a beginner, which is safe. Tag this as a capability gap if needed.

### Conversation Persistence

Phase 3 upgrades `GET /chat/stream` to load conversation history from DB:

```python
# Replace Phase 2 in-memory placeholder:
messages = await load_conversation(conversation_id, limit=20)  # last 20 messages

# load_conversation: SELECT * FROM messages WHERE conversation_id = ? 
# ORDER BY created_at DESC LIMIT 20, then reverse for chronological order
# Each message: {"role": role, "content": content}
```

After each `run_turn` completes, persist new messages:
```python
await save_messages(conversation_id, user_id, new_messages)
# new_messages: list of {role, content} added during this turn
```

**20-message limit concern (Open Question 5 in CONTEXT.md):** A full onboarding interview may use 10-15 message pairs. 20 messages = 10 exchange pairs -- tight but workable for Phase 3. Token-count-based truncation is deferred to Phase 4; use 20-message cap with a TODO comment.

---

## Plan Generation Implementation

### `plans` Table vs `sessions` Table

The design decision in CONTEXT.md (D-06) stores the plan as a JSON column in `plans`. However, the existing `sessions` table has individual session rows. Phase 3 uses both:

- `plans` table: stores the full plan JSON (for quick retrieval, adaptation snapshots)
- `sessions` table: individual session rows linked via `plan_id` FK (for missed-session detection, Calendar sync in Phase 4)

The `generate_plan` tool returns the JSON. The backend writes one row to `plans` and N rows to `sessions` (one per session in the 4-week plan). This is not a tool call -- the API layer does this DB write after receiving the `generate_plan` tool result.

### Cold-Start Plan Structure (PLAN-02)

Week 1 - Week 3 sessions (before FTP confidence >= medium):
```json
{
  "week": 1,
  "day": "Tuesday",
  "type": "endurance",
  "objective": "Zone 2 aerobic base - comfortable, conversational pace",
  "structure": {
    "warmup": {"duration_minutes": 10, "description": "Easy spin, HR Zone 1"},
    "main_set": {"duration_minutes": 30, "description": "Zone 2 aerobic - could hold a full conversation"},
    "cooldown": {"duration_minutes": 5, "description": "Easy spin"}
  },
  "duration_minutes": 45,
  "zone_targets": {"hr_zone": 2, "lower_bpm": 130, "upper_bpm": 148},
  "power_targets": null,
  "rpe_target": 3
}
```

### FTP Upgrade Path (PLAN-03, D-07)

When `estimate_ftp_from_rides` returns confidence >= "medium":
1. Agent calls `calculate_power_zones(ftp=estimated_ftp)`
2. Agent patches all future (not-yet-completed) sessions to add `power_targets`
3. DB update: `UPDATE sessions SET power_targets = ? WHERE user_id = ? AND status = 'planned' AND scheduled_date > now()`
4. Agent explains the upgrade in chat: "You now have 4 quality rides. I've calculated your power zones and updated your upcoming sessions."

### Back-Protective Constraints (PLAN-05)

`back_status = "moderate"` constraints applied in `generate_plan`:
- Weeks 1-2: max 30-minute sessions
- No session type "strength" until Week 3
- No RPE > 6 in Week 1
- `progress_load` receives `{"back_issues": true, "load_ramp_flag_threshold_pct": 10}`

---

## FIT Ingestion Pipeline

### fitdecode Package [VERIFIED: PyPI registry -- version 0.11.0 confirmed]

fitdecode 0.11.0 is the current version on PyPI (August 2025). Not in the current venv -- must be added to `requirements.txt`.

**Critical API details** [ASSUMED -- training knowledge; fitdecode not installed, no Context7 entry]:

```python
import fitdecode

def parse_fit_file(file_bytes: bytes) -> dict:
    """
    Parse .FIT file bytes, extract power/HR/cadence arrays.
    
    fitdecode.FitReader pattern:
    - Pass bytes directly via BytesIO or file path
    - error_handling=fitdecode.ErrorHandling.WARN (not RAISE)
    - Iterate over frames
    - Check frame.mesg_type.name == 'record' for data records
    - Use frame.get_value('field_name', fallback=None) for safe access
    """
    import io
    import numpy as np
    
    power_samples = []
    hr_samples = []
    cadence_samples = []
    duration_secs = 0
    
    with fitdecode.FitReader(
        io.BytesIO(file_bytes),
        error_handling=fitdecode.ErrorHandling.WARN,
    ) as reader:
        for frame in reader:
            if isinstance(frame, fitdecode.FitDataMessage):
                if frame.name == 'record':
                    power = frame.get_value('power', fallback=None)
                    hr = frame.get_value('heart_rate', fallback=None)
                    cadence = frame.get_value('cadence', fallback=None)
                    # timestamp for duration calc
                    ts = frame.get_value('timestamp', fallback=None)
                    
                    power_samples.append(power or 0)  # zeros for nulls (NP includes zeros)
                    if hr is not None:
                        hr_samples.append(hr)
                    if cadence is not None:
                        cadence_samples.append(cadence)
    
    # Duration from sample count (1 Hz assumption for indoor Zwift rides)
    duration_secs = len(power_samples)
    
    return {
        "power_array": power_samples,
        "hr_array": hr_samples,
        "cadence_array": cadence_samples,
        "duration_secs": duration_secs,
        "avg_hr": int(np.mean(hr_samples)) if hr_samples else None,
        "avg_cadence": int(np.mean(cadence_samples)) if cadence_samples else None,
    }
```

**Zwift .FIT field names** [ASSUMED]: Zwift exports use standard ANT+ FIT field names: `power` (watts), `heart_rate` (bpm), `cadence` (rpm), `timestamp`. The `enhanced_speed` field is for speed data, not power. GPS fields (`position_lat`, `position_long`) are absent in indoor rides -- the pipeline must not require them (FIT-02: "GPS fields are not required").

**asyncio.to_thread pattern** for CPU-bound FIT parsing (D-12):

```python
# api/routes/rides.py
@router.post("/upload")
async def upload_fit(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    background_tasks: BackgroundTasks = Depends(),
):
    file_bytes = await file.read()
    
    # CPU-bound parse in thread pool
    parsed = await asyncio.to_thread(parse_fit_file, file_bytes)
    
    if parsed is None or parsed["duration_secs"] < 600:
        raise HTTPException(422, detail={"error": "fit_parse_failed", "detail": "..."})
    
    # Upload raw FIT to Supabase Storage
    storage_path = f"fits/{user_id}/{file.filename}"
    await upload_to_storage(file_bytes, storage_path)
    
    # Persist ride row (TSS computed in background task)
    ride_id = await persist_ride_stub(user_id, parsed, storage_path)
    
    # Background task: compute TSS, update PMC, post debrief message
    background_tasks.add_task(process_ride_background, ride_id, user_id, parsed)
    
    return {"ride_id": ride_id, "status": "processing"}
```

**Background task pattern (D-15):** FastAPI `BackgroundTasks` is the correct choice over Supabase realtime for this use case. Supabase realtime would require a separate listener process; `BackgroundTasks` runs in-process after the response is sent, with access to the same app context. [ASSUMED: Supabase realtime requires separate setup]

### FIT Parse -> TSS Pipeline

```
1. parse_fit_file(bytes) -> {power_array, hr_array, duration_secs, avg_hr, avg_cadence}
2. Retrieve user's current FTP from profiles/rides history:
   - If estimate_ftp_from_rides returns confidence >= "medium": use that FTP
   - Otherwise: use placeholder FTP = 150W (beginner safe estimate; tagged in ftp_used column)
3. compute_tss(power_array, duration_secs, ftp) -> ToolResult
   - Returns None value if < 10 minutes (NP_MIN_DURATION_SECS = 600)
4. Load previous PMC state from pmc_history (most recent row for user)
5. update_pmc(prev_ctl, prev_atl, tss, days_of_data) -> ToolResult
6. INSERT INTO rides (user_id, tss, np_watts, intensity_factor, duration_secs, avg_hr, avg_cadence, ftp_used, ride_date, raw_fit_path)
7. INSERT INTO pmc_history (user_id, date, ctl, atl, tsb, tss_display_ready) ON CONFLICT UPDATE
8. Trigger ride debrief conversation (D-23)
```

**Cold-start TSS handling:** When FTP confidence is "insufficient_data", `compute_tss` still runs with the placeholder FTP (150W). The `ftp_used = 150.0` column documents this. TSS values computed with estimated FTP are approximate but allow PMC to start accumulating -- which is the goal.

---

## Adaptive Re-planning Logic

### Signal Detection (D-16, D-17)

```python
# Checked lazily on GET /chat/stream when conversation rehydrated, or via POST /sessions/{id}/missed

async def detect_signals(user_id: str) -> list[dict]:
    """Returns list of {type: "missed"|"underperformance", session_id, signal_tss_delta}"""
    signals = []
    
    # Missed session check: planned sessions past due with no matching ride
    overdue_sessions = await get_overdue_sessions(user_id, window_days=7)
    for session in overdue_sessions:
        # Check if a ride exists within ±1 day
        matching_ride = await find_ride_near_date(user_id, session.scheduled_date, tolerance_days=1)
        if not matching_ride:
            signals.append({"type": "missed", "session_id": session.id})
    
    # Underperformance check: rides where compliance_pct < 60
    recent_rides = await get_recent_rides(user_id, days=7)
    for ride in recent_rides:
        matched_session = await match_ride_to_session(ride)
        if matched_session:
            result = validate_session_vs_actual(
                planned={"tss": matched_session.planned_tss},
                actual={"tss": ride.tss}
            )
            if result.value["compliance_pct"] and result.value["compliance_pct"] < 60:
                signals.append({"type": "underperformance", "session_id": matched_session.id,
                                 "compliance_pct": result.value["compliance_pct"]})
    
    return signals
```

### Adaptation Decision Tree

```
signals = detect_signals(user_id)

len(signals) == 0:
  -> No adaptation needed

len(signals) == 1:
  -> MICRO-ADJUSTMENT (D-17)
  -> Adjust next 1-3 sessions inline (reduce duration/intensity)
  -> Log to adaptations table (scope="micro")
  -> Agent posts explanation in chat

len(signals) >= 2 AND all within 7-day window:
  -> MACRO RE-PLAN (D-18)
  -> Call progress_load with reduced weekly_capacity
  -> Re-generate session sequence for remaining weeks
  -> Check: sessions_shifted / total_upcoming_sessions <= 0.30 (D-19)
  -> If > 30% shift: MUST surface change summary to user before applying
  -> Log to adaptations table (scope="macro")
  -> Agent posts full change summary in chat
```

### 30% Shift Limit Enforcement (D-19, ADAPT-03)

```python
def check_shift_limit(before_sessions: list, after_sessions: list) -> dict:
    """
    Count sessions where scheduled_date changed by more than 1 day.
    Returns {shifted_count, total_upcoming, shift_pct, requires_user_confirmation}
    """
    shifted = sum(
        1 for before, after in zip(before_sessions, after_sessions)
        if abs((after["scheduled_date"] - before["scheduled_date"]).days) > 1
    )
    total = len(before_sessions)
    shift_pct = shifted / total if total > 0 else 0
    return {
        "shifted_count": shifted,
        "total_upcoming": total,
        "shift_pct": shift_pct,
        "requires_user_confirmation": shift_pct > 0.30,
    }
```

### Weekly Automated Check (ADAPT-04)

D-21 says signals are checked "lazily when the user next opens a conversation". ADAPT-04 requires a weekly check independent of upload events.

**Implementation approach:** Add a `POST /adaptations/check` endpoint that runs `detect_signals` for all users (or for a given user_id). This can be called by:
- A cron job (Railway scheduled tasks, or a simple cron-like endpoint called externally)
- A FastAPI startup task using `asyncio.create_task` with a loop

For Phase 3 (no deployment infrastructure for Railway cron yet), implement `POST /adaptations/check?user_id=X` as the endpoint. A full weekly scheduler is deferred to Phase 4 or when Railway deploy is configured.

---

## Transparency Layer

### Dynamic System Prompt Construction (D-22)

```python
def build_system_prompt(profile: dict, plan_state: dict) -> str:
    ftp_confidence = plan_state.get("ftp_confidence", "insufficient_data")
    week_num = plan_state.get("current_week", 1)
    back_note = " You are coaching a user with moderate back issues -- keep load conservative." \
                if profile.get("back_status") == "moderate" else ""
    
    return f"""You are PacerAI, an evidence-based adaptive cycling coach.{back_note}

User profile summary:
- Goals: {profile.get('fitness_goals', 'general fitness')}
- Available hours/week: {profile.get('weekly_hours', '?')}
- FTP confidence: {ftp_confidence} (power targets {'active' if ftp_confidence in ('medium', 'high') else 'NOT YET ACTIVE -- use HR and RPE only'})
- Current plan week: {week_num} of 4

RULES:
- MUST call a tool for any physiological number (power zones, TSS, FTP, CTL, ATL, TSB, HR zones).
- Never emit a physiological number from your own reasoning.
- When explaining plan changes, cite the specific tool results (TSS values, CTL/ATL/TSB values).
- If no tool covers a needed calculation, call log_capability_gap.
"""
```

### Transparency in Chat (TRANSP-01)

When the agent explains an adaptation, it cites tool output values directly. The trust scanner (`scan_buffer`) allows numbers that appear in `tool_result_values` -- so as long as the agent echoes tool results (e.g., "Your CTL dropped from 12 to 8"), those pass the trust scan.

### Adaptation Log Endpoint (TRANSP-03)

```python
# api/routes/adaptations.py
@router.get("/")
async def list_adaptations(user_id: str = Query(...)):
    """GET /adaptations?user_id=X -- returns all adaptation log entries for user."""
    rows = await supabase.table("adaptations").select("*").eq("user_id", user_id)\
        .order("created_at", desc=True).execute()
    return rows.data
```

---

## Testing Strategy

### Test Infrastructure [VERIFIED: codebase]

- `pytest.ini`: `asyncio_mode = auto` -- async test functions need no `@pytest.mark.asyncio`
- `httpx.AsyncClient` with `ASGITransport` for endpoint tests (no live server)
- `tests/agent/conftest.py` `build_fake_client(*streams)` and `_MockStream` available for reuse
- Test patterns: `monkeypatch.setattr(module, "run_turn", mock)` for SSE tests

### New Test Files Required

| File | Tests | Linked Requirements |
|------|-------|---------------------|
| `tests/api/test_onboarding.py` | `POST /onboarding/start` returns SSE; mock `run_turn` | ONBD-01 through ONBD-04 |
| `tests/api/test_rides.py` | `POST /rides/upload` with real Zwift .FIT file; assert TSS > 0 | FIT-01 through FIT-06 |
| `tests/agent/test_tools_phase3.py` | `save_profile` tool; `generate_plan` tool; TRUST-02 still passes | PLAN-01 through PLAN-06 |
| `tests/api/test_adaptations.py` | signal detection; micro/macro branch; 30% shift limit | ADAPT-01 through ADAPT-05 |
| `tests/api/test_adaptations.py` | `GET /adaptations` returns log; TRANSP-02 log written | TRANSP-01 through TRANSP-03 |

### Acceptance Test: Real .FIT File (FIT-06, D-13)

```python
# tests/api/test_rides.py
import pathlib

FIXTURE_PATH = pathlib.Path(__file__).parents[1] / "fixtures" / "sample_zwift.fit"

async def test_fit_upload_integration():
    """
    FIT-06 / D-13: Upload real Zwift .FIT file and assert:
    - HTTP 200 response with ride_id
    - TSS > 0 in the rides table
    - pmc_history row updated
    - No HTTP 422 (no parse error)
    """
    assert FIXTURE_PATH.exists(), f"Test fixture missing: {FIXTURE_PATH}"
    
    async with httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with open(FIXTURE_PATH, "rb") as f:
            response = await client.post(
                "/rides/upload",
                files={"file": ("sample_zwift.fit", f, "application/octet-stream")},
                data={"user_id": TEST_USER_ID},
            )
    
    assert response.status_code == 200
    body = response.json()
    assert "ride_id" in body
    
    # DB assertions require a Supabase test instance or mocked DB
    # For Phase 3: use monkeypatch on supabase client to capture inserts
```

**Note:** The test fixture `tests/fixtures/sample_zwift.fit` must be checked in. A Wave 0 task should acquire or generate this file. Options:
1. Download a sample FIT file from a public repository (garmin/fit-sdk has examples)
2. Export a Zwift ride if the developer has a Zwift account
3. Generate a synthetic .FIT file using `fitdecode` or the Garmin FIT SDK

### Existing Tests Must Stay Green

The `TRUST-02` import-time assertion in `agent/tools.py` will fail if the new tools are added to only one of `TOOL_REGISTRY` or `TOOL_SCHEMAS`. Every test that imports `agent.tools` will break. Add both entries atomically.

### Onboarding Interview Test (ONBD-01 through ONBD-04)

```python
# tests/api/test_onboarding.py
async def test_onboarding_multi_turn_mock(monkeypatch):
    """
    Verify POST /onboarding/start returns SSE stream.
    Use mock run_turn that simulates the interview sequence.
    """
    # Mock run_turn to yield a predefined interview sequence
    async def mock_interview(*args, **kwargs):
        yield {"event": "token", "data": {"text": "What are your fitness goals?"}}
        yield {"event": "tool_start", "data": {"name": "save_profile", "tool_use_id": "t1"}}
        yield {"event": "tool_result", "data": {"tool_use_id": "t1", "name": "save_profile", "value": '{"saved": true}'}}
        yield {"event": "done", "data": {}}
    
    monkeypatch.setattr(onboarding_module, "run_turn", mock_interview)
    ...
```

---

## Validation Architecture

### Test Framework [VERIFIED: codebase]

| Property | Value |
|----------|-------|
| Framework | pytest 9.1.1 + pytest-asyncio 1.4.0 |
| Config file | `pytest.ini` (exists; `asyncio_mode = auto`, `testpaths = tests`) |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ONBD-01 | Interview collects 6 required fields | unit | `pytest tests/api/test_onboarding.py -x` | No -- Wave 0 |
| ONBD-02 | back_status persisted and applied | unit | `pytest tests/api/test_onboarding.py::test_back_status_constraint -x` | No -- Wave 0 |
| ONBD-03 | Profile row inserted in DB | integration | `pytest tests/api/test_onboarding.py::test_profile_persisted -x` | No -- Wave 0 |
| ONBD-04 | Confirmation gate blocks early generate_plan | unit | `pytest tests/api/test_onboarding.py::test_confirmation_gate -x` | No -- Wave 0 |
| PLAN-01 | 4-week mesocycle generated | unit | `pytest tests/agent/test_tools_phase3.py::test_generate_plan -x` | No -- Wave 0 |
| PLAN-02 | Cold-start uses HR zones only | unit | `pytest tests/agent/test_tools_phase3.py::test_cold_start_hr_only -x` | No -- Wave 0 |
| PLAN-03 | Power targets absent when ftp_confidence=insufficient_data | unit | `pytest tests/agent/test_tools_phase3.py::test_power_targets_cold_start -x` | No -- Wave 0 |
| PLAN-04 | Each session has objective+structure+targets+duration | unit | `pytest tests/agent/test_tools_phase3.py::test_session_schema -x` | No -- Wave 0 |
| PLAN-05 | Back constraints applied in plan | unit | `pytest tests/agent/test_tools_phase3.py::test_back_constraints -x` | No -- Wave 0 |
| PLAN-06 | Trust-04: every number in plan traced to tool call | compliance | `pytest tests/agent/test_trust_corpus.py -x` | Exists (extend) |
| FIT-01 | Upload endpoint returns 200 | integration | `pytest tests/api/test_rides.py::test_upload_returns_200 -x` | No -- Wave 0 |
| FIT-02 | fitdecode with ErrorHandling.WARN | unit | `pytest tests/api/test_rides.py::test_fit_parse_warn -x` | No -- Wave 0 |
| FIT-03 | Missing HR/cadence handled gracefully | unit | `pytest tests/api/test_rides.py::test_missing_fields -x` | No -- Wave 0 |
| FIT-04 | TSS computed + PMC updated | integration | `pytest tests/api/test_rides.py::test_tss_computed -x` | No -- Wave 0 |
| FIT-05 | validate_session_vs_actual called | unit | `pytest tests/api/test_rides.py::test_session_compliance -x` | No -- Wave 0 |
| FIT-06 | Real Zwift .FIT acceptance test | integration | `pytest tests/api/test_rides.py::test_fit_upload_integration -x` | No -- Wave 0 |
| ADAPT-01 | Missed session detected | unit | `pytest tests/api/test_adaptations.py::test_missed_detection -x` | No -- Wave 0 |
| ADAPT-02 | Micro vs macro branch | unit | `pytest tests/api/test_adaptations.py::test_micro_macro_branch -x` | No -- Wave 0 |
| ADAPT-03 | 30% shift limit enforced | unit | `pytest tests/api/test_adaptations.py::test_shift_limit -x` | No -- Wave 0 |
| ADAPT-04 | Weekly check endpoint functional | unit | `pytest tests/api/test_adaptations.py::test_weekly_check -x` | No -- Wave 0 |
| ADAPT-05 | Intensity decided via tool results | unit | `pytest tests/api/test_adaptations.py::test_intensity_from_tools -x` | No -- Wave 0 |
| TRANSP-01 | Agent cites tool values in chat | compliance | extend trust corpus | Exists (extend) |
| TRANSP-02 | Adaptation log persisted | unit | `pytest tests/api/test_adaptations.py::test_log_persisted -x` | No -- Wave 0 |
| TRANSP-03 | GET /adaptations returns log | unit | `pytest tests/api/test_adaptations.py::test_get_adaptations -x` | No -- Wave 0 |

### Wave 0 Gaps

- [ ] `tests/api/__init__.py` -- init file for new api test package
- [ ] `tests/api/conftest.py` -- shared fixtures: test user_id, mock supabase client, mock background tasks
- [ ] `tests/api/test_onboarding.py` -- ONBD-01 through ONBD-04
- [ ] `tests/api/test_rides.py` -- FIT-01 through FIT-06
- [ ] `tests/api/test_adaptations.py` -- ADAPT-01 through ADAPT-05, TRANSP-01 through TRANSP-03
- [ ] `tests/agent/test_tools_phase3.py` -- PLAN-01 through PLAN-06, new tools
- [ ] `tests/fixtures/sample_zwift.fit` -- real Zwift .FIT file for FIT-06 acceptance test
- [ ] `fitdecode==0.11.0` added to `requirements.txt`

---

## Key Risks and Open Questions

### Risk 1: TSS Without FTP (Cold-Start)

`compute_tss` requires `ftp > 0`. Cold-start users have no FTP. Using a placeholder (150W) produces TSS values that are proportionally wrong but directionally correct for PMC initialization.

**Mitigation:** Store `ftp_used` in the `rides` table. When FTP is later estimated, backfill TSS values. Add a `backfill_tss` endpoint for Phase 4.

### Risk 2: TRUST-02 Assertion at Import

Adding `save_profile` or `generate_plan` to only one of `TOOL_REGISTRY`/`TOOL_SCHEMAS` will raise `RuntimeError` at import time, breaking ALL tests. This is a good invariant but requires careful atomic changes.

**Mitigation:** Both additions must be in the same commit. Tests should include a `test_trust02_passes_after_new_tools` check.

### Risk 3: fitdecode Field Names for Zwift

The exact field name for power in Zwift .FIT files is `"power"` [ASSUMED]. If it differs (e.g., `"enhanced_power"` for some head units), the pipeline silently gets all zeros.

**Mitigation:** The FIT-06 acceptance test with a real Zwift file will catch this immediately. Print/log the first 5 record field names during parsing for debugging.

**Concrete verification:** After installing fitdecode, run:
```python
import fitdecode, io
with fitdecode.FitReader(io.BytesIO(fit_bytes)) as r:
    for frame in r:
        if isinstance(frame, fitdecode.FitDataMessage) and frame.name == 'record':
            print(frame.fields)
            break
```

### Risk 4: Supabase Client Lifecycle in Background Tasks

The `_supabase_client` singleton in `capability_gap.py` is module-level. Background tasks run after the request is complete. If the request handler also uses the same singleton, there's no contention issue -- `asyncio` is single-threaded. But if `asyncio.to_thread` is used for sync code that also tries to use the async client, there will be an event loop conflict.

**Mitigation:** Only use `asyncio.to_thread` for the sync `parse_fit_file` function (pure numpy). All Supabase client operations stay in the main event loop with `await`. The thread only does CPU-bound computation.

### Risk 5: Conversation Persistence Adds Latency to Every Turn

Phase 3 adds DB reads (load last 20 messages) and writes (persist new messages) to every `run_turn` call. This adds ~50-100ms of Supabase latency.

**Mitigation:** Use a FastAPI lifespan singleton for the Supabase client (not a per-request `acreate_client`). The `log_capability_gap.py` module-level singleton is the pattern to extend.

### Open Question 1: fitdecode async + GIL

The `FitReader` context manager holds a file handle. Running it in `asyncio.to_thread` releases the GIL during I/O waits but not during CPU computation. For typical Zwift rides (1-2 hours at 1 Hz = 3600-7200 records), parsing takes ~50-200ms of pure Python CPU time. This is acceptable for Phase 3 without chunking.

**Answer:** Use `asyncio.to_thread(parse_fit_file, file_bytes)` where `parse_fit_file` opens and closes `FitReader` within the thread. No chunking needed for rides under ~2 hours.

### Open Question 2: Supabase Realtime vs FastAPI BackgroundTasks

D-15 decides FastAPI `BackgroundTasks`. This is correct: Supabase realtime requires a separate listener process and has connection limits in the free tier. `BackgroundTasks` runs in-process, has access to app state, and requires no additional infrastructure.

**Answer:** Use `FastAPI.BackgroundTasks`. The adaptation trigger is `background_tasks.add_task(process_ride_background, ride_id, user_id, parsed)`.

---

## Package Legitimacy Audit

> fitdecode is the only new external package. SQLAlchemy and asyncpg are NOT needed -- Phase 3 uses supabase-py-async (already installed) for all DB operations, not direct asyncpg/SQLAlchemy.

| Package | Registry | Status | Source Repo | Verdict | Disposition |
|---------|----------|--------|-------------|---------|-------------|
| fitdecode 0.11.0 | PyPI | Latest (Aug 2025) | github.com/polyvertex/fitdecode | SUS (unknown downloads via checker) | Approved -- see note |
| supabase 2.31.0 | PyPI | Already installed | github.com/supabase-community/supabase-py | OK (already in use) | Approved |

**fitdecode note:** The SUS verdict is a false positive from the legitimacy checker's PyPI download data unavailability. fitdecode is the package explicitly recommended in CLAUDE.md over fitparse (which is marked abandoned). The CLAUDE.md directive reads: "fitdecode (0.10.x) -- .FIT file parsing; NOT fitparse (inactive)". This is the project's own authoritative decision. [CITED: .claude/CLAUDE.md]

**Packages removed due to SLOP verdict:** None.

**SQLAlchemy/asyncpg not needed for Phase 3:** The supabase-py-async client already handles all DB operations via the Supabase REST API. Raw asyncpg/SQLAlchemy would require a direct Postgres connection and Alembic for migrations. Phase 3 continues the Supabase client pattern established in Phase 1/2. Alembic migrations are replaced by Supabase migration files (already established with `supabase/migrations/0001_initial_schema.sql`).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| fitdecode | FIT-02, FIT-03, FIT-04 | Not installed | 0.11.0 on PyPI | None -- blocking |
| python-multipart | POST /rides/upload file upload | In requirements.txt | latest | None |
| FastAPI | All endpoints | Installed | 0.115.14 | N/A |
| supabase | All DB operations | Installed | 2.31.0 | None |
| numpy | compute_tss, update_pmc | Installed | 2.4.6 | None |
| scipy | estimate_ftp_from_rides | Installed | 1.17.1 | None |
| anthropic SDK | run_turn | Installed (pinned to 0.67.*) | 0.67.x | None |
| Supabase project | DB writes | Not checked in research | Remote | Local with supabase CLI |

**Missing dependencies with no fallback:**
- `fitdecode==0.11.0` must be added to `requirements.txt` before Wave 1

---

## Architecture Patterns

### System Architecture Diagram

```
User (curl/test)
     |
     v
POST /onboarding/start -----> run_turn() -----> Anthropic API (SSE)
POST /chat/stream             |                  |
                              | tool_use blocks  |
                              v                  |
                         dispatch_tool()         |
                              |                  |
                    +---------+----------+       |
                    |                   |        |
               save_profile()     generate_plan() |
               progress_load()    calculate_hr_zones()
                    |                   |
                    v                   v
              Supabase DB          ToolResult JSON
              (profiles,           (returned to Claude)
               plans, sessions)

POST /rides/upload
     |
     v
parse_fit_file() [asyncio.to_thread]
     |
     v
BackgroundTasks.add_task(process_ride_background)
     |
     +---> compute_tss()
     +---> update_pmc()
     +---> validate_session_vs_actual()
     +---> Supabase DB (rides, pmc_history)
     +---> run_turn() for ride_debrief conversation (SSE to no-one for now; persisted)
```

### Project Structure (Phase 3 Additions)

```
api/
├── routes/
│   ├── chat.py              # Existing; upgraded to load messages from DB
│   ├── onboarding.py        # NEW: POST /onboarding/start
│   ├── rides.py             # NEW: POST /rides/upload
│   └── adaptations.py       # NEW: GET/POST /adaptations
sports_science/
│   ├── plan.py              # NEW: generate_plan() function
│   └── profile.py           # NEW: save_profile() async function
supabase/migrations/
│   └── 0002_phase3_schema.sql  # NEW: 2 new tables + column additions
tests/
├── api/
│   ├── __init__.py          # NEW
│   ├── conftest.py          # NEW: shared fixtures
│   ├── test_onboarding.py   # NEW
│   ├── test_rides.py        # NEW
│   └── test_adaptations.py  # NEW
├── agent/
│   └── test_tools_phase3.py # NEW
└── fixtures/
    └── sample_zwift.fit     # NEW: real FIT file for acceptance test
```

---

## Sources

### Primary (HIGH confidence)
- `/Users/christianmoore/ai/pacer-ai/agent/loop.py` -- run_turn implementation, SSE event schema, tool dispatch pattern
- `/Users/christianmoore/ai/pacer-ai/agent/tools.py` -- TOOL_REGISTRY, TOOL_SCHEMAS, TRUST-02 assertion
- `/Users/christianmoore/ai/pacer-ai/agent/trust.py` -- scan_buffer, handle_violation, PHYSIO_PATTERN
- `/Users/christianmoore/ai/pacer-ai/sports_science/*.py` -- all 8 tool implementations
- `/Users/christianmoore/ai/pacer-ai/supabase/migrations/0001_initial_schema.sql` -- existing DB schema
- `/Users/christianmoore/ai/pacer-ai/.planning/phases/03-coaching-loop/03-CONTEXT.md` -- locked decisions D-01 through D-25
- `pip index versions fitdecode` -- PyPI registry confirmation of 0.11.0
- `.claude/CLAUDE.md` -- tech stack decisions, fitdecode mandate, stack constraints

### Secondary (MEDIUM confidence)
- `pytest.ini` -- asyncio_mode=auto, testpaths
- `tests/agent/conftest.py` -- _MockStream, build_fake_client patterns
- `tests/agent/test_sse.py` -- test patterns for SSE endpoints

### Tertiary (ASSUMED -- training knowledge)
- fitdecode `FitReader` API details (`frame.get_value()`, `ErrorHandling.WARN`, field names `power`/`heart_rate`/`cadence`)
- Zwift .FIT field naming convention (`power` not `enhanced_power`)
- FastAPI BackgroundTasks vs Supabase realtime tradeoff reasoning

---

## Metadata

**Confidence breakdown:**
- Phase 2 foundation: HIGH -- read directly from codebase
- DB schema gaps: HIGH -- read directly from migration SQL
- New tool signatures: HIGH -- derived from locked decisions + existing ToolResult pattern
- fitdecode API: ASSUMED -- library not installed; training knowledge
- Zwift field names: ASSUMED -- no real FIT file available during research

**Research date:** 2026-06-20
**Valid until:** 2026-07-20 (fitdecode docs may change)

---

## RESEARCH COMPLETE
