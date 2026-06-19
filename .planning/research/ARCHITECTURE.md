# Architecture Research: PacerAI

**Researched:** 2026-06-19
**Overall confidence:** MEDIUM (tool use loop: MEDIUM via context7/official docs; PMC formulas: LOW via web; ZWO format: LOW via community reference)

---

## System Overview

PacerAI is a three-tier web application: React PWA (Vercel) talking to a FastAPI backend (Railway) backed by Supabase Postgres. The dominant architectural constraint is the trust model: the LLM (Claude via Anthropic API) makes all coaching judgements but is forbidden from emitting physiological numbers. Every number comes from a deterministic, unit-tested sports-science tool library. This constraint shapes every boundary.

```
Browser (React PWA)
    |-- REST (mutations, file upload, session CRUD)
    |-- SSE  (streaming chat responses)
    v
FastAPI (Railway)
    |-- anthropic.Anthropic().messages.create() -- Claude agent loop
    |-- sports_science/  (pure Python tool library, called by agent)
    |-- fitparse  (FIT file parsing)
    |-- google-auth-oauthlib  (Calendar sync)
    v
Supabase (Postgres + Storage)
    |-- Tables: users, profiles, sessions, rides, pmc_history, capability_gaps
    |-- Storage bucket: fit-files (raw uploads)
```

---

## Components

### 1. React PWA Frontend (Vite + Tailwind + shadcn/ui)

**Responsibility:** All user interaction. Renders screens, manages local UI state, streams chat display.

**Screens:** Onboarding/Interview, Today/Home, Agenda, Session Detail, History, Chat, During-Session (stepper + timer).

**Communication pattern:**
- REST (`fetch` / TanStack Query) for reads and mutations (profile load, session list, FIT upload, ZWO download)
- `EventSource` for streaming chat (SSE from `/chat/stream`)
- No WebSocket needed; SSE is unidirectional and sufficient for agent response streaming

**PWA requirements:** `vite-plugin-pwa` with service worker, `manifest.json`, `apple-mobile-web-app-capable` meta, works offline for During-Session view (cached plan data). iOS Safari tested on every release.

**Trust model surface:** Frontend never renders raw numbers from its own logic. All physiological values (zones, TSS, CTL/ATL/TSB, FTP estimate) arrive from the backend as strings already computed by the tool library.

---

### 2. FastAPI Backend (Railway, Python 3.12+)

**Responsibility:** API gateway, agent orchestration, file processing, external integrations.

**Key modules:**

| Module | Role |
|--------|------|
| `api/chat.py` | SSE streaming endpoint; runs the agent tool loop |
| `api/rides.py` | FIT upload, parse, compute metrics, update PMC |
| `api/sessions.py` | Plan CRUD, ZWO export, session completion |
| `api/calendar.py` | Google Calendar OAuth2 push/sync |
| `agent/loop.py` | Core agent loop (stop_reason handler) |
| `agent/tools.py` | Tool registry: wraps sports_science functions as Anthropic tool schemas |
| `sports_science/` | Pure Python tool library (zero Anthropic imports) |
| `sports_science/gaps.py` | Capability-gap logger |

**Why FastAPI over Node:** `fitparse` and `numpy`/`scipy` are Python-native; no JS equivalent with the same maturity. FastAPI async matches Railway's single-process deployment.

---

### 3. Sports-Science Tool Library (`sports_science/`)

**Responsibility:** The ONLY source of physiological numbers. Pure Python, deterministic, no LLM dependency.

**Contract:** Every function returns a `ToolResult` typed dict:
```python
{
  "value": <number or dict>,
  "unit": str,
  "methodology": str,   # e.g. "Coggan 2010 7-zone model"
  "inputs": dict        # echo of inputs for auditability
}
```

**Functions exposed as Anthropic tools:**

| Tool name | Input | Output |
|-----------|-------|--------|
| `calculate_power_zones` | ftp_watts | zones dict (W ranges) + methodology |
| `calculate_hr_zones` | lthr_bpm, method | zones dict + methodology |
| `estimate_ftp_from_rides` | ride_list (power arrays) | ftp_estimate + confidence + method |
| `compute_tss` | np_watts, if_val, duration_secs, ftp | tss float + methodology |
| `compute_np_if` | power_array_watts, ftp | {np, if_} + methodology |
| `update_pmc` | current_ctl, current_atl, tss | {new_ctl, new_atl, tsb} + formulas |
| `progress_load` | current_ctl, weeks, ramp_rate | target_tss_week + safety_check |
| `validate_session_vs_actual` | planned_session, actual_ride | delta_dict + assessment |

**Trust enforcement:** `agent/tools.py` builds the Anthropic `tools` array exclusively from this library. No raw Python callable can be added to the tool list without a corresponding `ToolResult`-typed function in `sports_science/`. Code review checklist includes: "does this tool call return methodology?" and "is any number in this response from a non-tool source?"

**Capability-gap logger:** When the agent needs a calculation with no tool, it calls `log_capability_gap(description, context)` which writes a structured JSON row to the `capability_gaps` table and returns a sentinel `{"error": "NO_TOOL", "gap": description}`. The agent is instructed (system prompt) to surface this to the user rather than fabricate a number.

---

### 4. Agent Tool-Calling Loop (`agent/loop.py`)

**Pattern:** Multi-turn loop using the raw Anthropic Python SDK (not the Agent SDK -- we need explicit control for streaming and gap logging).

```python
async def run_agent_turn(messages: list, user_id: str) -> AsyncIterator[str]:
    """Yields SSE-formatted chunks: text tokens and structured events."""
    tools = build_tool_list()          # from sports_science registry
    system = load_system_prompt()      # coaching persona + trust rules

    while True:
        response = await client.messages.create(
            model="claude-opus-4-5",   # or sonnet-4-5 for cost
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
        )

        # Stream any text blocks to client immediately
        for block in response.content:
            if block.type == "text":
                yield sse_chunk(block.text)

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = await dispatch_tool(block.name, block.input, user_id)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })
                    # Yield a structured event so UI can show "Calculating zones..."
                    yield sse_event("tool_called", {"tool": block.name, "result": result})

            # Append assistant turn + tool results, loop
            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})
```

**Key decisions:**
- Single-turn vs multi-turn: Multi-turn. The coaching agent routinely needs 2-4 tool calls per response (e.g. estimate FTP, compute zones, compute TSS for a proposed session, check load progression).
- Streaming: We stream text blocks as they arrive between tool calls. Tool calls are non-streaming (we wait for the full tool_use block before dispatching). This gives the user visible progress during long agent turns.
- `disable_parallel_tool_use: false`: Allow Claude to call multiple tools in one turn where possible (e.g. compute_np_if + compute_tss can be parallel). The dispatcher handles parallel execution with `asyncio.gather`.

---

### 5. FIT File Pipeline

```
POST /rides/upload (multipart)
    --> save raw bytes to Supabase Storage (fit-files/{user_id}/{filename})
    --> fitparse.FitFile(bytes_io).get_messages("record")
        --> extract: timestamp, power, heart_rate, cadence, speed
    --> compute_np_if(power_array, ftp)  [tool call]
    --> compute_tss(np, if_, duration, ftp)  [tool call]
    --> INSERT INTO rides (user_id, session_id, tss, np_watts, if_val, ...)
    --> update_pmc(ctl, atl, tss)  [tool call]
    --> UPDATE pmc_history for the ride date
    --> validate_session_vs_actual(planned, actual)  [tool call]
    --> PATCH sessions SET status='completed', delta=...
    --> trigger adaptive re-plan check (async task)
```

**Adaptive re-plan trigger:** After PMC update, if TSB or load delta exceeds threshold (configurable), enqueue a re-plan task. The re-plan task calls the agent with a system message: "User has uploaded a ride. PMC updated. Assess and adapt the next 7 days." Agent uses update_pmc + progress_load + validate_session_vs_actual to propose changes, which are written to the sessions table after agent confirms.

---

### 6. PMC Update Propagation

**Formula (Banister EWMA):**
```
CTL(t) = CTL(t-1) * exp(-1/42) + TSS(t) * (1 - exp(-1/42))
ATL(t) = ATL(t-1) * exp(-1/7)  + TSS(t) * (1 - exp(-1/7))
TSB(t) = CTL(t-1) - ATL(t-1)   # prior day's values = "form today"
```

**Update strategy:** Store one `pmc_history` row per day. On FIT upload for date D, recompute CTL/ATL forward from D to today (typically 0-7 rows to update). The `update_pmc` tool handles one-day increment; the pipeline calls it in a loop for any gap days.

**Re-plan signals the agent acts on:**
- TSB < -30: excessive fatigue; agent should reduce next session intensity or add rest day
- TSB > +25 for 3+ days: detraining; agent should increase load
- Session IF deviated > 15% from plan: recalibrate FTP estimate

---

### 7. Google Calendar Sync Service

**Pattern:** OAuth2 flow (web server flow) via `google-auth-oauthlib`. Tokens stored encrypted in Supabase (`users.google_tokens` jsonb column, encrypted at application layer with Fernet key from env).

```
POST /calendar/connect  --> redirect to Google OAuth consent
GET  /calendar/callback --> exchange code, store tokens
POST /calendar/push     --> for each upcoming session, create/update Google Calendar event
PATCH /sessions/{id}    --> on session edit, update corresponding calendar event_id
```

**Calendar event fields:** title ("PacerAI: Zone 2 Endurance 60min"), description (session targets, RPE, TSS), start/end datetime, color coding by zone. Stores `google_event_id` in sessions table for future updates/deletions.

---

### 8. ZWO Export Generator

**Pattern:** Pure Python function in `export/zwo.py`. Takes a `Session` model, returns XML string.

```xml
<workout_file>
  <name>Zone 2 Endurance</name>
  <sportType>bike</sportType>
  <workout>
    <Warmup Duration="600" PowerLow="0.45" PowerHigh="0.65" />
    <SteadyState Duration="2400" Power="0.65" Cadence="85" />
    <Cooldown Duration="300" PowerLow="0.65" PowerHigh="0.40" />
  </workout>
</workout_file>
```

Power values are FTP fractions derived from the tool-library zone boundaries. The ZWO generator does NOT call Claude; it is a pure data transformation from a `Session` model to XML. FTP fraction = session_target_watts / user_ftp_watts.

---

## API Design

### Routing

| Method | Path | Protocol | Purpose |
|--------|------|----------|---------|
| POST | `/chat/message` | REST | Send user message, get conversation_id |
| GET | `/chat/stream/{conv_id}` | SSE | Stream agent response for a conversation turn |
| POST | `/rides/upload` | REST (multipart) | Upload .FIT file |
| GET | `/sessions` | REST | List upcoming sessions |
| GET | `/sessions/{id}/export/zwo` | REST | Download .zwo file |
| POST | `/calendar/push` | REST | Push sessions to Google Calendar |
| GET | `/profile` | REST | Get user profile + PMC summary |
| PATCH | `/profile` | REST | Update profile fields |

### Chat protocol decision: REST + SSE (not WebSocket)

- **REST POST /chat/message** initiates a turn, returns `{conversation_id, message_id}`. Stores user message in DB.
- **SSE GET /chat/stream/{conv_id}** streams the agent response. Client connects after POST, receives text chunks + structured tool events.
- **Why not WebSocket:** The chat is turn-based (user sends, agent responds). SSE is unidirectional server-to-client which is exactly the shape needed. SSE supports HTTP/2 multiplexing, auto-reconnect, and event IDs without the complexity of WebSocket lifecycle management. WebSocket adds nothing here.
- **Why not pure REST polling:** Unacceptable latency for streaming agent responses that take 5-15 seconds with multiple tool calls.

### SSE event types

```
data: {"type": "text_chunk", "content": "Your Zone 2 target is"}
data: {"type": "tool_called", "tool": "calculate_power_zones", "result": {...}}
data: {"type": "text_chunk", "content": " 140-165 watts based on your FTP."}
data: {"type": "done", "message_id": "msg_123"}
data: {"type": "error", "code": "TOOL_UNAVAILABLE", "gap": "..."}
```

The `tool_called` events let the frontend show "Calculating zones..." skeleton cards while the agent is mid-loop.

---

## Database Schema (sketch)

```sql
-- Core user record (Supabase Auth handles auth; this extends it)
CREATE TABLE users (
  id          uuid PRIMARY KEY REFERENCES auth.users,
  email       text NOT NULL,
  created_at  timestamptz DEFAULT now(),
  google_tokens jsonb  -- encrypted; null if calendar not connected
);

-- Physiological and training profile
CREATE TABLE profiles (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES users NOT NULL UNIQUE,
  ftp_watts       int,               -- null until estimated or set
  lthr_bpm        int,               -- null until known
  weight_kg       numeric(5,1),
  height_cm       int,
  back_injury     boolean DEFAULT false,
  fitness_level   text,              -- 'beginner' | 'returning' | 'trained'
  weekly_hours    numeric(4,1),      -- available training hours
  interview_done  boolean DEFAULT false,
  updated_at      timestamptz DEFAULT now()
);

-- Planned sessions (the training plan)
CREATE TABLE sessions (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES users NOT NULL,
  date            date NOT NULL,
  title           text NOT NULL,
  description     text,
  duration_mins   int,
  target_tss      numeric(6,1),
  target_if       numeric(4,2),
  zone_primary    int,               -- 1-7 Coggan zone
  rpe_target      int,               -- 1-10 for cold-start sessions
  status          text DEFAULT 'planned',  -- planned|completed|missed|skipped
  google_event_id text,
  zwo_xml         text,              -- cached ZWO export
  ride_id         uuid REFERENCES rides,  -- linked actual ride when completed
  created_at      timestamptz DEFAULT now(),
  updated_at      timestamptz DEFAULT now()
);

-- Actual rides (from FIT file ingestion)
CREATE TABLE rides (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         uuid REFERENCES users NOT NULL,
  recorded_at     timestamptz NOT NULL,
  duration_secs   int,
  distance_km     numeric(8,2),
  tss             numeric(6,1),
  np_watts        int,
  avg_power_watts int,
  if_val          numeric(4,2),
  avg_hr_bpm      int,
  avg_cadence     int,
  fit_storage_path text,             -- Supabase Storage path
  ftp_at_time     int,               -- FTP used for computations
  created_at      timestamptz DEFAULT now()
);

-- Daily PMC state (one row per user per day)
CREATE TABLE pmc_history (
  id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id   uuid REFERENCES users NOT NULL,
  date      date NOT NULL,
  ctl       numeric(6,2) DEFAULT 0,
  atl       numeric(6,2) DEFAULT 0,
  tsb       numeric(6,2) DEFAULT 0,
  tss_day   numeric(6,1) DEFAULT 0,  -- TSS contributed on this day
  UNIQUE (user_id, date)
);

-- Conversation history (agent context)
CREATE TABLE conversations (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES users NOT NULL,
  created_at  timestamptz DEFAULT now()
);

CREATE TABLE messages (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid REFERENCES conversations NOT NULL,
  role            text NOT NULL,  -- 'user' | 'assistant'
  content         jsonb NOT NULL, -- Anthropic content block array
  created_at      timestamptz DEFAULT now()
);

-- Runtime capability-gap log (application-level, not GSD planning)
CREATE TABLE capability_gaps (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id     uuid REFERENCES users,
  description text NOT NULL,
  context     jsonb,
  created_at  timestamptz DEFAULT now()
);
```

**Indexes:** `(user_id, date)` on `pmc_history` and `sessions`; `conversation_id` on `messages`; `user_id` on `rides`.

**Row-level security:** All tables have RLS policies: `user_id = auth.uid()`. Supabase Auth manages JWTs. FastAPI validates JWT via `supabase-py` auth helper on every request.

---

## Data Flow

### 1. Chat turn (primary flow)

```
User types message
  --> POST /chat/message {content, conversation_id}
  --> FastAPI stores user message in messages table
  --> Returns {conversation_id, message_id}

Client connects EventSource to GET /chat/stream/{conv_id}
  --> FastAPI loads conversation history from messages table
  --> Starts agent loop (agent/loop.py)
      Loop iteration:
        --> client.messages.create(messages=history, tools=tool_registry)
        --> if stop_reason == "tool_use":
              for each tool_use block:
                dispatch to sports_science.{tool_name}(**input)
                yield SSE: {"type": "tool_called", ...}
              append tool_results to messages, continue loop
        --> if stop_reason == "end_turn":
              yield SSE: {"type": "text_chunk", ...} for each text block
              yield SSE: {"type": "done"}
              store assistant message in DB
              break
```

### 2. FIT upload flow

```
User selects .FIT file
  --> POST /rides/upload (multipart/form-data)
  --> FastAPI:
      1. Save to Supabase Storage
      2. fitparse.FitFile --> power[], hr[], cadence[], duration
      3. compute_np_if(power, ftp) --> {np, if_}  [tool lib]
      4. compute_tss(np, if_, duration, ftp) --> tss  [tool lib]
      5. INSERT rides row
      6. Load pmc_history for yesterday
      7. update_pmc(ctl, atl, tss) --> {new_ctl, new_atl, tsb}  [tool lib]
      8. UPSERT pmc_history for ride date
      9. validate_session_vs_actual(planned, actual) --> delta  [tool lib]
      10. PATCH session status='completed', delta stored
      11. Queue adaptive re-plan check if delta significant
  --> Returns {ride_id, tss, np, if_, tsb}

[Async] Re-plan check:
  --> If TSB or performance delta exceeds threshold:
      --> Run agent loop with re-plan system message
      --> Agent calls progress_load, update_pmc, validate_session_vs_actual
      --> Agent proposes session modifications
      --> Write proposed changes to sessions table
      --> Notify user via next chat response or push notification
```

### 3. ZWO export

```
GET /sessions/{id}/export/zwo
  --> Load session from DB (has target power zones, duration, structure)
  --> export/zwo.py: pure XML generation from session model
  --> Power fraction = target_watts / user_ftp  (no LLM)
  --> Return XML with Content-Disposition: attachment; filename=session.zwo
```

### 4. Calendar push

```
POST /calendar/push {session_ids: [...]}
  --> For each session_id:
      Load session
      Google Calendar API: events.insert() or events.patch()
      Store google_event_id in sessions table
  --> Return {pushed: N, errors: [...]}
```

---

## Build Order Implications

The trust model creates a strict dependency graph. Build in this order:

**Layer 0 (foundation, no dependencies):**
- Sports-science tool library + unit tests
- Database schema + migrations
- Supabase project setup (RLS, storage bucket)

**Layer 1 (requires Layer 0):**
- Agent tool registry (wraps Layer 0 functions as Anthropic tool schemas)
- FIT file parser pipeline (requires DB schema + tool library)
- Agent loop (requires tool registry)

**Layer 2 (requires Layer 1):**
- FastAPI chat endpoint with SSE streaming (requires agent loop)
- FastAPI rides endpoint (requires FIT pipeline)
- FastAPI sessions CRUD (requires DB)

**Layer 3 (requires Layer 2):**
- React PWA: onboarding interview screen (requires chat endpoint)
- React PWA: Today/Agenda screens (requires sessions endpoint)
- React PWA: FIT upload flow (requires rides endpoint)

**Layer 4 (independent, can overlap Layer 3):**
- ZWO export (pure data transformation, only needs sessions model)
- Google Calendar sync (separate OAuth flow, needs sessions model)
- During-Session view (needs sessions model + client-side timer only)

**Rationale:** The tool library must be complete and tested before the agent is wired up. An untested tool returning wrong numbers violates the trust model from day one. The agent loop must be proven (via unit tests with mocked API) before the UI is built on top of it. Calendar and ZWO are independent features that can be built in any order after the core plan model exists.

---

## Trust Model Enforcement Architecture

The trust model is enforced at three levels:

**1. Code boundary:** `sports_science/` has zero Anthropic imports. `agent/tools.py` has zero sports-science logic -- it only maps function names to their schemas and dispatches calls. No path from agent to a number that bypasses the tool library can exist.

**2. Tool schema:** Every tool in the Anthropic `tools` array is generated by `build_tool_list()` which iterates `sports_science.REGISTRY` (a dict of `{name: (fn, schema)}`). Adding a tool requires adding to the registry, which requires a unit-tested function with `ToolResult` return type.

**3. System prompt:** The system prompt includes explicit instructions: "You MUST NOT emit any watts, zone boundaries, TSS, CTL, ATL, TSB, IF, or FTP values from your own knowledge. Call the appropriate tool. If no tool exists, call log_capability_gap and inform the user."

**4. Capability-gap as last resort:** `log_capability_gap` is itself a tool in the registry. If Claude encounters a needed calculation with no tool, it calls this tool which returns `{"status": "logged", "message": "I don't have a tool for this calculation yet. I've logged it for the developer. For now, I'll use [fallback approach without numbers]."}`. This prevents both fabrication and silent failure.

**Audit surface:** Every tool call is logged (tool name + inputs + result) in the `messages` table as part of the conversation content blocks. A developer can query any conversation and see exactly which tools were called and what they returned.

---

*Sources: [Anthropic tool use docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/build-a-tool-using-agent), [FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/), [ZWO format reference](https://github.com/h4l/zwift-workout-file-reference), [TrainingPeaks PMC science](https://www.trainingpeaks.com/learn/articles/the-science-of-the-performance-manager/), [Banister model](https://fellrnr.com/wiki/Modeling_Human_Performance)*
