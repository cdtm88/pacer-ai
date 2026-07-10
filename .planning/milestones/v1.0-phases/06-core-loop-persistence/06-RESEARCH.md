# Phase 6: Core Loop Persistence - Research

**Researched:** 2026-07-03
**Domain:** Backend data persistence, PMC time-series correctness, adaptive-scheduling idempotency (FastAPI + Supabase Postgres + Anthropic tool-dispatch architecture)
**Confidence:** MEDIUM-HIGH — every defect claim below is code-verified against the current repo (grep/read, not training-data guesses). The *design* for adaptation idempotency and the macro-replan confirm flow is a recommendation (tagged `[ASSUMED]`) since no prior art exists in the codebase for it.

## Summary

Phase 6 is a correctness-repair phase, not a new-feature phase: almost every defect is already pinpointed by `.planning/research/APP-REVIEW-260703.md`, and this research adds exact file/line verification, one **previously undocumented schema bug** (`pmc_history` is missing the `tss` and `days_of_data` columns the code already writes to — every PMC upsert has been silently failing since Phase 3), one **previously undocumented CHECK-constraint bug** (`sessions.status` does not allow `'missed'`, so the existing `/adaptations/sessions/{id}/missed` endpoint would 500 the moment it is actually exercised against a real DB), and a concrete architectural answer for where plan persistence should hook in.

The single most important design decision: **`generate_plan` and `update_pmc` must stay pure, unit-tested, DB-free functions** (this is an explicit, already-locked docstring invariant in `plan.py` and is how `tests/sports_science/` is structured). Persistence for both must happen in an **orchestration layer above** the pure tool — for `generate_plan` that layer already exists and already does per-tool-name special-casing: `agent/tools.py::dispatch_tool`, which since commit `b3fcf39` (260702-wev) injects `user_id` into `save_profile`/`generate_plan` inputs before dispatch. The same function is the correct place to add a `generate_plan`-specific post-processing step that persists `plans` + `sessions` rows and rewrites `result.value["plan_id"]` before the tool result goes back to Claude. This works for both the onboarding flow (`onboarding.py`, gated by the existing "Here is what I have" approval per D-03/ONBD-04) and the general coaching chat flow (`chat.py`), because both funnel through the same `dispatch_tool`. No new "confirm plan" endpoint is needed for the *initial* plan — the existing summary-approval gate already is that confirmation. A **new** confirm endpoint IS needed for macro-replan (`D-19` dead end), because that is a genuinely two-phase flow (propose, then a separate user action to apply).

For PMC, the correct fix is **not** to patch the existing single-EWMA-step-per-upload code — it is architecturally unable to represent gap-day decay or same-day summation no matter how it's patched. The recommended design is a **recompute-from-scratch day-series builder**: on every ride upload, rebuild the user's entire canonical daily-TSS series (grouped by `ride_date`, summed for same-day rides) from their earliest ride to today, walk it day-by-day through the existing pure `update_pmc` function (incrementing `days_of_data` once per **calendar day**, not per upload), and bulk-upsert the resulting `pmc_history` rows. This is O(total ride-days) which is trivially cheap for a single-user MVP (bounded to low thousands of rows even after years of daily riding) and is naturally idempotent, naturally dedups via the FIT content-hash gate (a rejected duplicate never enters the day-sum), and naturally decays through empty days (every day in the range gets an `update_pmc` step, TSS=0 when no ride occurred).

**Primary recommendation:** Keep `sports_science/plan.py::generate_plan` and `sports_science/pmc.py::update_pmc` pure and untouched; add all persistence, day-series orchestration, and idempotency bookkeeping in a new backend orchestration layer (`agent/tools.py` for plan persistence, a new `backend/pmc_recompute.py` for PMC, and `backend/routes/adaptations.py` extended with a `trigger_session_ids` linkage) — plus four required schema migrations (`0005`) that must ship before any of this code runs against a live DB.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Plan persistence (plans/sessions rows) | API/Backend — `agent/tools.py::dispatch_tool` post-processing | Database (Supabase Postgres) | `generate_plan` is documented pure/no-DB (locked invariant, `plan.py:5-6`); persistence must live in the orchestration layer that already special-cases this exact tool name for user_id injection |
| FTP resolution & `profiles.ftp` write-back | API/Backend — `routes/rides.py::get_user_ftp` | Database | FTP math (`estimate_ftp_from_rides`) is pure in `sports_science/ftp.py`; persisting the resolved value is I/O and belongs at the route layer, mirroring the existing `save_profile` DB-write precedent |
| PMC day-series recompute | API/Backend — new `backend/pmc_recompute.py` orchestrator | Database | `update_pmc` (TOOL-05) is a locked, unit-tested pure single-step function; a new orchestration module wraps it in a loop, it must not be modified |
| FIT dedup | API/Backend — `routes/rides.py::upload_fit` | Database (unique constraint) + Storage | Hash computed at upload time in the route; DB unique constraint is the authoritative dedup guard (defence-in-depth against races) |
| Ride-session linking & compliance | API/Backend — `routes/rides.py` pipeline | Database | Needs a join between `rides` and `sessions`; pure compute (`validate_session_vs_actual`) is unchanged |
| Adaptation idempotency | API/Backend — `routes/adaptations.py` | Database (`adaptations` table extension) | Signal-consumption bookkeeping needs a persisted "already-handled" marker; this is inherently a database-state concern, not a pure-function concern |
| Macro-replan confirm | API/Backend — new endpoint in `routes/adaptations.py` | Database (`adaptations` table extension) | D-19 needs a stored, referenceable proposal to confirm against later; cannot be stateless |

## Standard Stack

No new external packages are required for this phase.

### Core (already installed, verified in repo)
| Library | Version (installed) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `supabase` (async client, `acreate_client`) | pinned in `requirements.txt`; already used everywhere via `backend/db.py` | All persistence I/O | Existing project-wide pattern (`get_async_supabase` singleton) |
| `fastapi` | pinned | Route layer | Already the framework |
| Python stdlib `hashlib` | 3.12 stdlib | FIT content-hash dedup | No dependency needed — `hashlib.sha256(file_bytes).hexdigest()` |
| Python stdlib `datetime`/`date` | 3.12 stdlib | Day-series generation for PMC recompute | Already used throughout `rides.py`/`adaptations.py` |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Recompute-from-scratch PMC | Incremental EWMA with a nightly gap-filling cron | Requires a scheduler (Vercel Cron or similar) — deferred; recompute-from-scratch is strictly simpler and already correct without any scheduled job, at negligible cost for single-user data volumes |
| Content-hash column + unique constraint for dedup | Client-side dedup only (frontend blocks re-upload) | Does not protect against retries/multiple devices; DB constraint is the only reliable guard |
| `trigger_session_ids uuid[]` array column on `adaptations` | A separate `adaptation_signals` join table | Array column is sufficient for this scale (single user, low row counts) and avoids a new table; a join table would be more "correct" relationally but is over-engineering for MVP — `[ASSUMED]`, flag for user/planner confirmation |

**Installation:** None — no new packages.

## Package Legitimacy Audit

**Not applicable.** This phase adds zero new third-party dependencies. All new code uses the Python standard library (`hashlib`, `datetime`) and the already-installed, already-audited `supabase` async client. No `npm install` / `pip install` step is required.

## Architecture Patterns

### System Architecture Diagram

```
 ONBOARDING / CHAT (SSE)                         RIDE UPLOAD
 ────────────────────────                        ─────────────
 User approves summary                           POST /rides/upload
       │                                                │
       ▼                                                ▼
 run_turn() tool_use loop                     read bytes, sha256 hash
       │                                                │
       ▼                                    ┌───────────┴───────────┐
 dispatch_tool(name="generate_plan")         │ SELECT rides WHERE     │
       │                                     │ user_id+content_hash   │
       ▼                                     └───────────┬───────────┘
 generate_plan() [PURE, unchanged]              exists?  │  new?
   -> sessions[], plan_id=None                     │            │
       │                                     return existing   parse_fit_file()
       ▼                                     ride (200,         (asyncio.to_thread)
 *** NEW HOOK ***                            duplicate=true)         │
 _persist_plan(user_id, result.value)              STOP        get_user_ftp()
   1. INSERT plans row                                                │
   2. resolve week+day -> scheduled_date                    INSERT rides (ride_date
   3. bulk INSERT sessions rows                              from FIT start_time,
      (plan_id, status='planned')                            content_hash, ftp_used)
   4. mutate result.value["plan_id"]                                  │
       │                                                    await process_ride_pipeline()
       ▼                                                     (INLINE-AWAITED, not
 tool_result -> back to Claude                               BackgroundTasks — Vercel)
                                                                        │
                                                        ┌───────────────┼────────────────┐
                                                        ▼               ▼                ▼
                                                  compute_tss()   link ride->session   PMC RECOMPUTE
                                                  [PURE]          (match by session_id  (pmc_recompute.py)
                                                                   scheduled_date       1. fetch all rides
                                                                   window, mark          for user, group-sum
                                                                   session completed)    by ride_date
                                                                        │               2. walk day-by-day
                                                                        ▼                  through update_pmc()
                                                                UPDATE rides (tss,          [PURE, unchanged]
                                                                np_watts, session_id,     3. bulk UPSERT
                                                                compliance_pct)              pmc_history

 WEEKLY / ON-DEMAND CHECK                        MACRO REPLAN CONFIRM (new, D-19)
 ─────────────────────────                       ──────────────────────────────
 POST /adaptations/check                          POST /adaptations/{id}/confirm
       │                                                 │
       ▼                                                 ▼
 detect_signals()                                 SELECT adaptations WHERE
   - query sessions status IN                      id=X AND user_id=Y
     ('planned','completed')                        AND status='proposed'
     minus session_ids already in                        │
     adaptations.trigger_session_ids                     ▼
   - missed: planned + past-due + no ride    apply after_snapshot to sessions
   - underperformance: completed + linked          table (the stored proposal,
     ride + compliance<60                          not recomputed) -> status='applied'
       │                                                 │
       ▼                                                 ▼
 decide_scope() -> micro | macro           calendar sync (fire-and-forget)
       │
       ▼
 apply_micro/_macro (existing, extended:
   - shift-guard check as today
   - if macro needs_confirmation: INSERT
     adaptations row status='proposed',
     return adaptation_id — do NOT apply
   - if applied: flip triggering session(s)
     status='missed' where signal was 'missed',
     record trigger_session_ids
```

### Recommended Project Structure

```
backend/
├── agent/
│   └── tools.py             # EXTEND: dispatch_tool gains a generate_plan
│                             #   post-processing branch (_persist_generated_plan)
├── routes/
│   ├── rides.py              # EXTEND: content-hash dedup, ride->session link,
│                             #   inline-await pipeline (drop BackgroundTasks),
│                             #   profiles.ftp write-back, fixed ftp_watts key
│   ├── adaptations.py        # EXTEND: trigger_session_ids bookkeeping, status
│                             #   flip on missed, new POST /{id}/confirm endpoint
│   └── sessions.py           # NO CHANGE needed for Phase 6 (reads already
│                             #   correct once rows exist) — verify only
├── pmc_recompute.py           # NEW: day-series builder wrapping update_pmc()
└── sports_science/
    ├── plan.py                # NO CHANGE — stays pure (locked invariant)
    ├── pmc.py                 # NO CHANGE — stays pure (locked invariant)
    └── ftp.py                 # ONE-LINE FIX: no change needed here; the bug is
                                #   the caller's key lookup, not this function
supabase/migrations/
└── 0005_phase6_persistence.sql  # NEW: see Migration List below
```

### Pattern 1: Tool-dispatch persistence hook (generate_plan → plans/sessions rows)

**What:** Extend `dispatch_tool` in `agent/tools.py` with a `generate_plan`-specific post-processing step, mirroring the existing `user_id`-injection special case for the same two tool names.
**When to use:** Any time a pure sports-science tool's output must be persisted before being handed back to Claude, without making the tool itself DB-aware.
**Example:**
```python
# Source: backend/agent/tools.py:400-453 (existing dispatch_tool), extended
async def dispatch_tool(tool_use_block, audit_log: list, user_id: str | None = None) -> dict:
    name = tool_use_block.name
    inputs = tool_use_block.input
    tool_use_id = tool_use_block.id

    if user_id is not None and name in {"save_profile", "generate_plan"}:
        inputs = {**inputs, "user_id": user_id}

    fn = TOOL_REGISTRY.get(name)
    ...
    result: ToolResult = await asyncio.to_thread(fn, **inputs)

    # NEW: persistence hook for generate_plan only. result.value is a mutable
    # dict even though ToolResult itself is frozen (pydantic frozen blocks
    # reassigning result.value, not mutating dict contents in place).
    if name == "generate_plan" and user_id is not None and result.value:
        await _persist_generated_plan(user_id, result.value)  # mutates in place

    audit_log.append({...})
    return {...}
```
`_persist_generated_plan` resolves each session's `week`/`day` pair to an absolute `scheduled_date` anchored on the confirmation date (Monday of the current week + day-of-week offset, rolling into next week if that day has already passed this week), inserts one `plans` row (`user_id`, `sessions` jsonb snapshot, `mesocycle_weeks`, `ftp_confidence`, `status='active'`), then bulk-inserts `sessions` rows with `plan_id` set, writing **both** `duration_mins` and `duration_minutes` (existing dual-column pattern, must stay hand-synced per the app-review pitfall list) and `status='planned'`.

### Pattern 2: PMC day-series recompute-from-scratch

**What:** Replace "one EWMA step per upload, keyed by upload date" with "rebuild the whole daily series from ride data, keyed by ride date, on every ride event."
**When to use:** Any time-series metric derived from sparse, retroactively-arriving, possibly-duplicated events (exactly PMC's situation).
**Why not patch the existing incremental code:** The existing code reads *one* row (`ORDER BY date DESC LIMIT 1`) as "yesterday", which is only correct if uploads always arrive in chronological order with no gaps and no re-processing. Retroactive FIT uploads (already an explicit supported case, `WR-009`), gap days, and dedup all violate that assumption simultaneously. A recompute-from-scratch pass sidesteps all three at once and is the standard pattern used by TrainingPeaks-style PMC implementations when backfilling historical data.
**Example:**
```python
# Source: NEW backend/pmc_recompute.py — orchestrates the existing pure update_pmc
from datetime import date, timedelta
from backend.sports_science.pmc import update_pmc

async def recompute_pmc_for_user(user_id: str, supabase) -> None:
    rides_resp = await (
        supabase.table("rides")
        .select("ride_date, tss")
        .eq("user_id", user_id)
        .execute()
    )
    rides = [r for r in (rides_resp.data or []) if r.get("ride_date") and r.get("tss") is not None]
    if not rides:
        return

    # Group-sum same-day rides (handles same-day double upload correctly).
    tss_by_day: dict[date, float] = {}
    for r in rides:
        d = date.fromisoformat(r["ride_date"])
        tss_by_day[d] = tss_by_day.get(d, 0.0) + float(r["tss"])

    start = min(tss_by_day)
    today = date.today()

    prev_ctl = prev_atl = 0.0
    days_of_data = 0
    rows_to_upsert = []
    d = start
    while d <= today:
        days_of_data += 1  # calendar days elapsed, NOT upload count
        tss_today = tss_by_day.get(d, 0.0)  # zero-TSS gap fill (D-06 decay)
        result = update_pmc(prev_ctl, prev_atl, tss_today, days_of_data)
        v = result.value
        rows_to_upsert.append({
            "user_id": user_id, "date": d.isoformat(),
            "ctl": v["ctl"], "atl": v["atl"], "tsb": v["tsb"],
            "tss": tss_today, "days_of_data": days_of_data,
            "tss_display_ready": v["tss_display_ready"],
        })
        prev_ctl, prev_atl = v["ctl"], v["atl"]
        d += timedelta(days=1)

    # Single bulk upsert call, not one round-trip per day.
    await supabase.table("pmc_history").upsert(
        rows_to_upsert, on_conflict="user_id,date"
    ).execute()
```
This is called **inline-awaited** from the ride-processing pipeline after the ride row is inserted (not `BackgroundTasks`, per the Vercel constraint). For a single-user MVP the full recompute is bounded (roughly `days_since_first_ride` rows, realistically low hundreds to low thousands even after years) and one bulk upsert call — this is not a performance concern at this scale. **`[ASSUMED]`**: if a future multi-user or multi-year-of-data scenario made full recompute too slow, an incremental variant reading the last 42+ days would be the next optimization; not needed now.

### Pattern 3: Content-hash FIT dedup

**What:** Compute `sha256(file_bytes)` at upload time; use it both as the Storage path key and as a DB uniqueness guard.
**When to use:** Any file-upload endpoint where the same physical file might be re-submitted (retry, multi-device, user error).
**Example:**
```python
# Source: NEW code for backend/routes/rides.py::upload_fit
import hashlib

content_hash = hashlib.sha256(file_bytes).hexdigest()

existing = await (
    supabase.table("rides")
    .select("id, tss, status" if "status" in _RIDES_COLS else "id")
    .eq("user_id", user_id)
    .eq("content_hash", content_hash)
    .execute()
)
if existing.data:
    return {"ride_id": existing.data[0]["id"], "status": "duplicate", "duplicate": True}

storage_path = f"{user_id}/{content_hash}.fit"  # hash-based path: identical
                                                  # content always maps to the
                                                  # same object (idempotent
                                                  # storage write, no filename
                                                  # collision surprises)
```
The DB `UNIQUE (user_id, content_hash)` constraint (added in the migration below) is the authoritative guard against a race between the pre-check `SELECT` and the `INSERT` (two concurrent uploads of the same file); catch the resulting unique-violation and fall back to the same `duplicate=True` response.

### Pattern 4: Ride-session linking replaces "first session today" fuzzy match

**What:** Replace the current `sessions.eq("scheduled_date", date.today())` lookup (uses upload date, matches literally any session scheduled today, ignores status) with a lookup anchored on the ride's own `ride_date` and an explicit link write-back.
**Example:**
```python
# Source: NEW code replacing backend/routes/rides.py:318-337
session_resp = await (
    supabase.table("sessions")
    .select("id, tss_target, type")
    .eq("user_id", user_id)
    .eq("scheduled_date", ride_date)          # ride's own date, not today
    .eq("status", "planned")                  # only an un-consumed session can match
    .limit(1)
    .execute()
)
if session_resp.data:
    matched_session = session_resp.data[0]
    compliance_result = validate_session_vs_actual(
        planned={"tss": matched_session.get("tss_target", 0)},
        actual={"tss": tss if tss is not None else 0.0},
    )
    await supabase.table("sessions").update({
        "status": "completed",
    }).eq("id", matched_session["id"]).eq("user_id", user_id).execute()
    ride_update["session_id"] = matched_session["id"]
```
This single change is what makes `detect_signals`'s "missed" query (which filters `status='planned'`) correctly stop seeing a session once a ride has actually completed it — it is the root fix underpinning the adaptation-idempotency design in Pattern 5.

### Pattern 5: Adaptation idempotency via `trigger_session_ids` + status flip

**What:** Two complementary mechanisms, both required:
1. **Status flip** — once a "missed" signal is acted on, the triggering session's `status` becomes `'missed'` (not just adjusted downstream sessions). Requires the `sessions.status` CHECK constraint to allow `'missed'` (currently does not — see migration list).
2. **Trigger linkage** — `adaptations` gains a `trigger_session_ids uuid[]` column. Before emitting a signal in `detect_signals`, exclude any session id that already appears in any `adaptations.trigger_session_ids` for this user (covers underperformance signals, which cannot be "consumed" via a status flip because the session is legitimately `completed`, not `missed`).

**Redesigned `detect_signals` query shape:**
```python
# Source: NEW code replacing backend/routes/adaptations.py:110-181
already_consumed = await (
    supabase.table("adaptations")
    .select("trigger_session_ids")
    .eq("user_id", user_id)
    .execute()
)
consumed_ids: set[str] = set()
for row in (already_consumed.data or []):
    consumed_ids.update(row.get("trigger_session_ids") or [])

sessions_resp = await (
    supabase.table("sessions")
    .select("id, scheduled_date, tss_target, status")
    .eq("user_id", user_id)
    .in_("status", ["planned", "completed"])
    .gte("scheduled_date", window_start.isoformat())
    .lte("scheduled_date", today.isoformat())
    .execute()
)
for session in sessions_resp.data or []:
    if session["id"] in consumed_ids:
        continue
    if session["status"] == "planned" and _parse_date(session["scheduled_date"]) < today:
        # still planned and past-due -> no ride ever linked -> missed
        signals.append({"type": "missed", "session_id": session["id"]})
    elif session["status"] == "completed":
        ride = await _get_linked_ride(session["id"])  # rides.session_id = session.id
        if ride:
            result = validate_session_vs_actual(
                planned={"tss": session.get("tss_target") or 0},
                actual={"tss": ride.get("tss") or 0},
            )
            if (result.value.get("compliance_pct") or 100) < 60:
                signals.append({"type": "underperformance", "session_id": session["id"]})
```
When `apply_micro_adjustment`/`apply_macro_replan` successfully applies, it must (a) write `trigger_session_ids` into the `adaptations` row it inserts via `log_adaptation`, and (b) for every signal of type `"missed"`, `UPDATE sessions SET status='missed' WHERE id = session_id`.

### Pattern 6: Macro-replan proposal/confirm two-phase commit (D-19)

**What:** `apply_macro_replan`'s `needs_confirmation` branch currently returns a `change_summary` and stops — nothing can ever apply it. Persist the proposal so a later request can apply exactly what was proposed (not a freshly recomputed version, which could differ if state changed in between).
**Example:**
```python
# Source: NEW code extending backend/routes/adaptations.py::apply_macro_replan
if shift_check["requires_user_confirmation"]:
    adaptation_id = await log_adaptation(
        user_id=user_id, trigger=primary_trigger, signal_count=len(signals),
        scope="macro", before_snapshot={"sessions": before_sessions},
        after_snapshot={"sessions": after_sessions, "recommended_ctl": recommended_ctl},
        explanation_text=change_summary["warning"],
        status="proposed",                       # NEW column, default 'applied' for old rows
        trigger_session_ids=[s.get("session_id") for s in signals if s.get("session_id")],
    )
    return {"status": "needs_confirmation", "scope": "macro",
            "adaptation_id": adaptation_id, "change_summary": change_summary}

# NEW endpoint
@router.post("/{adaptation_id}/confirm")
async def confirm_macro_replan(adaptation_id: str, current_user: dict = Depends(get_current_user)) -> dict:
    user_id = current_user["user_id"]
    validate_uuid(adaptation_id, "adaptation_id")
    supabase = await _get_async_supabase()
    row_resp = await (
        supabase.table("adaptations").select("*")
        .eq("id", adaptation_id).eq("user_id", user_id).eq("status", "proposed")
        .execute()
    )
    if not row_resp.data:
        raise HTTPException(404, {"error": "proposal_not_found",
                                   "detail": "No pending macro-replan proposal for this id"})
    proposal = row_resp.data[0]
    for session in proposal["after_snapshot"]["sessions"]:
        await supabase.table("sessions").update({
            "tss_target": session["tss_target"], "scheduled_date": session["scheduled_date"],
        }).eq("id", session["id"]).eq("user_id", user_id).execute()
    await supabase.table("adaptations").update({"status": "applied"}).eq("id", adaptation_id).execute()
    return {"status": "applied", "adaptation_id": adaptation_id}
```
`[ASSUMED]`: no rejection/expiry flow is specified by requirements; flag this as an open question for the planner rather than building it speculatively (avoids scope creep).

### Anti-Patterns to Avoid

- **Making `generate_plan`/`update_pmc` async and DB-aware:** breaks the locked "pure computation, no DB calls" invariant documented in both modules' docstrings and would silently desync from `tests/sports_science/` which tests them as pure functions with no mocking. Persistence belongs in the orchestration layer, not the tool.
- **Patching the existing single-step PMC upload code with a "look back N days and fill gaps" band-aid:** this still can't correctly handle retroactive out-of-order uploads or true idempotent reprocessing; recompute-from-scratch is not more code, it's less.
- **Using `BackgroundTasks.add_task` for anything in the reworked ride pipeline:** Vercel freezes the function after the response is sent; a task queued this way may never run to completion on Vercel serverless. Everything Phase 6 touches in `process_ride_background` must become `await`ed inline before the response.
- **Reusing `status='skipped'` as a stand-in for "missed":** the CHECK constraint already provides `'skipped'` (implies a *voluntary* user action, e.g., a future "Mark Missed" UI affordance already distinct in intent) versus `'missed'` (implies the system detected non-completion). Conflating them breaks the semantic distinction the schema clearly intends and complicates any future UI that needs to show them differently.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File content dedup | A custom "is this the same ride" heuristic (comparing power arrays, durations, etc.) | `hashlib.sha256(file_bytes).hexdigest()` + DB unique constraint | Byte-identical re-uploads are the actual failure mode observed (retry, multi-device); a cryptographic hash is the simplest, most correct answer and needs no library |
| Day-range iteration for the PMC series | Manual date-string arithmetic | `datetime.date` + `timedelta(days=1)` stdlib loop | Already the pattern used elsewhere in `adaptations.py` (`_parse_date`); no reason to introduce a date library |
| Bulk row upsert | Looping one `.upsert()` call per day | A single `.upsert(list_of_dicts, on_conflict=...)` call | supabase-py's `upsert()` already accepts a list; one round trip instead of N |

**Key insight:** every "hand-roll" temptation in this phase (custom dedup heuristics, incremental gap-patching for PMC, per-row upsert loops) is actually more code and less correct than the straightforward stdlib/bulk-API alternative. This phase is fundamentally about *replacing ad-hoc incremental logic with idempotent recomputation*, so resist the urge to make it cleverer.

## Common Pitfalls

### Pitfall 1: `pmc_history` is missing columns the code already writes to `[VERIFIED: migrations 0001-0004 read directly]`
**What goes wrong:** `process_ride_background`'s `pmc_history` upsert (`rides.py:362-379`) writes `tss` and `days_of_data` keys, but `0001_initial_schema.sql` only creates `id, user_id, date, ctl, atl, tsb, tss_display_ready, created_at`. No later migration (`0002`, `0003`, `0004`) adds these two columns.
**Why it happens:** PostgREST rejects inserts/upserts referencing unknown columns; the surrounding `try/except Exception: logger.error(...)` in `process_ride_background` swallows this, so the failure is invisible in normal operation.
**How to avoid:** The Phase 6 migration MUST add `pmc_history.tss numeric` and `pmc_history.days_of_data int NOT NULL DEFAULT 0` before any PMC-recompute code is deployed, or every recompute upsert will silently no-op exactly like today's code does.
**Warning signs:** `pmc_history` table has rows only with `tss_display_ready=false` and `null`-ish behavior despite uploads; or (if recompute is deployed pre-migration) recompute "succeeds" per logs but the table never updates.

### Pitfall 2: `sessions.status` CHECK constraint does not allow `'missed'` `[VERIFIED: 0001_initial_schema.sql:56-57, no later ALTER found]`
**What goes wrong:** `POST /adaptations/sessions/{id}/missed` (`adaptations.py:685`) sets `status='missed'`. The CHECK constraint is `status IN ('planned', 'completed', 'skipped', 'partial')`. This UPDATE will raise a Postgres check-violation and the endpoint will 500 the first time it's hit against a real (non-mocked) database — none of the existing tests catch this because `tests/api/test_adaptations.py` mocks Supabase and never round-trips through a real constraint.
**Why it happens:** The endpoint and the schema were evidently written independently without a shared migration.
**How to avoid:** The Phase 6 migration MUST `ALTER TABLE sessions DROP CONSTRAINT ... ; ALTER TABLE sessions ADD CONSTRAINT ... CHECK (status IN ('planned','completed','skipped','partial','missed'))`.
**Warning signs:** would only surface in a live/integration test hitting the real Supabase instance — add exactly that as a Wave 0 gap (see Validation Architecture).

### Pitfall 3: Inline-awaiting the ride pipeline changes the upload response contract and breaks existing tests `[VERIFIED: tests/api/test_rides.py:107-142, 396-449]`
**What goes wrong:** `test_upload_returns_200` and `test_fit_upload_integration` both monkeypatch `process_ride_background` to a no-op/capture stub and assert the HTTP response is `{"status": "processing"}` *before* the (mocked) background work would have run. If Phase 6 makes the pipeline `await`ed inline, by the time the response is returned the ride **has** already been processed — `"status": "processing"` becomes an inaccurate label, and any test still monkeypatching "the background function" as a separate seam needs updating to monkeypatch the now-inline call instead (the tests will still pass mechanically if the mock is still swapped in the same way, but the semantic assertion `status == "processing"` should become `status == "processed"` or similar to reflect the new synchronous reality).
**How to avoid:** Rename the response status field value (e.g., `"processed"` once inline; keep `"duplicate"` for the dedup path) and update the two affected tests as part of this phase's Wave 0/1 work, not as an incidental side effect discovered later.
**Warning signs:** frontend `FitUploadZone`/upload UX currently has no progress indicator (Phase 9 concern) — inline-await means the HTTP request now takes as long as parsing + TSS + PMC recompute + compliance check, which is still sub-second for a single ride and one recompute pass, but should be noted as a UX latency consideration for the planner, not solved in Phase 6 (no progress bar is in scope here).

### Pitfall 4: `profiles.ftp` does not exist, so `sessions.py:328`'s `.select("ftp")` is already broken today `[VERIFIED: grep across all 4 migrations, zero occurrence of "ADD COLUMN ftp" or "ftp" in CREATE TABLE profiles]`
**What goes wrong:** `GET /sessions/{id}/export.zwo` selects `profiles.ftp`, a column that has never existed. PostgREST returns an error for the unknown column; this is likely already producing a 500 (or is masked if this code path has literally never executed against a live DB yet, e.g. during dev before real ZWO exports were tried against a populated profile).
**How to avoid:** Migration adds `profiles.ftp numeric` (nullable) and `profiles.lthr numeric` (nullable) columns. `profiles.ftp` should be write-back-populated by `get_user_ftp` (route layer) once `estimate_ftp_from_rides` confidence reaches `medium`/`high` — not just used transiently for that one ride's TSS calc as today. `profiles.lthr` should be populated from `lthr_estimate` at `save_profile` time (keep `lthr_estimate` as the raw self-reported onboarding value for audit; `lthr` becomes the "confirmed/current" value the rest of the app reads, matching the frontend's expected column name).
**Note (explicitly out of Phase 6 scope, flagged not fixed):** the frontend `Profile` TypeScript interface (`frontend/src/lib/api.ts:46-56`) also expects `display_name`, `weight_kg`, `onboarding_complete`, and `updated_at`, none of which exist in the schema at all. This is broader than the phase goal ("fix `ftp_watts`/`ftp` mismatch, add missing `profiles.ftp`/`lthr` columns") and is Phase 9 (Frontend Resilience) territory — do not scope-creep into fixing all four here, but the planner should be aware `GET /profiles/me` will still not satisfy the full frontend contract after Phase 6.

### Pitfall 5: Trust-scanner interaction is a non-issue here, but verify anyway
**What could go wrong:** Changing tool output shapes (e.g., `generate_plan`'s `plan_id` becoming a real UUID instead of `None`, `sessions` list gaining real `id` fields) could theoretically interact with `scan_buffer`'s substring-attribution logic against `tool_result_values` (`agent/trust.py:94-163`).
**Why it's actually fine:** UUIDs contain hyphens and are never matched by `PHYSIO_PATTERN_A`/`PHYSIO_PATTERN_B` (both require a bare number adjacent to a physio unit token). No change to trust-scanner behavior is expected.
**Verify anyway:** Add a targeted assertion in the Wave testing plan that a real `generate_plan` tool result (with a populated `plan_id` and session `id`s) does not itself trigger a trust violation when echoed by the model — `tests/agent/test_trust_corpus.py` is the right home for this if not already covered.

### Pitfall 6: Frontend field-name mismatches are NOT fixed by Phase 6 and must not be assumed fixed
**What goes wrong:** Even after sessions/rides start being real rows, `frontend/src/lib/api.ts`'s `Session` interface (`date`, `planned_tss`, `actual_tss`, `notes` — none of which the backend returns) and `Ride` interface (`duration_seconds`, `avg_power_watts`, `file_name` vs backend's `duration_secs`, `avg_power`, no filename field at all) remain mismatched. Today/Agenda/History screens may start rendering *some* real data (whatever field names happen to line up, e.g. `id`, `status`, `scheduled_date`, `tss`, `compliance_pct`) but will continue showing `"--"` or `undefined` for the mismatched fields.
**How to avoid:** Do not attempt to fix frontend TS interfaces in Phase 6 (that's Phase 9's explicit charter). Do verify, as a Phase 6 acceptance check, that the backend's `_SESSION_COLUMNS` and `rides` select-list are internally consistent and that real data flows end-to-end through the API — visual/frontend correctness is verified in Phase 9.

## Code Examples

### FTP key-mismatch fix (one-line, but write-back is the real fix)
```python
# Source: backend/routes/rides.py:235-236, current (buggy) code:
if ftp_value is not None and confidence in ("medium", "high"):
    return (float(ftp_value.get("ftp_watts", COLD_START_FTP)), False)  # WRONG KEY

# Fixed, PLUS profile write-back (new):
if ftp_value is not None and confidence in ("medium", "high"):
    resolved_ftp = float(ftp_value.get("ftp", COLD_START_FTP))  # ftp.py:100 returns "ftp"
    try:
        await supabase.table("profiles").update({"ftp": resolved_ftp}).eq("user_id", user_id).execute()
    except Exception as exc:
        logger.warning("profiles.ftp write-back failed (non-fatal): %s", exc)
    return (resolved_ftp, False)
```

### Week/day → absolute scheduled_date resolution (needed by Pattern 1)
```python
# Source: NEW helper for agent/tools.py::_persist_generated_plan
from datetime import date, timedelta

_DAY_INDEX = {"Monday": 0, "Tuesday": 1, "Wednesday": 2, "Thursday": 3,
              "Friday": 4, "Saturday": 5, "Sunday": 6}

def _resolve_scheduled_date(confirm_date: date, week: int, day_name: str) -> date:
    # Week 1 starts on the Monday of confirm_date's week (or confirm_date
    # itself if a session's day has already passed this week -> next week).
    monday_of_week1 = confirm_date - timedelta(days=confirm_date.weekday())
    target = monday_of_week1 + timedelta(weeks=week - 1, days=_DAY_INDEX[day_name])
    return target
```
`[ASSUMED]`: this "anchor plan Week 1 to the current calendar week's Monday" policy is a reasonable default but is not specified anywhere in requirements/CONTEXT — flag for planner/user confirmation since it affects exactly which dates Today/Agenda show immediately after confirmation.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Single-EWMA-step-per-upload PMC keyed by upload date | Recompute-from-scratch day-series keyed by ride date | This phase | Correctly handles gaps, same-day rides, retroactive uploads, and reprocessing |
| Filename-based Storage path (`fits/{user_id}/{filename}`) | Content-hash-based Storage path (`{user_id}/{hash}.fit`) | This phase | Eliminates silent overwrite-on-same-filename and gives a natural dedup key |
| "First session scheduled today" fuzzy ride-session match | Exact `ride_date == scheduled_date AND status='planned'` match + explicit `session_id` write-back | This phase | Removes false matches and enables correct downstream idempotency |

**Deprecated/outdated:** the incremental single-step PMC update pattern (`update_pmc` called once per upload with only the immediately-prior row as context) should be considered obsolete for any future PMC-touching code — it cannot be made correct without becoming the recompute pattern.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `trigger_session_ids uuid[]` array column is sufficient (vs. a normalized join table) for idempotency bookkeeping at this data scale | Pattern 5, Architecture Patterns | Low — single-user MVP row counts are small; a join table refactor later is cheap if this proves inadequate |
| A2 | No rejection/expiry flow is needed for proposed macro-replans (D-19 confirm endpoint) | Pattern 6 | Low-medium — a stale, never-confirmed proposal could accumulate; recommend the planner add a TTL or "supersede on next `/check`" rule as a small follow-up task rather than building it speculatively now |
| A3 | Plan Week 1 anchors to the current calendar week's Monday at confirmation time | Code Examples (scheduled_date resolution) | Medium — directly affects which dates the user sees immediately after onboarding; wrong anchor could put Week 1's Monday/Tuesday sessions in the past on the day of confirmation. Recommend confirming with user/CONTEXT before locking |
| A4 | Full PMC recompute-from-scratch on every ride upload is performant enough with no caching/incremental optimization, given single-user MVP scale | Pattern 2 | Low — bounded by `days_since_first_ride`, realistically hundreds to low thousands of rows; would only become a concern at multi-year, multi-user scale far beyond current PROJECT.md scope |
| A5 | `profiles.lthr` should be populated by copying `lthr_estimate` at `save_profile` time, keeping both columns | Pitfall 4 | Low-medium — an alternative is to rename `lthr_estimate` to `lthr` outright and drop the "estimate vs confirmed" distinction; either is workable, flag for planner decision |

**If this table is empty:** N/A — see rows above; all are LOW-MEDIUM risk implementation-detail decisions, none touch compliance/safety/back-protective logic (those are Phase 8 territory and untouched here).

## Open Questions

1. **Does the macro-replan confirm endpoint need a rejection path, or does silence/timeout implicitly reject?**
   - What we know: ADAPT-03/D-19 only specifies that a >30% shift must "surface a change summary to the user" before applying; nothing about rejection.
   - What's unclear: whether a proposed-but-never-confirmed macro replan should be superseded automatically by the next `/adaptations/check` run (recommended), or persist indefinitely as a stale "proposed" row.
   - Recommendation: have `/adaptations/check` supersede any prior `status='proposed'` row for the same user before creating a new proposal (`UPDATE adaptations SET status='superseded' WHERE user_id=X AND status='proposed'`); simplest correct behavior, no new endpoint needed.

2. **Should PMC recompute run synchronously inline on every upload, or be debounced/batched?**
   - What we know: Vercel constraint requires no `BackgroundTasks`; inline-await is mandated.
   - What's unclear: whether recompute should also be triggered from other events (e.g., a manual "recompute PMC" endpoint if a user needs to fix historical data), beyond the ride-upload trigger.
   - Recommendation: implement the ride-upload trigger only for Phase 6 (satisfies the phase goal); do not build an admin/manual recompute endpoint unless requested — avoid scope creep.

3. **Does `apply_micro_adjustment` also need `trigger_session_ids` bookkeeping, or is the status-flip-to-'missed' sufficient for micro?**
   - What we know: micro handles exactly 1 signal (`decide_scope` guarantees this); if that signal is `"missed"`, the status flip alone prevents re-detection.
   - What's unclear: if the single signal is `"underperformance"` (a completed session, not flippable to `missed`), micro-scope also needs the `trigger_session_ids` guard to avoid re-triggering on every subsequent `/check`.
   - Recommendation: apply `trigger_session_ids` bookkeeping uniformly to both micro and macro paths (Pattern 5 already assumes this) — do not special-case micro as "status flip is enough," since the underperformance-via-micro case would silently break idempotency otherwise.

## Environment Availability

Skipped — this phase has no new external tool/service dependencies beyond the already-configured Supabase project (verified reachable via existing `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` env vars used throughout the existing, passing test suite and prior phases' live verification).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest + pytest-asyncio (`asyncio_mode = auto`, per `tests/api/conftest.py` docstring) |
| Config file | `pytest.ini` (repo root) |
| Quick run command | `pytest tests/sports_science/ tests/agent/ -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

Phase 6 has no formally mapped requirement IDs (ROADMAP.md lists `Requirements: TBD`); the phase goal decomposes into the following testable behaviors, each traced to the exact defect it fixes:

| Behavior | Test Type | Automated Command | File Exists? |
|----------|-----------|-------------------|-------------|
| `generate_plan` tool call results in real `plans`+`sessions` rows with correct `plan_id` | integration (mocked Supabase) | `pytest tests/agent/test_tools_phase3.py -k generate_plan -x` | ❌ Wave 0 — extend existing file |
| FTP key fix: `get_user_ftp` returns the estimated value (not cold-start) when confidence is medium/high | unit | `pytest tests/api/test_rides.py -k get_user_ftp -x` | ❌ Wave 0 — new test, existing file |
| `profiles.ftp` write-back occurs after a medium/high-confidence estimate | integration (mocked Supabase) | `pytest tests/api/test_rides.py -k ftp_writeback -x` | ❌ Wave 0 — new test |
| PMC recompute: zero-TSS gap days present in output series | unit | `pytest tests/test_pmc_recompute.py -k gap_days -x` | ❌ Wave 0 — new file |
| PMC recompute: same-day rides summed, not overwritten | unit | `pytest tests/test_pmc_recompute.py -k same_day_sum -x` | ❌ Wave 0 — new file |
| PMC recompute: `days_of_data` counts calendar days, not upload count | unit | `pytest tests/test_pmc_recompute.py -k days_of_data_calendar -x` | ❌ Wave 0 — new file |
| FIT dedup: re-uploading identical bytes returns `duplicate=True`, no second row | integration (mocked Supabase) | `pytest tests/api/test_rides.py -k dedup -x` | ❌ Wave 0 — new test |
| Ride-session link: matched session flips to `completed`, `rides.session_id` set | integration (mocked Supabase) | `pytest tests/api/test_rides.py -k session_link -x` | ❌ Wave 0 — new test |
| `detect_signals` idempotency: second `/check` call does not re-emit an already-consumed signal | integration (mocked Supabase) | `pytest tests/api/test_adaptations.py -k idempotent -x` | ❌ Wave 0 — new test |
| `POST /adaptations/sessions/{id}/missed` succeeds against the real CHECK constraint values | integration (mocked Supabase, asserting the UPDATE payload's status value is schema-legal) | `pytest tests/api/test_adaptations.py -k missed_status_value -x` | ❌ Wave 0 — new test |
| `POST /adaptations/{id}/confirm` applies a stored `proposed` snapshot exactly | integration (mocked Supabase) | `pytest tests/api/test_adaptations.py -k confirm_macro -x` | ❌ Wave 0 — new endpoint + test |
| 30% shift guard is live (not mathematically dead) | unit | `pytest tests/api/test_adaptations.py -k shift_limit -x` | ✅ `check_shift_limit` exists and is unit-testable already; extend if `apply_macro_replan`'s shift semantics change |
| Existing `test_upload_returns_200`/`test_fit_upload_integration` updated for inline-await response contract | integration | `pytest tests/api/test_rides.py -k upload_returns -x` | ⚠️ Existing file, must be edited (Pitfall 3) |

### Sampling Rate
- **Per task commit:** `pytest tests/sports_science/ tests/agent/test_tools_phase3.py tests/api/test_rides.py tests/api/test_adaptations.py -x -q`
- **Per wave merge:** `pytest tests/ -q` (full suite)
- **Phase gate:** Full suite green before `/gsd-verify-work`, plus a live/manual check against the real Supabase instance for the two schema-constraint bugs found in this research (Pitfalls 1 and 2) — mocked tests cannot catch CHECK-constraint or missing-column errors, since the mock Supabase client accepts any payload shape.

### Wave 0 Gaps
- [ ] `tests/test_pmc_recompute.py` — new file, covers gap-day decay, same-day summation, calendar-day `days_of_data`, dedup interaction
- [ ] `supabase/migrations/0005_phase6_persistence.sql` — must exist and be applied (`supabase db push --linked --yes`, existing project pattern) before any integration test that isn't fully mocked can be trusted
- [ ] One live/manual verification step (not automatable in the mocked test suite) confirming the `sessions.status` CHECK constraint accepts `'missed'` and `pmc_history` accepts `tss`/`days_of_data` against the real Supabase project — recommend a `checkpoint:human-verify` or a `supabase db push` + one real API call as part of Wave 0, since this class of bug (schema drift vs. mocked tests) has already caused multiple silent production failures this project (`profiles.goals`/`fitness_goals` mismatch, fixed in 260702-vs6, is the identical failure pattern)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No change | Existing `get_current_user` JWT dependency, unchanged |
| V3 Session Management | No change | N/A |
| V4 Access Control | Yes | Every new/changed endpoint (`POST /adaptations/{id}/confirm`, ride dedup lookup, plan persistence) MUST dual-filter by `id` AND `user_id` exactly like the existing IDOR-mitigated patterns in `sessions.py`/`rides.py` (`eq("id", ...).eq("user_id", ...)`) |
| V5 Input Validation | Yes | `validate_uuid()` (existing `backend/utils.py` helper) on any new path parameter (`adaptation_id`); content-hash is server-computed from uploaded bytes, not client-supplied, so no injection surface there |
| V6 Cryptography | Yes (narrow) | `hashlib.sha256` for content-hash dedup is a non-cryptographic-secrecy use (content-addressing, not authentication) — collision resistance is more than sufficient for this purpose; no secret material involved, no library needed beyond stdlib |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| IDOR on new `/adaptations/{id}/confirm` endpoint (confirming another user's proposed replan) | Tampering / Information Disclosure | Dual-filter `eq("id", adaptation_id).eq("user_id", user_id).eq("status", "proposed")` before any apply — mirrors existing `mark_session_missed`'s ownership check pattern |
| Storage path collision/overwrite from client-controlled filename | Tampering | Already mitigated by switching to hash-based Storage paths (Pattern 3) — a side benefit of the dedup fix, not just a dedup feature |
| Race condition: two concurrent uploads of the same file both pass the pre-check `SELECT` before either `INSERT`s | Tampering (duplicate data) | DB-level `UNIQUE (user_id, content_hash)` constraint is the authoritative guard; the pre-check `SELECT` is only an optimization to avoid unnecessary parsing/processing work, not the security boundary |

## Sources

### Primary (HIGH confidence — direct code inspection this session)
- `backend/sports_science/plan.py`, `pmc.py`, `ftp.py`, `compliance.py`, `load.py`, `profile.py`, `types.py`, `zwo.py` — full read
- `backend/routes/rides.py`, `adaptations.py`, `onboarding.py`, `sessions.py`, `chat.py` (partial) — full/partial read
- `backend/agent/tools.py`, `loop.py`, `trust.py`, `main.py`, `db.py` — full read
- `supabase/migrations/0001_initial_schema.sql` through `0004_auto_provision_users.sql` — full read, cross-referenced for every column/constraint claim above
- `tests/api/conftest.py`, `test_rides.py`, `test_sessions.py`, `tests/sports_science/test_pmc.py` — full/partial read for test-pattern and mocking-convention verification
- `frontend/src/lib/api.ts` — grepped for `Profile`/`Session`/`Ride` TS interfaces (contract-mismatch verification)
- `.planning/research/APP-REVIEW-260703.md`, `.planning/REQUIREMENTS.md`, `.planning/STATE.md`, `.planning/ROADMAP.md` — full read (upstream inputs)

### Secondary (MEDIUM confidence)
- None — no external documentation lookups were needed for this phase; all findings are internal-codebase-verification, and `.planning/config.json` has all external-search providers (`brave_search`, `exa_search`, `firecrawl`, etc.) disabled, consistent with this being a pure internal-defect-repair phase requiring no new library research

### Tertiary (LOW confidence / ASSUMED)
- Plan Week-1-anchoring policy (A3), `trigger_session_ids` array-column vs. join-table choice (A1), macro-replan rejection/expiry policy (A2), `profiles.lthr` vs `lthr_estimate` dual-column policy (A5) — all flagged in Assumptions Log, none touch safety-critical (back-protective) logic

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, all existing patterns verified in repo
- Architecture (persistence hook location, PMC recompute design): MEDIUM-HIGH — the pure/impure boundary decision is directly supported by locked docstrings in the codebase; the specific recompute/idempotency mechanics are sound engineering but are this session's original design, not lifted from an existing pattern in the repo
- Pitfalls: HIGH — Pitfalls 1, 2, and 4 are newly-discovered, directly-verified schema/code defects (grep-confirmed absence of columns/constraint values across all 4 migration files), not speculative

**Research date:** 2026-07-03
**Valid until:** Until the next schema migration lands or `.planning/research/APP-REVIEW-260703.md` findings are superseded — recommend re-verifying migration state (`ls supabase/migrations/`) at planning time in case Phase 7+ work has already landed additional migrations by the time Phase 6 is planned/executed.
