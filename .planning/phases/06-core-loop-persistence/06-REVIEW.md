---
phase: 06-core-loop-persistence
reviewed: 2026-07-03T10:16:56Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - backend/agent/tools.py
  - backend/pmc_recompute.py
  - backend/routes/adaptations.py
  - backend/routes/rides.py
  - backend/sports_science/compliance.py
  - backend/sports_science/profile.py
  - supabase/migrations/0005_phase6_persistence.sql
  - tests/agent/test_tools_phase3.py
  - tests/api/test_adaptations.py
  - tests/api/test_rides.py
  - tests/test_pmc_recompute.py
findings:
  critical: 4
  warning: 12
  info: 6
  total: 22
status: issues_found
---

# Phase 6: Code Review Report

**Reviewed:** 2026-07-03T10:16:56Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Phase 6 delivers real improvements: the PMC recompute-from-scratch (backend/pmc_recompute.py) is correct on gap decay, same-day summation, and calendar-day counting; the content-hash dedup race is properly closed by the DB UNIQUE constraint with a fallback lookup; the FTP key fix and write-back are correct and tested; the confirm endpoint has proper IDOR dual-filtering; and server-side user_id injection into save_profile/generate_plan is well tested.

However, the adaptation core loop is structurally broken against real data. The plan persistence layer added this phase never writes `sessions.tss_target`, so every downstream consumer of that column (underperformance detection, ride compliance, micro/macro TSS adjustment) is inert or destructive. On top of that: the manual missed-session endpoint can never trigger an adaptation for the session it marks; the macro replan generator guarantees a 100% shift so the 30% guard fires on every macro replan; and unconfirmed proposals permanently consume their trigger sessions so lost signals never re-fire. These four defects compound: in production the adaptive re-planning feature effectively cannot complete an apply cycle end to end.

Purity check: `generate_plan` (sports_science/plan.py) and `update_pmc` (sports_science/pmc.py) remain pure and DB-free; persistence correctly lives in the orchestration layer. `save_profile` retains its own DB access as before (it is a persistence tool by design).

## Critical Issues

### CR-01: sessions.tss_target is never populated — underperformance detection, ride compliance, and TSS adjustments are dead against real data

**File:** `backend/agent/tools.py:479-497` (root cause), consumers at `backend/routes/adaptations.py:197-212, 404-412, 551-557` and `backend/routes/rides.py:317-322`
**Issue:** `generate_plan` sessions carry no TSS value at all (see `backend/sports_science/plan.py:153-163`), and `_persist_generated_plan` inserts session rows without `tss_target`. The column exists (migration 0003 added it "referenced by adaptations.py detect_signals") but no code path in the entire backend ever writes a real value into it. Consequences, all provable by tracing:
- `detect_signals` underperformance: `planned_tss = session.get("tss_target") or 0` → 0 → `validate_session_vs_actual` returns `compliance_pct=None` → the ADAPT-05 signal can never fire for any plan-generated session.
- `process_ride_background` (FIT-05): `matched_session.get("tss_target", 0)` → 0 → `rides.compliance_pct` is always persisted as NULL.
- `apply_micro_adjustment`: `new_tss = round((None or 0) * 0.8, 1)` → writes `tss_target = 0.0` over NULL, actively corrupting the column into a value that then makes future compliance 0-division-guarded forever.
- `apply_macro_replan`: same `new_tss = 0.0` for every session.
**Fix:** Have `generate_plan` emit a per-session `tss_target` (it already knows duration, zone, and RPE; a Coggan zone-2 TSS-per-hour estimate is a pure computation and belongs in the tool per the trust model), and persist it in `_persist_generated_plan`:
```python
# plan.py _build_sessions: add e.g.
"tss_target": round(duration / 60 * ZONE2_TSS_PER_HOUR, 1),
# tools.py _persist_generated_plan session_rows:
"tss_target": session["tss_target"],
```
Also guard `apply_micro_adjustment`/`apply_macro_replan` to skip TSS scaling when `tss_target` is None instead of writing 0.0.

### CR-02: POST /adaptations/sessions/{id}/missed can never generate a signal for the session it marks missed

**File:** `backend/routes/adaptations.py:841-855` (with `detect_signals` filter at line 144)
**Issue:** The endpoint flips the session's status to `'missed'`, then re-runs `detect_signals`. But `detect_signals` only loads sessions with `.in_("status", ["planned", "completed"])` — the session just marked `'missed'` is excluded from candidates, so it can never emit a missed signal. No signal is synthesized for it either, and it is never recorded in `trigger_session_ids`. Net effect: a user manually reporting a missed session produces `signals=[], scope=None, result=None` — no micro-adjustment ever happens, while the identical miss detected automatically by `/adaptations/check` does trigger one. The D-16 endpoint's primary purpose silently no-ops.
**Fix:** Synthesize the signal for the marked session and merge it with detection output:
```python
signals = await detect_signals(user_id)
manual = {"type": "missed", "session_id": session_id}
if session_id not in {s.get("session_id") for s in signals}:
    signals.append(manual)
scope = decide_scope(signals)
```
(Do the status flip after, or keep the flip and rely on the synthesized signal; ensure the adaptation logs `session_id` in `trigger_session_ids`.)

### CR-03: Macro replan always returns needs_confirmation — the auto-apply branch is unreachable dead code

**File:** `backend/routes/adaptations.py:549-559` (shift generator) and `check_shift_limit` at 298-299
**Issue:** The "progressive spacing" generator shifts session `i` by `i + 2` days, so even session 0 shifts by 2 days. `check_shift_limit` counts any shift `> 1` day as shifted, so every session with a parseable date is shifted → `shift_pct == 1.0 > 0.30` for every macro replan with at least one session. `requires_user_confirmation` is therefore always True: the entire apply branch (lines 611-662), including the `status='missed'` flips for missed-signal sessions and the "applied" adaptation log, is unreachable in production. This inverts ADAPT-03/D-19 semantics — the 30% guard was specified to discriminate large shifts from small ones, not to fire unconditionally. The code comment (lines 546-548) shows the generator was tuned so the guard "can fire" and overshot to "always fires". No test exercises the applied path, so this went undetected.
**Fix:** Make the reschedule proportional to the disruption rather than unconditionally ≥2 days, e.g. shift only sessions that conflict with recovery (or shift by `i // 2` days so early sessions stay within the 1-day tolerance), and add a test asserting a macro replan that shifts ≤30% of sessions returns `status="applied"`.

### CR-04: Unconfirmed/superseded proposals permanently consume trigger sessions — signals are silently lost forever

**File:** `backend/routes/adaptations.py:129-137` (consumed-ids query) with proposal insert at 592-602
**Issue:** The Pattern-5 consumed-ids pre-query reads `trigger_session_ids` from ALL adaptations rows with no status filter. A macro replan persists its proposal with `status='proposed'` and the triggering session ids (line 601). If the user never confirms — or the proposal is auto-superseded by the OQ1 update at lines 584-589 — those session ids remain in `trigger_session_ids` of a row that was never applied, so `detect_signals` skips them on every future check. Combined with CR-03 (every macro is a proposal), any macro-scale disruption the user ignores is permanently dropped: the sessions stay `'planned'`, past-due, unadjusted, and undetectable. Training-plan adaptation data is effectively lost.
**Fix:** Scope consumption to adaptations that were actually acted on:
```python
consumed_resp = await (
    supabase.table("adaptations")
    .select("trigger_session_ids")
    .eq("user_id", user_id)
    .in_("status", ["applied", "proposed"])   # exclude superseded
    .execute()
)
```
and clear/ignore `trigger_session_ids` when a proposal is superseded (or filter to `applied` plus only the single currently-pending `proposed` row).

## Warnings

### WR-01: dispatch_tool honors LLM-supplied user_id when the caller passes user_id=None

**File:** `backend/agent/tools.py:532-533`
**Issue:** Injection only happens `if user_id is not None`. `run_turn`/`dispatch_tool` default `user_id=None`, and the tool input schemas not declaring `user_id` does not prevent the model from emitting one (Anthropic does not enforce `additionalProperties: false`). If any current or future call path omits `user_id`, an LLM-emitted `user_id` flows straight into `save_profile(**inputs)` and is written with the service-role key (RLS bypass) — a prompt-injection-to-cross-user-write path. Today `chat.py` always passes it, so this is defense-in-depth, but the failure mode is silent.
**Fix:** Fail closed: for `save_profile`/`generate_plan`, strip any inbound `user_id` unconditionally and error when no server-side identity is available:
```python
if name in {"save_profile", "generate_plan"}:
    inputs = {k: v for k, v in inputs.items() if k != "user_id"}
    if user_id is None:
        return _error_block(tool_use_id, "server identity required for this tool")
    inputs["user_id"] = user_id
```

### WR-02: Week-1 roll-forward creates duplicate scheduled_dates colliding with Week 2

**File:** `backend/agent/tools.py:429-435`
**Issue:** A Week-1 session whose weekday precedes `confirm_date` is rolled +7 days, landing on the exact same date as the Week-2 session for that weekday (both resolve to Monday-of-week-1 + 1 week + day offset). Result: two `'planned'` sessions on one date. The ride-session link (`rides.py:308-316`) uses `.limit(1)` with no `.order()`, so which session gets completed is arbitrary; `_find_matching_ride`'s `day_rides[0]` fallback then treats the other as satisfied too, suppressing a legitimate missed signal.
**Fix:** When rolling a Week-1 session forward, detect the collision with the Week-2 session on the same weekday and either drop the Week-1 session or place it on the nearest free day. Add a deterministic `.order("scheduled_date")`/tiebreak to the session-link query.

### WR-03: No supersede of the prior active plan — active plans and stale sessions accumulate

**File:** `backend/agent/tools.py:455-470`
**Issue:** `_persist_generated_plan` inserts a new `plans` row with `status='active'` without superseding any existing active plan (the schema has a `'superseded'` status for exactly this). Every re-run of the interview or re-plan stacks another active plan whose old `'planned'` sessions remain live: they generate false missed signals in `detect_signals`, compete for ride-session links, and pollute `/sessions` views.
**Fix:** Before the insert:
```python
await supabase.table("plans").update({"status": "superseded"}).eq("user_id", user_id).eq("status", "active").execute()
await supabase.table("sessions").update({"status": "skipped"}).eq("user_id", user_id).eq("status", "planned").execute()
```

### WR-04: raw_fit_path recorded with bucket prefix that does not match the stored object key

**File:** `backend/routes/rides.py:530-538, 564`
**Issue:** The object is uploaded to bucket `"fits"` at key `f"{user_id}/{content_hash}.fit"`, but `raw_fit_path` is persisted as `f"fits/{user_id}/{content_hash}.fit"`. Any future `storage.from_("fits").download(raw_fit_path)` (reprocessing, backfill — explicitly anticipated by T-03-15) will 404 because the bucket name is duplicated in the key.
**Fix:** Persist the actual object key: `storage_path = f"{user_id}/{content_hash}.fit"` (bucket is implied by the `from_("fits")` call), and use one variable for both the upload and the DB row so they cannot diverge.

### WR-05: detect_signals ride-window off-by-one causes false missed signals at the window edge

**File:** `backend/routes/adaptations.py:152-158` vs `_find_matching_ride` at 80-92
**Issue:** Rides are loaded with `.gte("ride_date", window_start)`, but `_find_matching_ride` checks `sched - 1 day`. A session scheduled exactly on `window_start` whose ride happened the day before falls outside the ride query, so the session is falsely flagged missed (and, per Pattern 5, permanently consumed once an adaptation logs it).
**Fix:** Widen the ride query by the match tolerance: `.gte("ride_date", (window_start - timedelta(days=1)).isoformat())`.

### WR-06: Underperformance false-fires at 0% when the matched ride's TSS is NULL

**File:** `backend/routes/adaptations.py:198-212`
**Issue:** `actual_tss = found_ride.get("tss") or 0`. A completed session matched to a ride whose pipeline failed to compute TSS (rides.tss NULL — a real state, since `process_ride_background` logs-and-continues on failure) produces `compliance_pct = 0 < 60` → a spurious underperformance signal that can trigger a real plan reduction.
**Fix:** Skip the check when the ride has no TSS: `if found_ride.get("tss") is None: continue`.

### WR-07: Underperformance threshold hardcoded at 60 while the tool flags under_performed at 70 — comment claims the opposite

**File:** `backend/routes/adaptations.py:206-207` vs `backend/sports_science/compliance.py:21-22`
**Issue:** The route comment says "The compliance threshold decision comes from the tool result, not a hardcoded literal", yet the route compares `compliance_pct < 60` — a hardcoded literal that ignores the tool's own `under_performed` flag (which fires at `< 70`). Two divergent thresholds now exist for the same concept; a 65%-compliance session is flagged `under_performed` by the tool but not a signal in the route.
**Fix:** Use the tool's flag as the decision source: `if "under_performed" in result.value.get("flags", []):` — or, if 60 is the intended ADAPT-05 threshold, move it into `compliance.py` as a named constant and delete the misleading comment.

### WR-08: Adaptation calendar sync is dead code, and it relies on BackgroundTasks despite the Vercel constraint

**File:** `backend/routes/adaptations.py:376-384, 491-499` (selects), `725-733, 858-865` (sync)
**Issue:** Two independent defects: (1) The session SELECTs in `apply_micro_adjustment` and `apply_macro_replan` fetch `"id, scheduled_date, tss_target, duration_minutes, status"` — never `calendar_event_id` — so `session.get("calendar_event_id")` and the `before_by_id` fallback are always None and `update_calendar_event` is never scheduled. CAL-02 sync after adaptation is unreachable. (2) Even if it were reachable, `background_tasks.add_task` is used, which Vercel freezes after the response — the same constraint that forced the rides pipeline to inline-await in this very phase.
**Fix:** Add `calendar_event_id` to both SELECT column lists, and inline-await the calendar update in a best-effort try/except (matching the rides pipeline pattern) instead of BackgroundTasks.

### WR-09: pmc_recompute date parsing sits outside the try blocks, violating the documented never-raise contract

**File:** `backend/pmc_recompute.py:79-84`
**Issue:** The docstring promises a failure "is logged loudly ... but never raised out: the caller inline-awaits this from the upload path and a PMC failure must not fail the whole upload." But only the read and the upsert are guarded. `date.fromisoformat(r["ride_date"])` (line 81) raises `ValueError` on any non-`YYYY-MM-DD` value (e.g. a timestamptz string after a schema/type drift) and propagates out of the function. Today the outer `process_ride_background` catch masks it, but the module's own contract is broken and any future direct caller inherits the risk.
**Fix:** Wrap the grouping/walk in the same try/except-log pattern, or parse defensively: `date.fromisoformat(str(r["ride_date"])[:10])` inside a per-row try that skips malformed rows.

### WR-10: _persist_generated_plan is non-atomic — a sessions-insert failure orphans an active plans row

**File:** `backend/agent/tools.py:455-506`
**Issue:** The `plans` insert commits before the `sessions` insert. If the sessions insert fails (constraint, transient error), the exception surfaces as a tool error (correct per D-14) but the `plans` row remains `status='active'` with zero session rows. The LLM's natural retry then creates a second active plan (compounding WR-03). There is no transaction and no compensating delete.
**Fix:** On sessions-insert failure, best-effort delete or mark the orphan before re-raising:
```python
try:
    sessions_insert = await supabase.table("sessions").insert(session_rows).execute()
except Exception:
    await supabase.table("plans").delete().eq("id", plan_id).execute()
    raise
```
Also note `sessions_insert.data` shorter than `sessions` would silently leave trailing sessions without ids — assert `len(sessions_insert.data) == len(sessions)`.

### WR-11: Session UPDATEs by id without user_id filter — inconsistent with the codebase's own dual-filter rule

**File:** `backend/routes/adaptations.py:408-412, 613-616, 841`
**Issue:** The phase explicitly adopts dual-filtering (`.eq("id").eq("user_id")`) "for defence-in-depth" on the missed-status flips (lines 434-439, 621-627) and the confirm endpoint (790-793), but the micro TSS update (408-412), the macro apply update (613-616), and the `mark_session_missed` status update (841) filter by `id` alone. The ids come from user-scoped reads so there is no exploit today, but the mark-missed case is a TOCTOU pattern (ownership checked in a prior query, then updated unscoped) and all three run under the service-role key where the WHERE clause is the only tenant boundary.
**Fix:** Append `.eq("user_id", user_id)` to all three updates.

### WR-12: test_session_compliance passes vacuously and masks CR-01

**File:** `tests/api/test_rides.py:530-613`
**Issue:** The mocked session row is `{"tss": 50.0, "session_type": "endurance"}` — it has neither `tss_target` nor `id`, the two fields the production code actually reads. So `matched_session.get("tss_target", 0)` yields 0 → `compliance_pct=None`, and `matched_session["id"]` raises KeyError inside the swallowed try. The assertion `"compliance_pct" in ride_payload` still passes because the key is present with value None. The test therefore certifies FIT-05 while exercising the exact NULL-compliance failure mode of CR-01.
**Fix:** Use a realistic row (`{"id": "sess-1", "tss_target": 50.0, "type": "endurance"}`) and assert `ride_payload["compliance_pct"] is not None` and approximately equal to the expected percentage.

## Info

### IN-01: Stale module docstring — claims 8 tool schemas, there are 10

**File:** `backend/agent/tools.py:5`
**Issue:** "TOOL_SCHEMAS: 8 manual Anthropic tool schema dicts" — save_profile and generate_plan make it 10 (the TRUST-02 test asserts 10).
**Fix:** Update the docstring.

### IN-02: plans.ftp_confidence is always NULL

**File:** `backend/agent/tools.py:462-465`
**Issue:** `plan_value.get("ftp_confidence")` is always None because `generate_plan` puts confidence in `ToolResult.inputs`, not `value`. The column exists precisely to record confidence at plan-generation time and is never populated. The code comment acknowledges this instead of fixing it — `dispatch_tool` has `result.inputs` in hand and could pass it through.
**Fix:** Pass `result.inputs.get("ftp_confidence")` into `_persist_generated_plan` as a parameter.

### IN-03: plans.sessions JSONB snapshot lacks session ids

**File:** `backend/agent/tools.py:455-506`
**Issue:** The `plans.sessions` JSONB is inserted before the sessions rows exist, so the stored snapshot never contains the session ids that the tool_result (and the LLM) sees. Anyone reconciling `plans.sessions` against the `sessions` table cannot join them.
**Fix:** Either update the plans row after id assignment, or accept and document the asymmetry.

### IN-04: Unused import and unused parameter

**File:** `backend/routes/adaptations.py:43`; `backend/routes/rides.py:449`
**Issue:** `delete_calendar_event` is imported but never used in adaptations.py. `background_tasks: BackgroundTasks` in `upload_fit` is a leftover from the pre-inline-await pipeline and is never referenced.
**Fix:** Remove both.

### IN-05: Duplicate Supabase singleton in profile.py

**File:** `backend/sports_science/profile.py:19-44`
**Issue:** `profile.py` maintains its own module-level async client cache separate from `backend.db.get_async_supabase`, doubling connection pools and env-var handling. (Kept out of sports_science purity debates since save_profile is a persistence tool by design, but the client should be shared.)
**Fix:** Import and use `backend.db.get_async_supabase` — tests already monkeypatch at module level and would need a one-line adjustment.

### IN-06: confirm endpoint does not flip missed trigger sessions or guard against stale snapshots

**File:** `backend/routes/adaptations.py:742-804`
**Issue:** The direct-apply macro path flips missed-signal sessions to `'missed'` (lines 620-627); the confirm path applies only `tss_target`/`scheduled_date` from the snapshot, so trigger sessions stay `'planned'` (harmless today only because Pattern 5 consumption suppresses them — see CR-04). It also applies a possibly-stale snapshot by design without checking whether the sessions still exist or changed; documented as intended, noting it here for the record.
**Fix:** On confirm, replay the missed-status flips for the proposal's `trigger_session_ids`.

---

_Reviewed: 2026-07-03T10:16:56Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
