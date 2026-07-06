---
phase: 03-coaching-loop
reviewed: 2026-07-06T00:00:00Z
depth: standard
files_reviewed: 17
files_reviewed_list:
  - backend/agent/loop.py
  - backend/agent/tools.py
  - backend/main.py
  - backend/routes/_sse.py
  - backend/routes/adaptations.py
  - backend/routes/chat.py
  - backend/routes/onboarding.py
  - backend/routes/rides.py
  - backend/sports_science/plan.py
  - backend/sports_science/profile.py
  - supabase/migrations/0002_phase3_schema.sql
  - tests/agent/fixtures/trust_corpus.py
  - tests/agent/test_tools_phase3.py
  - tests/api/__init__.py
  - tests/api/conftest.py
  - tests/api/test_adaptations.py
  - tests/api/test_onboarding.py
  - tests/api/test_rides.py
findings:
  critical: 1
  warning: 6
  info: 1
  total: 8
status: issues_found
---

# Phase 03: Code Review Report

**Reviewed:** 2026-07-06T00:00:00Z
**Depth:** standard
**Files Reviewed:** 17
**Status:** issues_found

## Summary

This review focused on the agent/tool-dispatch trust boundary (`loop.py`, `tools.py`) and the
onboarding/chat/adaptations/rides routes, per the re-verification brief. No path was found where
an LLM-authored physiological number reaches a user-facing response without first passing the
`trust_scanner` gate in `loop.py` — the buffer-then-scan-then-yield sequencing (TRUST-03/Pitfall 5)
is implemented correctly, and the `generate_plan`/`save_profile` server-side injection allowlist in
`dispatch_tool` is thorough and well covered by tests for the sequential case.

However, one genuine data-integrity BLOCKER was found in the scheduling math (`plan.py` +
`tools.py`), which — under realistic onboarding inputs — silently creates two distinct sessions on
the identical `scheduled_date`, defeating the "no two sessions share a date" invariant the code
explicitly documents and claims to test for. Several WARNING-level gaps were also found: a latent
race condition in the same-turn trust-sensitive injection for `generate_plan` when tools are
dispatched in parallel (AGENT-02/D-12) rather than sequentially, a persistence-atomicity gap when
persisting a generated plan, an inconsistent defense-in-depth filter in one adaptations write, an
unused/dead filename-sanitization function whose doc comments claim it's an active threat
mitigation, an unverified self-reported LTHR value in onboarding Branch A, and an SSE persistence
bug that can save partial/incomplete assistant text to the messages table as if the turn had
completed successfully.

## Critical Issues

### CR-01: Duplicate `scheduled_date` across sessions when `preferred_days` is shorter than the weekly session count

**File:** `backend/sports_science/plan.py:132-135` (produced) and `backend/agent/tools.py:455-494` (persisted without full collision handling)

**Issue:**
`_build_sessions` in `plan.py` deliberately cycles through `preferred_days` when it has fewer
entries than `n_sessions` (the WR-01 comment even gives the example): with `weekly_hours > 3.0`
(`n_sessions = 4`) and `preferred_days = ["Tuesday", "Thursday"]`, the per-week day list becomes
`[Tuesday, Thursday, Tuesday, Thursday]`. The outer loop (`for week in range(1, 5): for i, day in
enumerate(days):`) then builds **two distinct sessions in the same week on the same weekday**
(e.g. two separate "Tuesday" sessions in week 1, each with different content/intensity).

`_resolve_all_scheduled_dates` in `tools.py` (WR-02) only special-cases collisions caused by the
Week-1 roll-forward (`session["week"] == 1 and target < confirm_date`); its "first pass" assigns
`resolved[i] = target` and adds it to `used` for every *non-rolled* session **without checking
`used` for a pre-existing collision**. Since the two same-week/same-weekday sessions described
above are both non-rolled, they both resolve to the exact same naive date and both get silently
added to `used` — producing two `sessions` rows with an identical `scheduled_date`.

This directly contradicts the function's own docstring ("no two sessions ever share a
scheduled_date") and breaks downstream logic that assumes one planned session per date:
- `rides.py`'s ride-session link query (`.eq("scheduled_date", ride_date).eq("status",
  "planned").order("id", desc=False).limit(1)`) will only ever match one of the two same-date
  sessions to an uploaded ride; the other can never be linked.
- `adaptations.detect_signals`'s missed-session check will then perpetually flag the un-matchable
  sibling session as `"missed"` even though the user actually rode that day, because
  `_find_matching_ride` can only attach one ride per date.

No test exercises this path: `test_week1_rollforward_avoids_week2_collision` and
`test_resolve_all_dates_no_roll_matches_single_resolver` only cover the week-1-roll collision case,
and every `generate_plan` test in `test_tools_phase3.py` either omits `preferred_days` (falling
back to the 4-entry `_DEFAULT_DAYS`) or uses `weekly_hours` values whose `n_sessions` never exceeds
the supplied `preferred_days` length.

**Fix:**
Make `_resolve_all_scheduled_dates` collision-aware for *all* sessions, not just rolled week-1
ones — e.g. process every session in order and push the target date forward to the earliest free
date whenever `target in used`, instead of only doing this fan-out for the roll-forward branch:

```python
resolved: list[date | None] = [None] * len(sessions)
used: set[date] = set()
for i, (session, target) in enumerate(zip(sessions, naive)):
    needs_roll = session["week"] == 1 and target < confirm_date
    candidate = target + timedelta(days=7) if needs_roll else target
    while candidate in used:
        candidate += timedelta(days=1)
    resolved[i] = candidate
    used.add(candidate)
```

Alternatively (or additionally), fix the root cause in `plan.py`'s `_build_sessions` so the same
weekday is never assigned twice within a single week when `preferred_days` is shorter than
`n_sessions` (e.g. distribute the "extra" sessions across different days each week instead of
repeating the same short cycle within one week).

## Warnings

### WR-01: `dispatch_tool`'s same-turn trust-sensitive injection for `generate_plan` races against parallel tool dispatch

**File:** `backend/agent/tools.py:734-753` combined with `backend/agent/loop.py:253-261`

**Issue:** `loop.py` dispatches every unique tool_use block from one assistant turn concurrently via
`asyncio.gather` (AGENT-02/D-12). `dispatch_tool`'s `generate_plan` branch sources
`ftp_watts`/`ftp_confidence`/`load_targets`/`hr_zones` from **this turn's in-memory `audit_log`**
(`_last_audit_result`), falling back to safe cold-start defaults (`insufficient_data`, `[]`) when no
matching entry exists yet. If the model ever emits `calculate_hr_zones`/`progress_load`/
`estimate_ftp_from_rides` in the *same* tool_use batch as `generate_plan` (which the API and this
codebase's own AGENT-02 parallel-dispatch design permit), the coroutines run concurrently and there
is no guarantee the dependency tool's coroutine has appended to `audit_log` by the time
`generate_plan`'s coroutine reaches its `_last_audit_result` lookup — `generate_plan`'s own
coroutine does two awaited Supabase round-trips (`pmc_history`, `profiles`) before that lookup,
while the dependency tools are fast synchronous compute functions dispatched via
`asyncio.to_thread`, so the ordering is a real (if currently favorable) race, not a guarantee. All
existing TRUST-07 tests (`test_generate_plan_injection_uses_same_turn_ftp_and_load_entries`, etc.)
pre-populate `audit_log` before calling `dispatch_tool`, i.e. they only exercise the sequential
case and never the concurrent-dispatch scenario this code explicitly supports.

**Fix:** Either (a) have `loop.py` detect when `generate_plan` is present in the same dispatch
batch as one of its prerequisite tools and force those prerequisites to be awaited to completion
before dispatching `generate_plan`, or (b) have `dispatch_tool` reject/defer a `generate_plan` call
whenever a prerequisite tool_use block is present in the *same* batch rather than relying on
`audit_log` state that may not exist yet.

### WR-02: No transactional integrity when persisting a generated plan

**File:** `backend/agent/tools.py:497-578` (`_persist_generated_plan`)

**Issue:** `_persist_generated_plan` performs two independent, non-atomic Supabase requests: insert
one `plans` row, then insert all `sessions` rows. If the `sessions` insert fails (e.g. a future
unique constraint, a transient network error, or malformed row data) after the `plans` insert has
already succeeded, the exception propagates to `dispatch_tool`'s outer `except`, which returns an
`is_error` tool result — but the `plans` row already committed with `status='active'` and zero
sessions is never cleaned up or marked superseded. A retried `generate_plan` call would then create
a second `active` plan row for the same user, compounding the orphaned-row problem.

**Fix:** Wrap the two inserts in a single Postgres transaction (e.g. an RPC/stored procedure that
inserts both in one call), or add explicit cleanup: on a `sessions` insert failure, delete or mark
the just-inserted `plans` row as `superseded` before re-raising.

### WR-03: `mark_session_missed`'s status-flip UPDATE omits the `user_id` defense-in-depth filter

**File:** `backend/routes/adaptations.py:905`

**Issue:** Every other session-mutating UPDATE in this file dual-filters by `id` and `user_id`
(e.g. `apply_micro_adjustment`'s missed-flip at line 466-471, `apply_macro_replan`'s missed-flip at
line 665-673). `mark_session_missed`'s own status-flip breaks that pattern:

```python
await supabase.table("sessions").update({"status": "missed"}).eq("id", session_id).execute()
```

Ownership was verified moments earlier via a separate SELECT, so this is not an immediate IDOR (no
cross-user write is currently reachable), but it removes the defense-in-depth guarantee documented
at the top of the file ("Backend writes use SERVICE_ROLE_KEY... Reads filtered by user_id... T-04-04")
and introduces a TOCTOU gap versus the rest of the module's consistent dual-filter convention.

**Fix:**
```python
await (
    supabase.table("sessions")
    .update({"status": "missed"})
    .eq("id", session_id)
    .eq("user_id", user_id)
    .execute()
)
```

### WR-04: `_sanitize_filename` is dead code; the module's documented threat mitigation (T-03-13) is not actually wired up

**File:** `backend/routes/rides.py:418-431` (definition), never invoked anywhere in `upload_fit` (`backend/routes/rides.py:450-625`)

**Issue:** The module docstring and header comment both claim "Filename is sanitized before use in
Storage path (T-03-13: no path traversal)" and list "T-03-13: filename sanitized with
os.path.basename + re.sub" as an applied threat mitigation. In the actual `upload_fit` handler, the
Storage path is built entirely from `user_id` and `content_hash` (`storage_path =
f"{user_id}/{content_hash}.fit"`, line 537) — `file.filename` is never read and
`_sanitize_filename` is never called. There is currently no live path-traversal vector because the
object key is content-addressed, not filename-derived, but the docstring is misleading: a future
reviewer (or this very re-verification) could reasonably conclude a filename-sanitization
mitigation is active when it is dead code.

**Fix:** Either delete `_sanitize_filename` and update the docstring/threat-mitigation notes to
state the real mitigation (content-addressed storage keys make the original filename irrelevant),
or actually use the sanitized filename somewhere meaningful (e.g. storing it as display metadata on
the `rides` row) so the documented mitigation is truthful.

### WR-05: Onboarding Branch A's self-reported LTHR is persisted to `save_profile` with no cross-check against the conversation transcript

**File:** `backend/agent/tools.py:777-791` (CR-02 lthr override block)

**Issue:** `dispatch_tool`'s `save_profile` branch only overrides `lthr_estimate` when this turn's
`audit_log` carries an `estimate_lthr_from_max_hr` result (Branch B). In Branch A (user states LTHR
directly), the LLM-supplied `lthr_estimate` argument passes through to the `save_profile` upsert
completely unverified — nothing cross-checks that the numeric value matches what the user actually
typed. The `self_reported_values`/`trust_scanner` mechanism in `loop.py` (08-08/D-02/D-05) only
guards the assistant's free-text *response*, not the *arguments* of a tool call; a hallucinating
model could in principle invent an LTHR value in Branch A and have it written straight to
`profiles.lthr_estimate`/`profiles.lthr` with no server-side or transcript-based validation,
despite the project's stated principle that physiological data must be provably sourced.

**Fix:** At minimum, document this as a known/accepted architectural limitation (tool-call
arguments are trusted, only free text is scanned). If stronger guarantees are desired, extend the
`self_reported_values` mechanism to also validate that Branch A's `lthr_estimate` argument appears
as a number in the collected self-reported user text before allowing it through to `save_profile`.

### WR-06: SSE error paths still persist partial assistant text to the messages table as if the turn completed successfully

**File:** `backend/routes/_sse.py:96-110`

**Issue:** `sse_generator`'s `try` block appends to `assistant_sink` once the `async for event in
fn(...)` loop finishes *without raising an exception* — but `run_turn` (`loop.py`) yields its
`"max_tool_turns"` and `"unexpected_stop"` error conditions via a normal `yield` followed by
`return`, not via a raised exception. The code comment ("Stream completed successfully -- publish
to sink if provided" / "Do NOT append to assistant_sink on the error path") only distinguishes
based on whether a Python exception propagated, not on whether the *last SSE event* was `"error"`.
Consequently, when a turn ends via `unexpected_stop` (e.g. Claude hit `max_tokens` mid-sentence) or
`max_tool_turns`, any tokens streamed in earlier, trust-scan-passed rounds of that same turn are
still concatenated and persisted to the `messages` table via `save_messages` as a normal
`"assistant"` message — even though the turn is known to have ended abnormally/incompletely. This
pollutes conversation history with truncated replies that get reloaded as prior context on the next
turn (`load_conversation`), which can confuse subsequent model reasoning (e.g. the model appears to
have already said something it never finished saying).

**Fix:** Have `run_turn` communicate turn-level success vs. failure explicitly (e.g. a sentinel
final event, or by not yielding `"error"` conditions through the same channel as recoverable ones),
and have `sse_generator` skip the `assistant_sink.append(...)` call whenever the last event yielded
was `"error"`:

```python
last_event_type = None
async for event in fn(...):
    last_event_type = event["event"]
    ...
if assistant_sink is not None and last_event_type != "error":
    assistant_sink.append(accumulated_text)
```

## Info

### IN-01: Mutable Pydantic model instance used as a route default argument

**File:** `backend/routes/onboarding.py:272`

**Issue:** `body: OnboardingStartBody = OnboardingStartBody()` uses a single shared instance,
evaluated once at import time, as the default for every request that omits a body. Current code
only reads from `body` (never mutates it), so there is no live bug today, but this is a classic
Python foot-gun (shared mutable default) that would silently start leaking state across requests if
any future change mutated `body` in place.

**Fix:** Use `body: OnboardingStartBody | None = None` and construct a fresh
`OnboardingStartBody()` inside the handler when `body is None`, or rely on FastAPI's own
per-request model instantiation (`body: OnboardingStartBody = Depends()` / a `Body(default=None)`
pattern) rather than a shared default instance.

---

_Reviewed: 2026-07-06T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
