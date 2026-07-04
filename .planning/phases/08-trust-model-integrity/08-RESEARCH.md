# Phase 8: Trust Model Integrity - Research

**Researched:** 2026-07-04
**Domain:** Backend trust-model hardening (Python/FastAPI agent layer + sports-science tool library + Supabase persistence)
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Mode:** `--auto` — no interactive questions were asked. Every decision below is the recommended option, auto-selected and logged for audit.

- **D-01 (auto):** New `audit_log` Postgres table, written per tool dispatch inside `dispatch_tool` (same call sites that already do `audit_log.append(...)` in `backend/agent/tools.py:586,601,629,642`), following the exact async-Supabase-service-role pattern already proven in `backend/sports_science/capability_gap.py::log_capability_gap` (cached singleton client, best-effort insert, never blocks the tool result on write failure).
- **D-02 (auto):** Split enforcement by input provenance, mirroring the already-validated `user_id` server-side-injection fix (commit `b3fcf39`, 260702-wev): values that come from a prior trusted tool result (`current_ctl` from `update_pmc`, `ftp_watts`/`ftp_confidence` from `estimate_ftp_from_rides`, `load_targets` from `progress_load`) are injected server-side in `dispatch_tool` from the last verified DB/tool-result value, never taken from the LLM's tool-call arguments at all. Values the LLM must legitimately transcribe from the conversation (`max_hr_or_lthr`) are validated against a session-scoped "confirmed values" registry populated only from actual tool results and the onboarding profile.
- **D-03 (locked by ROADMAP goal, not a gray area):** Replace the substring check in `scan_buffer` with numeric-parse + tolerance (e.g. exact float compare within ~0.01) plus a word/token boundary requirement, so "250" can no longer match inside "2500" or a timestamp.
- **D-04 (auto):** Seed `tool_result_values` at the start of each turn by reloading prior tool-result content from a persisted source for the current `conversation_id`, not an in-memory/process cache (Phase 7 established this backend runs as stateless Vercel serverless functions).
- **D-05 (auto):** Add a direct onboarding question ("Do you know your lactate threshold heart rate, or your resting/max HR?") with three explicit outcomes stored on the profile: (1) user gives LTHR directly -> used as-is; (2) user gives max HR only -> LTHR estimated via a documented %-of-max-HR heuristic; (3) user knows neither -> explicit `hr_zones_available: false` stored on the profile; `calculate_hr_zones` and `generate_plan`'s HR-based targets are skipped entirely, falling back to the RPE-only cold-start path (Phase 3 D-07 in `03-CONTEXT.md`).
- **D-06 (auto):** Correct `HR_ZONE_BOUNDARIES` in `constants.py` to true Coggan/Allen boundaries (~68/83/94/105% of LTHR) rather than the current Friel-style values, and keep the methodology string as "Coggan/Allen" (now honestly true instead of falsely claimed). This also resolves Zone 2 beginner-safety (real Coggan Zone 2 ~69-83% LTHR is materially gentler than the current mislabeled 81-90%).
- **D-07 (auto):** Add `preferred_days` as a real parameter sourced from the user's profile, replacing the hardcoded `_DEFAULT_DAYS[:n_sessions]` slice in `_build_sessions`. Wire `current_ctl` and `load_targets["recommended_ctl_target"]` into an actual per-week progression decision: when `current_ctl` is far below the recommended target (true beginner, low base fitness), keep week-over-week volume flat/conservative rather than the current fixed 4-week template; combine with `back_status == "moderate"` to cap Week 1 duration further when both signals indicate an at-risk beginner.

### Claude's Discretion

Exact numeric tolerance for D-03's float comparison, exact %-of-max-HR formula for D-05's LTHR estimate, and the precise progression-multiplier curve for D-07 are left to planning/research — the direction is locked, the constants are not. (This research proposes concrete values for all three below; the planner should confirm or adjust them, not treat them as re-opened for exploration.)

### Deferred Ideas (OUT OF SCOPE)

- **CP model quality-filter bug** (`ftp.py:46` — `best_ftp_estimate` always `None`, dead code; fed whole-ride duration/avg-power instead of mean-max efforts; FTP=CP with no 0.95 discount, unsafe overestimate direction) — not acted on here; flag for roadmap backlog.
- **ZWO fixed-0.65-FTP bug** (`zwo.py:22-26,97` — recovery sessions export as a 65% steady-state ride regardless of session type/power_targets) — flag for backlog.
- **NaN propagation in metrics**, and the review doc's "misc" bullet list (zone input validation, 0.56/0.55 boundary duplication, week-4 duration overflow, `weekly_hours=0` still scheduling sessions, `load.py` mild/moderate distinction erased, `zwo.py` None-duration TypeError) — flagged for backlog, not this phase.
- None of the above block Phase 8's stated goal.
</user_constraints>

## Summary

All seven defects in `08-CONTEXT.md` were re-confirmed by direct source read during this research pass, and the exact code seams for each fix were located. Two findings materially refine the CONTEXT.md decisions and must reach the planner:

1. **D-04's stated source (`messages` table) does not exist as a reload target.** `save_messages` (`backend/routes/onboarding.py:149-174`) is only ever called with plain `{role: "user"|"assistant", content: str}` pairs — the tool-result content blocks that `run_turn` builds internally (`backend/agent/loop.py:232`) are never passed to it. The `messages.role` CHECK constraint allows `'tool'`, but nothing ever writes that role. D-01's new `audit_log` table (scoped by `user_id` + `conversation_id` + `created_at`) is the only real candidate for D-04's cross-turn reload, and it is a strictly better source than the messages table would have been (it stores the actual `result` JSON, not a reconstructed content block). This means **D-01 and D-04 are one combined implementation**, not two independent ones.
2. **Neither `run_turn` nor `sse_generator` nor `dispatch_tool` currently receives `conversation_id`** — only `user_id` was threaded through in the 260702-wev fix. D-01 (schema needs `conversation_id`) and D-04 (reload must be scoped to one conversation) both require this threading, following the exact pattern 260702-wev already established for `user_id`.

Everything else confirms CONTEXT.md's decisions with no material changes. `preferred_days`, `lthr_estimate`/`lthr`, and `back_status` already exist as `profiles` columns (migration `0002_phase3_schema.sql`) — D-05 and D-07 are wiring gaps, not schema gaps, except for a new `hr_zones_available` boolean D-05 needs. `profiles.ftp` and `pmc_history.ctl/atl` already exist and are queried today by `backend/routes/adaptations.py:550-558` using the exact pattern D-02's server-side injection should reuse.

**Primary recommendation:** Implement D-01+D-04 as a single `audit_log` table + reload mechanism (thread `conversation_id` alongside the existing `user_id` injection chain); implement D-02+D-07 as one expanded server-side-injection block in `dispatch_tool` for the `generate_plan` tool (current_ctl, ftp_watts, ftp_confidence, load_targets, preferred_days all become server-sourced, never LLM-trusted); fix D-03's substring bug with numeric-token extraction + tolerance compare; fix D-06's constants against the verified Coggan/Allen source (68/83/94/105% of LTHR — precise values confirmed below); add the LTHR onboarding question (D-05) reusing the existing `hr_zones_available`-style gate pattern already established for FTP confidence gating.

<phase_requirements>
## Phase Requirements

No requirement IDs were formally assigned to this phase in `REQUIREMENTS.md` at research time — `08-CONTEXT.md` names it as a re-verification/hardening pass over requirements originally completed in Phase 2, plus net-new sub-scope (LTHR collection, HR-zone correction, generate_plan wiring). This research proposes the following ID scheme; the planner should assign final numbers and update `REQUIREMENTS.md`'s traceability table accordingly.

| ID | Description | Research Support |
|----|-------------|-------------------|
| TRUST-03 (existing, re-verify) | Every assistant response is parsed before display; unsourced physiological number triggers retry + capability-gap log | D-03's numeric-token/tolerance rewrite (Code Examples, Pattern 3) hardens this under real conversation load |
| TRUST-04 (existing, re-verify) | Every physiological number traceable to a tool-library call, verifiable in application logs | D-01's `audit_log` table (Architecture Patterns Pattern 1, Migration Reference) makes "verifiable in logs" literally true for the first time |
| TRUST-05 (existing, re-verify) | Agent calls `log_capability_gap` and falls back to qualitative reasoning when a method is missing | Unaffected by this phase's changes; `handle_violation`'s call to `log_capability_gap` is untouched by D-03's rewrite (only the attribution check changes, not the violation-handling hook) |
| TOOL-02 (existing, amend) | `calculate_hr_zones(max_hr_or_lthr)` returns HR zones with boundary values and methodology string | D-06 corrects the boundary constants so the existing "Coggan/Allen" methodology claim becomes true (Code Examples, State of the Art) |
| PLAN-06 (existing, re-verify) | Every physiological number in a generated plan traceable to a tool-library call | D-07's wiring of `current_ctl`/`load_targets`/`preferred_days` closes the gap where `generate_plan` accepted-but-ignored inputs whose caps were promised but never enforced |
| TRUST-06 (proposed, new) | `audit_log` table persisted per tool dispatch, queryable by user_id + conversation_id | D-01 (Architecture Patterns Pattern 1, Migration Reference) |
| TRUST-07 (proposed, new) | `generate_plan`'s trust-sensitive inputs (current_ctl, ftp_watts, ftp_confidence, load_targets, preferred_days) are server-injected, never trusted from LLM tool-call arguments | D-02 + D-07 combined (Architecture Patterns Pattern 2) |
| TRUST-08 (proposed, new) | Bare-number attribution uses word-boundary + numeric-tolerance matching instead of substring | D-03 (Code Examples, Pitfall 3) |
| TRUST-09 (proposed, new) | `tool_result_values` seeded from a persisted audit trail at the start of every turn, eliminating cross-turn false positives on a stateless serverless backend | D-04 (Architecture Patterns diagram, Pitfall 1 and 2) |
| ONBD-05 (proposed, new) | Onboarding collects LTHR, or a max-HR-derived estimate, or an explicit `hr_zones_available: false` with RPE-only fallback | D-05 (Migration Reference, Assumptions Log A2) |
| PLAN-07 (proposed, new) | `generate_plan` consumes `current_ctl`/`load_targets` for CTL-gap-aware progression and `preferred_days` for real scheduling, so back-protective caps actually constrain sessions | D-07 (Code Examples, Assumptions Log A3) |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Audit log persistence (D-01) | API/Backend (agent layer: `dispatch_tool`) | Database (new `audit_log` table) | Write happens at the tool-dispatch choke point; storage is Postgres |
| Tool input provenance / server-side injection (D-02, D-07) | API/Backend (`dispatch_tool`) | Database (`profiles`, `pmc_history` lookups) | Same choke point already used for the `user_id` injection precedent |
| Attribution matching rewrite (D-03) | API/Backend (`agent/trust.py`, pure function) | — | No I/O; pure regex/parse logic |
| Cross-turn seeding (D-04) | API/Backend (`agent/loop.py` turn setup) | Database (reads new `audit_log` table) | Must run before the first `scan_buffer` call each turn |
| LTHR onboarding collection (D-05) | API/Backend (`routes/onboarding.py` system prompt + `save_profile`) | Database (`profiles.lthr`, new `hr_zones_available` column) | Interview flow lives in the system-prompt string, not a state machine |
| HR zone constants correction (D-06) | API/Backend (`sports_science/constants.py`, `zones.py`) | — | Pure constants table, zero I/O (TRUST-01 invariant) |
| generate_plan wiring (D-07) | API/Backend (`sports_science/plan.py`) | API/Backend (`dispatch_tool` for the injected inputs) | Pure computation tool; the values it receives are fixed upstream by D-02 |

## Package Legitimacy Audit

**No new external packages are introduced by this phase.** All seven fixes use libraries already present and verified in the codebase (`supabase` 2.31.0, `anthropic` 0.67.0, Python stdlib `re`/`json`/`hashlib`). Package Legitimacy Gate is not applicable — skip.

## Standard Stack

### Core (already in use, no version changes needed)

| Library | Version (verified installed) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `supabase` (async client, `acreate_client`/`AsyncClient`) | 2.31.0 `[VERIFIED: pip show supabase in project .venv]` | Postgres access for new `audit_log` table + reads of `profiles`/`pmc_history` | Already the sole DB access layer project-wide; `backend/db.py::get_async_supabase()` is the centralized (WR-003) singleton |
| `anthropic` | 0.67.0 `[VERIFIED: pip show anthropic in project .venv]` | Tool schemas / streaming | No schema-shape changes needed for any D-01..D-07 fix except widening `generate_plan`'s description (still same param count once server-injected params are stripped from the LLM-facing schema) |
| Python stdlib `re` | 3.12 | D-03's rewritten attribution matching | No third-party regex/NLP library needed; a hand-rolled tokenizer + `float()` compare is simpler and more auditable than pulling in a parsing library for this narrow case |

### Supporting

| Library | Purpose | When to Use |
|---------|---------|-------------|
| `backend.db.get_async_supabase()` (existing centralized singleton, `backend/db.py`) | New `audit_log` writer, `profiles`/`pmc_history` lookups for D-02 | Use this — not a fourth duplicated singleton — since `backend/agent/tools.py` already imports it (`from backend.db import get_async_supabase as _get_async_supabase`) for `_persist_generated_plan` |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `backend.db.get_async_supabase()` for the new audit writer | Duplicate the `capability_gap.py`-style local module-level singleton (as D-01's CONTEXT.md literally says "mirror capability_gap.py") | CONTEXT.md's literal wording asks for the `capability_gap.py` pattern (best-effort insert, never blocks). That *behavioral* pattern should be kept, but the *client-acquisition* pattern should use the already-centralized `backend.db` singleton instead of adding a fourth duplicate `_supabase_client` module global — `capability_gap.py` and `profile.py`'s duplication predates WR-003's consolidation and is legacy, not a pattern to keep multiplying. Flag this as a discretionary refinement for the planner. |
| Word-boundary + tolerance regex for D-03 | A dedicated NLP/number-extraction library (e.g. `word2number`, `text2num`) | Overkill — the task is "is this JSON-embedded number the same value as this prose number," not natural-language number parsing. Hand-rolled `re.finditer(r'(?<![\d.])-?\d+(?:\.\d+)?(?!\d)')` + float compare is simpler, dependency-free, and auditable inline (Don't Hand-Roll section below has the exception rationale). |

**Installation:** None — no new packages.

## Architecture Patterns

### System Architecture Diagram

```
                     ┌─────────────────────────────────────────┐
                     │  routes/chat.py, routes/onboarding.py    │
                     │  (has user_id + conversation_id in scope)│
                     └───────────────┬───────────────────────────┘
                                     │ sse_generator(..., user_id, conversation_id)  <-- NEW: thread conversation_id
                                     v
                     ┌─────────────────────────────────────────┐
                     │  routes/_sse.py :: sse_generator          │
                     └───────────────┬───────────────────────────┘
                                     │ run_turn(..., user_id, conversation_id)        <-- NEW
                                     v
        ┌────────────────────────────────────────────────────────────────┐
        │  agent/loop.py :: run_turn                                     │
        │                                                                │
        │  [NEW D-04] before first scan_buffer call this turn:           │
        │    tool_result_values = await load_prior_audit_values(         │
        │        conversation_id)   <-- reads NEW audit_log table        │
        │                                                                │
        │  while retries <= MAX_RETRIES:                                 │
        │    stream Claude -> buffer text -> scan_buffer(text, values)   │
        │    if stop_reason == "tool_use":                                │
        │       dispatch_tool(block, audit_log, user_id, conversation_id) │
        └───────────────┬────────────────────────────────────────────────┘
                        │ per tool_use block
                        v
        ┌────────────────────────────────────────────────────────────────┐
        │  agent/tools.py :: dispatch_tool                                │
        │                                                                │
        │  [existing] user_id injection allowlist: save_profile,          │
        │             generate_plan                                       │
        │                                                                │
        │  [NEW D-02+D-07] generate_plan-only interception BEFORE fn():  │
        │    current_ctl      <- pmc_history latest row (DB query)       │
        │    ftp_watts,                                                   │
        │    ftp_confidence   <- this-turn audit_log's                    │
        │                         estimate_ftp_from_rides result           │
        │                         (fallback: insufficient_data/None)      │
        │    load_targets     <- this-turn audit_log's progress_load      │
        │                         result (D-08 guarantees same-turn order)│
        │    preferred_days   <- profiles.preferred_days (DB query)       │
        │    (any LLM-supplied values for these 5 keys are discarded)     │
        │                                                                │
        │  [NEW D-01] after fn() succeeds or fails:                       │
        │    write one row to audit_log (best-effort, never blocks)       │
        │    columns: user_id, conversation_id, tool_use_id, tool_name,   │
        │             inputs, result, is_error, created_at                │
        └───────────────┬────────────────────────────────────────────────┘
                        │ ToolResult
                        v
        ┌────────────────────────────────────────────────────────────────┐
        │  sports_science/*.py (pure, zero DB/Anthropic imports, TRUST-01)│
        │    zones.py [D-06 constants fix]                                │
        │    plan.py  [D-07 CTL-gap-aware progression + preferred_days]   │
        └────────────────────────────────────────────────────────────────┘

        ┌────────────────────────────────────────────────────────────────┐
        │  agent/trust.py :: scan_buffer  [D-03 rewrite]                  │
        │    OLD: `bare_number in val`           (substring — buggy)      │
        │    NEW: extract all numeric tokens from val via                │
        │         re.finditer(r'(?<![\d.])-?\d+(?:\.\d+)?(?!\d)', val),   │
        │         then abs(candidate - token) <= TOLERANCE compare        │
        └────────────────────────────────────────────────────────────────┘
```

### Recommended Project Structure (files touched, no new top-level dirs)

```
backend/
├── agent/
│   ├── audit.py          # NEW: write_audit_entry(), load_prior_audit_values() -- both use backend.db
│   ├── tools.py           # dispatch_tool: D-01 write call + D-02/D-07 injection block
│   ├── trust.py            # D-03: numeric-token/tolerance rewrite of scan_buffer's attribution check
│   └── loop.py              # D-04: seed tool_result_values from load_prior_audit_values() before the while-loop
├── routes/
│   ├── _sse.py               # thread conversation_id through to run_turn
│   ├── chat.py                 # pass conversation_id=conversation_id
│   └── onboarding.py             # pass conversation_id=conversation_id; add LTHR question to ONBOARDING_SYSTEM_PROMPT
└── sports_science/
    ├── constants.py                 # D-06: corrected HR_ZONE_BOUNDARIES
    ├── zones.py                       # no logic change; boundaries flow from constants.py
    ├── profile.py                       # add hr_zones_available param/column to save_profile
    └── plan.py                            # D-07: preferred_days param, CTL-gap-aware progression
supabase/migrations/
└── 0009_audit_log_and_hr_zones_flag.sql   # NEW: audit_log table + profiles.hr_zones_available column
tests/
├── agent/test_audit.py         # NEW (Wave 0 gap)
├── agent/test_trust.py          # extend for D-03 tolerance/boundary cases
├── agent/test_loop.py             # extend for D-04 seeding
├── agent/test_tools_phase3.py       # extend for D-02/D-07 injection
└── sports_science/
    ├── test_zones.py                    # update HR boundary assertions for D-06
    └── test_plan.py                       # NEW (Wave 0 gap) -- generate_plan currently only tested inline in test_tools_phase3.py
```

### Pattern 1: Best-effort DB write that never blocks the caller (D-01)
**What:** Wrap the Supabase insert in `try/except: pass`, matching `capability_gap.py`'s proven pattern, but acquire the client via the centralized `backend.db.get_async_supabase()` instead of a new duplicate singleton.
**When to use:** Any audit/telemetry write that must not break the user-facing tool-call flow.
**Example:**
```python
# backend/agent/audit.py (new)
# Source: mirrors backend/sports_science/capability_gap.py's proven
# best-effort-insert shape; client acquisition uses the already-centralized
# backend.db.get_async_supabase() (WR-003) instead of a 4th duplicate singleton.
from backend.db import get_async_supabase

async def write_audit_entry(
    user_id: str | None,
    conversation_id: str | None,
    tool_use_id: str,
    tool_name: str,
    inputs: dict,
    result: dict | None,
    is_error: bool,
) -> None:
    try:
        supabase = await get_async_supabase()
        await supabase.table("audit_log").insert({
            "user_id": user_id,
            "conversation_id": conversation_id,
            "tool_use_id": tool_use_id,
            "tool_name": tool_name,
            "inputs": inputs,
            "result": result,
            "is_error": is_error,
        }).execute()
    except Exception:
        pass  # D-14: audit logging is best-effort; never blocks the tool result
```

### Pattern 2: Server-side value injection for a trust-sensitive tool (D-02, D-07 — extends the 260702-wev precedent)
**What:** `dispatch_tool` already has an allowlist (`{"save_profile", "generate_plan"}`) where it strips any LLM-supplied `user_id` and injects the server-verified one. D-02/D-07 extend the SAME choke point for `generate_plan` only, for five more keys.
**When to use:** Any tool parameter that represents a fact the server already knows authoritatively and the LLM should never be trusted to transcribe correctly.
**Example:**
```python
# backend/agent/tools.py -- dispatch_tool, extending the existing
# "if name in {'save_profile', 'generate_plan'}" block (line 577)
if name == "generate_plan":
    # D-02: current_ctl from the latest pmc_history row -- same query
    # shape as backend/routes/adaptations.py:550-558.
    pmc_resp = await supabase.table("pmc_history").select("ctl").eq(
        "user_id", user_id
    ).order("date", desc=True).limit(1).execute()
    current_ctl = float((pmc_resp.data or [{}])[0].get("ctl") or 0.0)

    # D-02: ftp_watts/ftp_confidence and load_targets come from THIS TURN's
    # audit_log (in-memory list already threaded into dispatch_tool) -- D-08's
    # tool order guarantees estimate_ftp_from_rides and progress_load already
    # ran earlier in this same turn when applicable.
    ftp_entry = _last_audit_result(audit_log, "estimate_ftp_from_rides")
    load_entry = _last_audit_result(audit_log, "progress_load")

    # D-07: preferred_days from the profile (already collected in onboarding).
    profile_resp = await supabase.table("profiles").select(
        "preferred_days"
    ).eq("user_id", user_id).execute()
    preferred_days = (profile_resp.data or [{}])[0].get("preferred_days") or []

    inputs = {
        **inputs,
        "current_ctl": current_ctl,
        "ftp_watts": (ftp_entry or {}).get("value", {}).get("ftp_watts"),
        "ftp_confidence": (ftp_entry or {}).get("value", {}).get("confidence", "insufficient_data"),
        "load_targets": (load_entry or {}).get("value", {"recommended_ctl_target": current_ctl}),
        "preferred_days": preferred_days,
    }
```

### Pattern 3: Numeric-token extraction with tolerance (D-03)
**What:** Replace `s in val` substring checks with tokenized numeric extraction + float tolerance compare.
**When to use:** Any "is this number present in this JSON blob" check where the JSON blob is a serialized dict of floats/ints (not free text).
**Example:**
```python
# backend/agent/trust.py -- replaces the `any(s in val for ...)` checks
import re

_NUMERIC_TOKEN = re.compile(r"(?<![\d.])-?\d+(?:\.\d+)?(?!\d)")
NUMERIC_TOLERANCE = 0.01

def _is_attributed(candidate_str: str, tool_result_values: list[str]) -> bool:
    try:
        candidate = float(candidate_str)
    except ValueError:
        return False
    for val in tool_result_values:
        for token_match in _NUMERIC_TOKEN.finditer(val):
            try:
                if abs(candidate - float(token_match.group(0))) <= NUMERIC_TOLERANCE:
                    return True
            except ValueError:
                continue
    return False
```
Note the negative lookbehind `(?<![\d.])` and lookahead `(?!\d)` are what prevent "25" from matching inside "2500" or "0.250" — this is the core fix for the substring bug described in `08-CONTEXT.md` line 13 and the review doc.

### Anti-Patterns to Avoid
- **Reusing `messages` table for D-04 as CONTEXT.md's literal text suggests:** the table never receives tool_result content today (`save_messages` only ever gets `{role: user|assistant, content: str}`). Attempting D-04 against `messages` would require either (a) a new persistence write path with no current callers, duplicating work D-01 already does, or (b) silently reading an empty result set and falsely believing seeding works. Use the new `audit_log` table instead — one persistence mechanism serves both D-01 and D-04.
- **Adding a 4th duplicated Supabase singleton:** `capability_gap.py` and `profile.py` each have their own module-level `_supabase_client`. Do not add a 5th (or 4th, depending on count) copy for the new `audit_log` writer — use `backend.db.get_async_supabase()`, which `agent/tools.py` already imports.
- **Trusting the LLM's `generate_plan` inputs for anything server-derivable:** the whole point of D-02/D-07 is that `current_ctl`, `ftp_watts`, `ftp_confidence`, `load_targets`, and `preferred_days` must never flow from `tool_use_block.input` into the actual function call.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Numeric string parsing/tolerance compare | A general-purpose text-to-number NLP parser | `re.finditer` + `float()` (Pattern 3 above) | The domain is narrow (compare two decimal numbers embedded in JSON-like text); a full NLP number parser is unnecessary complexity and adds a dependency with its own false-positive/negative surface |
| Supabase client pooling | A new per-module singleton (the `capability_gap.py`/`profile.py` pattern) | `backend.db.get_async_supabase()` | WR-003 already consolidated 6 duplicated singletons into one; adding another regresses that work |
| LTHR-from-max-HR estimation | A custom regression/lookup table | Documented %-of-max-HR heuristic (85-90%, cite methodology string) — same `ToolResult` shape as every other tool | Consistency with TOOL-09 (methodology-tagged results); a bespoke formula with no citation would violate the "no invented numbers" trust model this exact phase is hardening |

**Key insight:** Every fix in this phase is a *wiring* or *constants* correction inside an already-correct architecture (TRUST-01/02 boundaries, `ToolResult` shape, best-effort-write pattern) — there is no new subsystem to design, only existing seams to extend consistently.

## Common Pitfalls

### Pitfall 1: D-04's stated reload source doesn't exist
**What goes wrong:** Implementing D-04 exactly as CONTEXT.md's prose describes ("reload prior tool-result content blocks from the persisted `messages` table") silently does nothing, because no code path ever writes `role='tool'` (or any tool_result JSON) to `messages`.
**Why it happens:** CONTEXT.md's decision was written from the ROADMAP/review doc's framing before this research pass traced `save_messages`'s actual call sites.
**How to avoid:** Source D-04's reload from the new `audit_log` table (D-01) instead — implement D-01 first (or as the same task) and D-04 as a read against it, scoped by `conversation_id` and ordered by `created_at`.
**Warning signs:** A "GREEN" D-04 test that only proves the reload function returns `[]` for every conversation (because the source table is always empty).

### Pitfall 2: `conversation_id` is not currently threaded to `dispatch_tool`
**What goes wrong:** D-01's audit rows and D-04's reload both need `conversation_id` scoping, but `run_turn`/`sse_generator`/`dispatch_tool` signatures don't carry it today — only `user_id` was added in 260702-wev.
**Why it happens:** 260702-wev solved the identity-injection bug in isolation; conversation-scoping was out of scope for that fix.
**How to avoid:** Thread `conversation_id` through the identical chain `user_id` already uses (`chat.py`/`onboarding.py` -> `sse_generator` -> `run_turn` -> `dispatch_tool`), as a new explicit kwarg, not inferred from anywhere else.
**Warning signs:** `audit_log.conversation_id` column always NULL in a live test.

### Pitfall 3: Tolerance compare on a wide float range creates new false positives
**What goes wrong:** A single global `NUMERIC_TOLERANCE = 0.01` works for exact float attribution but is meaningless for values that get `round()`-ed at different points (e.g. `zones.py`'s `round(z["lower"] * ftp)` rounds to an int, but the LLM might say "180.0"). If tolerance is too loose (e.g. 1.0) it re-introduces the "250 matches 2500" class of bug at a different granularity; too tight (e.g. 1e-9) breaks legitimate float/int mismatches (180 vs 180.0).
**Why it happens:** Watts/BPM/TSS values are rounded ints in tool output but the LLM may echo them as floats or vice versa.
**How to avoid:** Use a tolerance of `0.01` for exact-decimal domains (TSS/IF/CTL/ATL, which carry one decimal place per `plan.py`'s `round(..., 1)`) but confirm during planning whether integer-rounded fields (watts, bpm) need `abs(candidate - token) < 1` instead. Recommend testing both boundary cases explicitly.
**Warning signs:** A previously-passing corpus test (`test_trust_corpus.py`) starts failing after the D-03 rewrite — this is the regression signal the existing "zero false positive / zero false negative" tests (`test_false_positive_rate_is_zero`, `test_false_negative_rate_is_zero`) are designed to catch. Run that corpus first against the new implementation before considering D-03 done.

### Pitfall 4: `ftp_confidence`/`load_targets` are not durably stored anywhere — same-turn dependency is load-bearing
**What goes wrong:** Unlike `current_ctl` (durable in `pmc_history`) and `preferred_days` (durable in `profiles`), there is no table that stores "current FTP confidence" or "current load targets" outside of a specific tool call's return value. If `generate_plan` is ever invoked in a turn where `estimate_ftp_from_rides`/`progress_load` did NOT run earlier in that same turn (e.g. a future conversational flow that violates D-08's stated order), the server-side injection has nothing to fall back to except a safe default.
**Why it happens:** These two tool outputs were designed to be ephemeral/pure — `estimate_ftp_from_rides` recomputes from ride history every call rather than persisting a "current confidence" row.
**How to avoid:** When no same-turn audit_log entry exists for `estimate_ftp_from_rides`/`progress_load`, fall back to `ftp_confidence="insufficient_data"`, `ftp_watts=None`, `load_targets={"recommended_ctl_target": current_ctl}` — the same cold-start-safe defaults `generate_plan`/`plan.py` already treat as the conservative case. Never fall back to trusting the LLM's supplied values for these keys.
**Warning signs:** A `generate_plan` call outside the D-08-mandated order silently uses stale or LLM-fabricated FTP data.

### Pitfall 5: HR zone boundary source disagreement in adjacent web sources
**What goes wrong:** Some secondary sources round Coggan Zone 4's lower bound to 91% or 95% inconsistently (a scraped search snippet during this research showed both "91-105%" and "95-105%" for the same zone from different aggregator sites).
**Why it happens:** Aggregator/calculator sites often round or transcribe the original Coggan/Allen table inconsistently; TrainingPeaks and Coggan's own book are the canonical source, not third-party calculator sites.
**How to avoid:** Use the values cross-checked against the more authoritative-looking source in this research (69-83%, 84-94%, 95-105%, 106%+, with Zone 1 "up to 68%") and treat CONTEXT.md's own stated "~68/83/94/105%" as the locked target — this research confirms that framing is directionally correct; convert to continuous decimal boundaries (below) rather than the human-rounded ranges, matching this codebase's existing `POWER_ZONE_BOUNDARIES` convention of contiguous zones (each zone's `upper` equals the next zone's `lower`).
**Warning signs:** A new HR zone boundary test asserts a boundary value (e.g. 0.95) that doesn't match the continuous-boundary convention already used by `POWER_ZONE_BOUNDARIES` (0.55, 0.75, 0.90...).

## Code Examples

### D-06: Corrected `HR_ZONE_BOUNDARIES` (constants.py)
```python
# Source: Coggan/Allen HR zone percentages of LTHR, cross-checked via
# web search against multiple Coggan-attributed sources during this research
# session (see Sources section) [CITED]. Converted from the human-rounded
# ranges ("up to 68%", "69-83%", "84-94%", "95-105%", "106%+") to continuous
# decimal boundaries matching this file's existing POWER_ZONE_BOUNDARIES
# convention (each zone's upper == next zone's lower).
HR_ZONE_BOUNDARIES = [
    {"zone": 1, "name": "Active Recovery", "lower": 0.00, "upper": 0.68},
    {"zone": 2, "name": "Endurance",       "lower": 0.68, "upper": 0.83},
    {"zone": 3, "name": "Tempo",           "lower": 0.83, "upper": 0.94},
    {"zone": 4, "name": "Threshold",       "lower": 0.94, "upper": 1.05},
    {"zone": 5, "name": "VO2max",          "lower": 1.05, "upper": None},
]
```
This is a pure constants-table edit; `zones.py::calculate_hr_zones` needs no code change, only `constants.py` and the tests asserting the old (81/90/94/100) boundaries in `tests/sports_science/test_zones.py` (currently no HR-boundary-overlap parametrized test exists — only the power-zone one at line 40 — this is a Wave 0 gap; add the HR equivalent).

### D-07: CTL-gap-aware progression (concrete, testable algorithm proposal — Claude's Discretion per CONTEXT.md, confirm exact thresholds during planning)
```python
# backend/sports_science/plan.py -- proposed addition to _build_sessions
def _is_true_beginner_ramp(current_ctl: float, load_targets: dict) -> bool:
    """
    True when current CTL is far below the recommended target -- i.e. a
    genuine low-base-fitness beginner, not just someone slightly under target.
    Cold start (current_ctl == 0, the common case for a brand-new user with
    no ride history) always qualifies.
    """
    target = load_targets.get("recommended_ctl_target", current_ctl) or 0.0
    if target <= 0:
        return False
    gap_ratio = (target - current_ctl) / target
    return current_ctl <= 0 or gap_ratio >= 0.5


# In _build_sessions, when _is_true_beginner_ramp(...) is True:
#   - Week 2 and Week 3 duration use the SAME conservative cap as Week 1
#     (min(45, ...), or min(30, ...) if back_status == "moderate") instead
#     of the uncapped base_duration -- i.e. flat volume across weeks 1-3.
#   - When BOTH _is_true_beginner_ramp(...) AND back_status == "moderate":
#     tighten Week 1's cap further, e.g. min(20, ...) instead of 30 --
#     satisfies CONTEXT.md's "combine with back_status == moderate to cap
#     Week 1 duration further when both signals indicate an at-risk beginner."
#   - Week 4 recovery reduction (-40%) is unaffected either way.
```
This is directly unit-testable: `generate_plan(current_ctl=0.0, load_targets={"recommended_ctl_target": 20.0}, back_status="moderate", ...)` should assert Week 1/2/3 durations are all equal (flat) and capped below the current 30-minute back-moderate cap, versus `generate_plan(current_ctl=18.0, load_targets={"recommended_ctl_target": 20.0}, back_status="none", ...)` (gap_ratio=0.1, not a true-beginner-ramp case) preserving today's existing week1-conservative/week2-3-full behavior.

### D-02/D-07: `pmc_history` latest-CTL query pattern (already proven in this codebase)
```python
# Source: backend/routes/adaptations.py:550-558 (existing, working pattern)
pmc_resp = await (
    supabase.table("pmc_history")
    .select("ctl, atl")
    .eq("user_id", user_id)
    .order("date", desc=True)
    .execute()
)
pmc_rows = pmc_resp.data or []
current_ctl = float((pmc_rows[0].get("ctl") or 0) if pmc_rows else 0)
```

## Migration Reference

New migration `supabase/migrations/0009_audit_log_and_hr_zones_flag.sql`, following the idempotent style of `0005_phase6_persistence.sql`/`0006_pmc_unique_and_fits_bucket.sql` (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`):

```sql
-- audit_log: TRUST-04 durable, verifiable per-tool-call trail (D-01).
-- Written best-effort from dispatch_tool; never blocks the tool result on failure.
CREATE TABLE IF NOT EXISTS public.audit_log (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid,           -- nullable: some tool calls precede auth resolution
    conversation_id uuid,           -- nullable: not every dispatch_tool call site has one yet
    tool_use_id     text NOT NULL,
    tool_name       text NOT NULL,
    inputs          jsonb,
    result          jsonb,          -- ToolResult.model_dump(), or null on error
    is_error        boolean NOT NULL DEFAULT false,
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "audit_log: own row" ON public.audit_log
    USING (user_id = auth.uid());

-- Index for D-04's cross-turn reload (scoped by conversation, ordered by time).
CREATE INDEX IF NOT EXISTS audit_log_conversation_created_idx
    ON public.audit_log (conversation_id, created_at);

-- hr_zones_available: D-05's explicit "neither LTHR nor max HR known" flag.
-- When false, calculate_hr_zones/generate_plan's HR-based targets are skipped
-- entirely in favor of the existing cold-start RPE-only path (Phase 3 D-07).
ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS hr_zones_available boolean;
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Substring `in` check for number attribution | Numeric-token extraction + tolerance compare | This phase (D-03) | Eliminates "250 matches 2500/0.250/timestamp" false-negative-to-trust (i.e. false "attributed") class of bug |
| Per-request `audit_log: list = []` (never persisted) | Persisted `audit_log` Postgres table | This phase (D-01) | TRUST-04 becomes actually verifiable, not just constructed-and-discarded |
| `tool_result_values` reset per API round only within one HTTP request | Seeded from persisted audit trail at the start of every turn | This phase (D-04) | Removes cross-turn false positives inherent to stateless Vercel serverless functions (already established as the deploy target in Phase 7) |
| Friel-style HR zone boundaries mislabeled as Coggan/Allen | True Coggan/Allen boundaries (68/83/94/105% LTHR) | This phase (D-06) | Methodology string becomes honest; Zone 2 ceiling drops from 90% to 83% LTHR, safer for a deconditioned beginner with back issues |

**Deprecated/outdated:** None — this phase corrects implementation bugs and gaps in an already-current architecture; no library or pattern is being replaced with a newer alternative.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `NUMERIC_TOLERANCE = 0.01` is the right default for D-03's float compare | Code Examples / Pitfall 3 | If tool outputs use integer rounding (watts/bpm) rather than 1-decimal rounding (TSS/IF), 0.01 may be too tight for legitimate `180` vs `180.0` type mismatches; needs corpus-test verification during planning, not blind acceptance |
| A2 | 85-90% of max HR is an acceptable LTHR estimation fallback for D-05's "user knows max HR but not LTHR" branch | Don't Hand-Roll, Common Pitfalls | This is explicitly a rough heuristic per every source found (`[ASSUMED]`); coaches prefer an actual threshold test. Must be labeled low-confidence in the tool's methodology string and probably gated behind additional confirmation language in the onboarding prompt ("this is an estimate, not a measured value") |
| A3 | `gap_ratio >= 0.5` (current CTL less than half the recommended target) is the right "true beginner" threshold for D-07's flat-volume-ramp trigger | Code Examples (D-07 progression) | Untested threshold with no external citation — pure engineering judgment. If set too low, most legitimate users get the conservative flat ramp unnecessarily; if too high, at-risk beginners don't get it. This is explicitly "Claude's Discretion" per CONTEXT.md and needs a decision (not just acceptance) during planning, possibly with a quick sanity check against a few `(current_ctl, target_ctl)` example scenarios |
| A4 | An `audit_log` row per tool call (not batched per turn) is acceptable write volume | Architecture Patterns / Pattern 1 | CONTEXT.md's D-01 already locks per-call writes over batching (deliberately, for partial-turn survivability), so this is not a new assumption — restating for completeness. No action needed unless write volume becomes a real concern post-launch (unlikely at this project's scale) |

## Open Questions (RESOLVED)

1. **RESOLVED — Should `dispatch_tool`'s new `generate_plan` interception query the DB synchronously inline, or reuse the existing this-turn `audit_log` list for `current_ctl` too (instead of a fresh `pmc_history` query)?**
   - What we know: `current_ctl` is durable in `pmc_history` and queryable independent of same-turn tool calls (unlike `ftp_confidence`/`load_targets`, which only exist as ephemeral tool outputs).
   - What's unclear: Whether `update_pmc` is ever called in the same turn as `generate_plan` during onboarding (D-08's stated order for onboarding is `save_profile -> progress_load -> calculate_hr_zones -> generate_plan`, which does NOT include `update_pmc` — meaning for a first-time onboarding plan, `current_ctl` should come from the DB query, correctly returning 0 for a true cold start).
   - Resolution: Always query `pmc_history` directly for `current_ctl` (durable, correct for both cold-start onboarding and later coaching-chat re-plans); use this-turn `audit_log` only for `ftp_confidence`/`load_targets` (ephemeral, no durable store). Reflected in the Code Examples above and incorporated into Plan 08-06 (cited in that plan's key_links as "Open Question 1 resolution").

2. **RESOLVED — Does the `messages` table's `role` CHECK constraint (`'user'|'assistant'|'tool'`) need to actually gain a writer now, or can it stay unused?**
   - What we know: Nothing currently writes `role='tool'`; D-01/D-04 route around this by using the new `audit_log` table instead.
   - What's unclear: Whether any other in-flight or planned work (outside Phase 8's scope) depends on `messages.role='tool'` ever being populated.
   - Resolution: Leave `messages.role='tool'` unused for this phase — no plan adds a writer for it. If a future phase needs full conversational-turn tool-call replay (not just trust-attribution values), that's a separate concern from what TRUST-04/03 require here.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Local Supabase Postgres (via project's linked remote) | New `audit_log` table migration | Not verified locally in this session (no `supabase` CLI connectivity check run — out of scope for a research pass with no destructive DB actions) | — | Migration applies via the existing `supabase db push --linked --yes` pattern documented in STATE.md's "Migration applied via supabase db push --linked" decision entry |
| `pytest` + `pytest-asyncio` | All new/updated unit tests | ✓ | `asyncio_mode = auto` (pytest.ini) | — |
| Project `.venv` (supabase 2.31.0, anthropic 0.67.0) | Running the test suite locally | ✓ (confirmed via `pip show` in this session) | 2.31.0 / 0.67.0 | — |

**Missing dependencies with no fallback:** None — this phase requires no new external tool/service beyond what's already provisioned.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-asyncio (`asyncio_mode = auto`) |
| Config file | `pytest.ini` (repo root) |
| Quick run command | `.venv/bin/python -m pytest tests/agent/test_trust.py tests/agent/test_loop.py tests/agent/test_tools_phase3.py tests/sports_science/test_zones.py -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -q` |

**Baseline (confirmed by running the full suite in this research session, before any Phase 8 change):** `9 failed, 250 passed` — the 9 failures are pre-existing and unrelated (`tests/agent/test_sse.py` x8, `tests/sports_science/test_capability_gap.py::test_supabase_insert_called_with_correct_fields` x1; documented as the same baseline in the 260702-vsp/w52/wev quick-task summaries). The planner/verifier should treat this exact count as the pre-Phase-8 baseline — any NEW failures beyond these 9 identities are regressions from this phase's work.

### Phase Requirement -> Test Map (proposed IDs — see Phase Requirements section; planner assigns final numbers)

| Proposed ID | Behavior | Test Type | Automated Command | File Exists? |
|-------------|----------|-----------|-------------------|-------------|
| TRUST-06 | `audit_log` row written per tool dispatch, queryable by user_id+conversation_id | unit | `pytest tests/agent/test_audit.py -x` | ❌ Wave 0 |
| TRUST-07 | `generate_plan`'s current_ctl/ftp_watts/ftp_confidence/load_targets/preferred_days are server-injected, LLM-supplied values discarded | unit | `pytest tests/agent/test_tools_phase3.py -k generate_plan_injection -x` | ❌ Wave 0 (extend existing file) |
| TRUST-08 | `scan_buffer` uses numeric-token + tolerance matching, not substring; "250" no longer matches "2500"/"0.250" | unit | `pytest tests/agent/test_trust.py -x` | ✅ (extend) |
| TRUST-09 | `tool_result_values` seeded from persisted audit trail at start of turn; legit prior-turn number no longer flagged | unit | `pytest tests/agent/test_loop.py -k cross_turn_seed -x` | ❌ Wave 0 (extend existing file) |
| ONBD-05 | Onboarding collects LTHR, or max-HR-derived estimate, or explicit `hr_zones_available=false` with RPE-only fallback | unit + manual | `pytest tests/api/test_onboarding.py -x` | ✅ (extend) |
| (amends TOOL-02) | `HR_ZONE_BOUNDARIES` match true Coggan/Allen 68/83/94/105% and Zone 2 ceiling drops from 90% to 83% | unit | `pytest tests/sports_science/test_zones.py -x` | ✅ (extend) |
| PLAN-07 | `generate_plan` consumes `current_ctl`/`load_targets`/`preferred_days`; back-protective + CTL-gap caps actually constrain sessions | unit | `pytest tests/sports_science/test_plan.py -x` | ❌ Wave 0 (new file — currently only inline tests in `test_tools_phase3.py`) |

### Sampling Rate
- **Per task commit:** Quick run command above.
- **Per wave merge:** Full suite command.
- **Phase gate:** Full suite green (9 pre-existing failures only) before `/gsd-verify-work`.

### Wave 0 Gaps
- [ ] `tests/agent/test_audit.py` — covers TRUST-06 (new `audit_log` writer + reload function), mocking `backend.db.get_async_supabase` the same way `test_capability_gap.py` mocks `acreate_client`.
- [ ] `tests/sports_science/test_plan.py` — extract `generate_plan`'s inline tests out of `test_tools_phase3.py` into a dedicated file (matching the `test_zones.py`/`test_load.py` per-module convention already used everywhere else in `tests/sports_science/`), and add the D-07 CTL-gap-ramp + preferred_days cases.
- [ ] Extend `tests/agent/test_loop.py` with a cross-turn seeding test (TRUST-09) mocking the new `load_prior_audit_values` call.
- [ ] Extend `tests/agent/test_tools_phase3.py` with the `generate_plan` server-injection cases (TRUST-07), following the exact `test_user_id_injected_server_side_through_run_turn` mocking pattern in `tests/agent/test_loop.py:345` (patch `TOOL_REGISTRY["generate_plan"]` with a `MagicMock`, assert `call_args.kwargs` carries server-sourced values regardless of what the fake tool_use block supplied).
- [ ] Add an HR-zone boundary-overlap parametrized test to `tests/sports_science/test_zones.py`, mirroring the existing `test_zone_boundary_no_overlap` (power zones) at line 40 — no HR equivalent exists today.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-------------------|
| V1 Architecture | yes | Trust-boundary enforcement between LLM output and physiological data source (TRUST-01/02 invariant, this phase's core subject) |
| V4 Access Control | yes | `audit_log` RLS policy `user_id = auth.uid()` (mirrors every other user-owned table); server-side value injection prevents a compromised/malicious LLM turn from writing fabricated values through `generate_plan`/`save_profile` |
| V5 Input Validation | yes | D-03's numeric-token/tolerance rewrite is itself an input-validation control (validating that a number in model output actually matches a trusted source) |
| V6 Cryptography | no | No new crypto surface in this phase |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Prompt-injection laundering: LLM invents a physiological number, hands it into a tool call as an *input*, tool echoes it back, scanner treats it as "attributed" | Tampering | D-02/D-07: server-side injection of trust-sensitive tool inputs from verified DB/same-turn-audit sources; LLM-supplied values for these keys are always discarded, never merely validated |
| Trust-scanner bypass via substring collision (e.g. "25" hiding inside "2500", "0.250", or a timestamp digit run) | Tampering / Spoofing (of trust attribution) | D-03: numeric-token extraction with boundary lookaround + float tolerance compare, replacing the substring check |
| Cross-tenant audit-log read (a `conversation_id` belonging to another user is queried for cross-turn seeding) | Information Disclosure | `audit_log` RLS policy (`user_id = auth.uid()`) plus explicit `.eq("user_id", user_id)` app-layer re-enforcement in the reload query, matching the existing defence-in-depth pattern already used in `onboarding.py::load_conversation` (line 139) and `_resolve_conversation_id`'s ownership check (WR-08) |
| Stateless-serverless cache poisoning / staleness (an in-memory cache surviving across invocations would be invisible/incoherent on Vercel) | Tampering (of trust state) | D-04 explicitly avoids any in-process cache; all cross-turn state is reloaded from Postgres per Phase 7's already-locked Vercel-serverless architecture decision |

## Sources

### Primary (HIGH confidence)
- Direct source reads (this session): `backend/agent/trust.py`, `backend/agent/loop.py`, `backend/agent/tools.py`, `backend/routes/_sse.py`, `backend/routes/chat.py`, `backend/routes/onboarding.py`, `backend/routes/adaptations.py`, `backend/sports_science/plan.py`, `backend/sports_science/zones.py`, `backend/sports_science/constants.py`, `backend/sports_science/profile.py`, `backend/sports_science/capability_gap.py`, `backend/db.py`, `supabase/migrations/0001-0008*.sql`
- Test suite baseline run: `.venv/bin/python -m pytest tests/ -q` -> `9 failed, 250 passed` (this session, `[VERIFIED: local pytest run]`)
- Package versions: `.venv/bin/pip show supabase anthropic` -> supabase 2.31.0, anthropic 0.67.0 `[VERIFIED: pip show in project .venv]`

### Secondary (MEDIUM confidence)
- [Coggan Heart Rate Training Zone Calculator (maklinbikes.com, redirected from endurancepath.com)](https://maklinbikes.com/coggan-heart-rate-training-zone-calculator/) — Coggan/Allen HR zone percentages of LTHR: Z1 up to 68%, Z2 69-83%, Z3 84-94%, Z4 95-105%, Z5 106%+ `[CITED]`
- [Cycling Heart Rate Zones Calculator — Cyclists Hub](https://www.cyclistshub.com/tools/heart-rate-calculator/) and related aggregator results — cross-check on the ~85-90%-of-max-HR LTHR estimation fallback `[CITED, low-precision]`

### Tertiary (LOW confidence)
- WebSearch aggregate snippets for LTHR-from-max-HR fallback formula (rouvy.com, formbeat.com, cyclistshub.com) — consistent 85-90% range but explicitly caveated by every source as an inferior fallback to an actual threshold test `[ASSUMED — flagged in Assumptions Log A2]`

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages, all versions verified against the installed `.venv`
- Architecture: HIGH — every seam (dispatch_tool, run_turn, scan_buffer, save_messages, sse_generator) was read directly, not inferred
- Pitfalls: HIGH for D-01/D-02/D-03/D-04/D-06/D-07 (all directly confirmed against source); MEDIUM for D-05's exact LTHR-estimation formula and D-07's exact CTL-gap threshold (both explicitly "Claude's Discretion" per CONTEXT.md and flagged as assumptions needing planning-time confirmation)

**Research date:** 2026-07-04
**Valid until:** 30 days (stable internal codebase; no fast-moving external dependency drives this phase)
