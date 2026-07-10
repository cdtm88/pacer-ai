---
phase: 08-trust-model-integrity
reviewed: 2026-07-04T00:00:00Z
depth: standard
files_reviewed: 18
files_reviewed_list:
  - backend/agent/audit.py
  - backend/agent/loop.py
  - backend/agent/tools.py
  - backend/agent/trust.py
  - backend/routes/_sse.py
  - backend/routes/chat.py
  - backend/routes/onboarding.py
  - backend/sports_science/constants.py
  - backend/sports_science/plan.py
  - backend/sports_science/profile.py
  - backend/sports_science/zones.py
  - supabase/migrations/0009_audit_log_and_hr_zones_flag.sql
  - tests/agent/test_audit.py
  - tests/agent/test_loop.py
  - tests/agent/test_tools_phase3.py
  - tests/agent/test_trust.py
  - tests/api/test_onboarding.py
  - tests/sports_science/test_plan.py
  - tests/sports_science/test_zones.py
findings:
  critical: 3
  warning: 4
  info: 0
  total: 7
status: issues_found
---

# Phase 8: Code Review Report

**Reviewed:** 2026-07-04T00:00:00Z
**Depth:** standard
**Files Reviewed:** 18
**Status:** issues_found

## Summary

Phase 8's audit-log persistence, cross-turn seeding, and the 5-key server-injection
block in `dispatch_tool` (current_ctl, ftp_watts, ftp_confidence, load_targets,
preferred_days) are all correctly implemented: `write_audit_entry` and
`load_prior_audit_values` are genuinely fenced by top-level `try/except` blocks that
can never raise, and the five explicitly-named trust-sensitive `generate_plan` inputs
are unconditionally discarded and replaced from durable/in-memory server sources with
no path for an LLM-supplied value to reach `generate_plan()`.

However, the *scope* of "trust-sensitive values requiring server injection" was drawn
too narrowly. Two more physiological inputs flow from the LLM's tool call straight
into a persisted plan with no verification against this turn's tool results: `hr_zones`
(generate_plan) and `lthr_estimate` (save_profile, onboarding Branch B). Both are
exactly the kind of "number-laundering through tool calls" this phase was built to
close, and neither is covered by the existing discard/override logic. Additionally,
`/chat/stream` threads a raw, unvalidated client-supplied `conversation_id` into
`dispatch_tool`'s audit writes and `save_messages`, unlike the ownership-verified
`_resolve_conversation_id` path phase 07 added to onboarding — an asymmetry that lets
a client point the durable audit trail and message history at a conversation_id it
does not own.

## Critical Issues

### CR-01: `generate_plan`'s `hr_zones` input is never server-verified — LLM can inject fabricated HR-zone numbers into the persisted plan

**File:** `backend/agent/tools.py:729-748` (injection block), `backend/sports_science/plan.py:51-61` (`_build_zone2_targets`), `backend/routes/onboarding.py:81-84` (Branch C prompt)

**Issue:** `dispatch_tool`'s generate_plan injection block explicitly discards and
overrides only `current_ctl`, `ftp_watts`, `ftp_confidence`, `load_targets`, and
`preferred_days`. `hr_zones` — a list of `{zone, lower_bpm, upper_bpm}` dicts that is
just as "physiological" as any of those five — passes straight through from
`tool_use_block.input` with zero verification against this turn's
`calculate_hr_zones` audit_log entry. `_build_zone2_targets` (plan.py) then copies
`lower_bpm`/`upper_bpm` verbatim into every session's `zone_targets`, which
`_persist_generated_plan` writes to the `sessions` table and the frontend later
displays as an authoritative training target — i.e. exactly the "LLM never emits
physiological numbers directly" invariant CLAUDE.md's Architecture constraint exists
to prevent.

This is not theoretical: onboarding Branch C ("neither LTHR nor max HR known")
explicitly instructs the model to "SKIP calculate_hr_zones entirely" (line 83), yet
`generate_plan`'s schema still lists `hr_zones` as a **required** input
(`backend/agent/tools.py:367-371`) with no guidance in the prompt for what to supply
when no HR-zone tool was ever called. The model is left to either violate the
required-field schema or fabricate zone bpm values for a case the trust model was
specifically designed to prevent.

**Fix:**
```python
# backend/agent/tools.py, inside the generate_plan injection block, alongside
# the ftp_entry/load_entry lookups:
hr_zones_entry = _last_audit_result(audit_log, "calculate_hr_zones")
hr_zones_value = (hr_zones_entry or {}).get("value") or []

inputs = {
    k: v
    for k, v in inputs.items()
    if k not in {
        "current_ctl", "ftp_watts", "ftp_confidence", "load_targets",
        "preferred_days", "hr_zones",
    }
}
inputs = {
    **inputs,
    "current_ctl": current_ctl,
    "ftp_watts": ftp_watts,
    "ftp_confidence": ftp_confidence,
    "load_targets": load_targets,
    "preferred_days": preferred_days,
    "hr_zones": hr_zones_value,  # [] when Branch C skipped the tool this turn
}
```
Also update the onboarding prompt / schema so `hr_zones` is not silently required
when Branch C is taken (e.g. make it optional, defaulting to `[]` server-side).

---

### CR-02: `save_profile`'s `lthr_estimate` is never cross-checked against `estimate_lthr_from_max_hr`'s result — a full number-laundering path remains open

**File:** `backend/agent/tools.py:616-645`, `backend/routes/onboarding.py:76-80` (Branch B)

**Issue:** `dispatch_tool` only strips/re-injects `user_id` for `save_profile`
(`inputs = {k: v for k, v in inputs.items() if k != "user_id"}` then
`inputs = {**inputs, "user_id": user_id}`). `lthr_estimate` — the one field in
`save_profile`'s schema that is explicitly meant to be *tool-derived* in Branch B
("call the `estimate_lthr_from_max_hr` tool ... Use that tool's returned LTHR as
`lthr_estimate` when you call `save_profile`") — passes through completely
unverified. Nothing in `dispatch_tool` confirms the value the LLM supplies for
`lthr_estimate` actually matches this turn's `estimate_lthr_from_max_hr` audit_log
result.

Because `save_profile` persists this value directly to `profiles.lthr_estimate` /
`profiles.lthr`, and those columns then seed every subsequent `calculate_hr_zones`
call for the user's entire training plan, an LLM that supplies a fabricated LTHR
(whether from a reasoning error or content in the user's own message) launders an
unsourced physiological number into the one table this phase's whole security model
is meant to keep authoritative.

**Fix:** In `dispatch_tool`'s `save_profile` branch, when this turn's `audit_log`
contains an `estimate_lthr_from_max_hr` entry, override `lthr_estimate` from that
result (mirroring the `generate_plan` ftp_watts pattern); when Branch A applies
(user-stated LTHR, no tool call expected) leave the LLM-supplied value as-is since
it is a legitimate self-report, not a computed value — but the two cases need to be
distinguishable server-side rather than trusting the LLM's choice unconditionally.

---

### CR-03: `/chat/stream` threads an unvalidated client-supplied `conversation_id` into audit writes and message persistence

**File:** `backend/routes/chat.py:69-131`

**Issue:** `chat_stream` takes `conversation_id` directly from the query string with
no format or ownership validation, then:
- passes it to `sse_generator(...)` → `run_turn(...)` → `dispatch_tool(...)`, which
  calls `write_audit_entry(user_id=user_id, conversation_id=conversation_id, ...)`
  (writing durable `audit_log` rows keyed to whatever `conversation_id` the caller
  supplied), and
- passes it to `save_messages(conversation_id, user_id, new_turns)` (line 120),
  inserting new `messages` rows against that same unverified id.

`load_conversation` does re-filter by `.eq("user_id", user_id)` so a foreign/garbage
`conversation_id` cannot be used to *read* another user's history — but nothing stops
a client from supplying another user's real `conversation_id` (or a syntactically
valid but non-existent one) and having their own turn's audit rows and message rows
persisted under it. This is exactly the class of bug `backend/routes/onboarding.py`'s
`_resolve_conversation_id` (WR-08, phase 07) was written to close, but that fix was
never applied to the coaching endpoint — an asymmetric, easily-missed gap that
directly affects the audit trail this phase introduces as the trust model's
durable source of truth, and undermines the "cross-turn seeding scoped to the right
conversation" guarantee this phase's task explicitly calls out.

**Fix:** Extract `onboarding.py`'s `_resolve_conversation_id` (format validation +
ownership check, falling back to `None`/"treat as absent" on any failure) into a
shared helper and apply it in `chat_stream` before `conversation_id` is used for
`load_conversation`, `sse_generator`, or `save_messages`.

## Warnings

### WR-01: `_build_sessions` silently drops sessions when `preferred_days` is shorter than the computed session count

**File:** `backend/sports_science/plan.py:127`

**Issue:** `days = (preferred_days or _DEFAULT_DAYS)[:n_sessions]` only falls back to
`_DEFAULT_DAYS` when `preferred_days` is empty/None. If a user supplies, say, 2
preferred days while `weekly_hours` computes `n_sessions=4`, `days` has only 2
entries, and `for i, day in enumerate(days)` silently generates a 2-session-per-week
plan instead of 4 — with no top-up/cycling to reach `n_sessions`. No test in
`tests/sports_science/test_plan.py` or `tests/agent/test_tools_phase3.py` exercises
`len(preferred_days) < n_sessions`.

**Fix:** When `len(preferred_days) < n_sessions`, cycle through `preferred_days`
(or pad from `_DEFAULT_DAYS`) to reach `n_sessions`, e.g.
`days = [preferred_days[i % len(preferred_days)] for i in range(n_sessions)]` when
`preferred_days` is non-empty.

### WR-02: `plans.ftp_confidence` is permanently written as `NULL`

**File:** `backend/agent/tools.py:512-517`, `backend/sports_science/plan.py:288-297`

**Issue:** `_persist_generated_plan` sets
`"ftp_confidence": plan_value.get("ftp_confidence")`, but `generate_plan`'s returned
`value` dict (plan.py's `ToolResult(value={...})`) never contains an
`ftp_confidence` key — the code comment even acknowledges this
("`_persist_generated_plan` does not receive [it]; left None when unavailable").
The correct, server-injected `ftp_confidence` value *is* available in
`dispatch_tool`'s local `inputs` dict at the `_persist_generated_plan` call site
(`backend/agent/tools.py:762-763`), so this is a straightforward plumbing gap, not
an inherent limitation — every row ever written to `plans.ftp_confidence` is `NULL`.

**Fix:** Pass `inputs["ftp_confidence"]` (or `ftp_confidence` directly) into
`_persist_generated_plan`, e.g.
`await _persist_generated_plan(user_id, result.value, ftp_confidence=inputs["ftp_confidence"])`.

### WR-03: `write_audit_entry`'s docstring contradicts its actual (safe) usage

**File:** `backend/agent/audit.py:34-36`, `backend/agent/tools.py:630,654,678(approx),770,792`

**Issue:** The docstring states "Callers should fire this without awaiting its
outcome for correctness (it always 'succeeds' from the caller's view)," but every
call site in `dispatch_tool` does `await write_audit_entry(...)` synchronously in
the request path. This is currently harmless (the function's internal
`try/except: pass` means awaiting it never raises or blocks on error), but the
docstring describes a fire-and-forget (`asyncio.create_task`) usage pattern that
does not match the code. A future maintainer following the docstring's semantics
rather than the working implementation risks introducing an actual fire-and-forget
call that could reorder audit writes relative to the tool_result response.

**Fix:** Update the docstring to describe the actual (awaited, never-raising)
contract, or change the call sites to genuinely fire-and-forget if that was the
intent.

### WR-04: Numeric-token tolerance attribution can be fooled by date/timestamp components in tool result values

**File:** `backend/agent/trust.py:99-123` (`_NUMERIC_TOKEN`, `_is_attributed`)

**Issue:** `_NUMERIC_TOKEN` extracts any boundary-aware standalone digit run, which
includes date/time components embedded in a tool result's `inputs` or `value` dict
(e.g. an ISO date string such as `"2026-07-04"` yields standalone tokens `2026`,
`7`, `4`). A small hallucinated physiological number that coincidentally matches one
of these components (e.g. an unsourced "CTL is 4" or "TSS 7") would be falsely
attributed as sourced, because `_is_attributed` only compares numeric value, not
semantic origin. The existing regression test
(`test_timestamp_digit_run_does_not_attribute`) only demonstrates one timestamp
string that happens not to produce a colliding token (`42` truly does not appear
standalone in `2024-01-01T00:04:20Z`); it does not cover the general case of
short date components (day/month values 1-31, single-digit hours/minutes) that
routinely appear standalone once split on non-digit boundaries.

**Fix:** Either exclude tokens sourced from known non-physiological JSON keys
(e.g. skip any key ending in `_at`, `date`, `timestamp` when building
`tool_result_values`), or scope `_is_attributed` to numeric *values* extracted via a
JSON parse of each tool_result string rather than raw regex token extraction over
the whole string, which would eliminate the date-substring class of collision
entirely.

---

_Reviewed: 2026-07-04T00:00:00Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
