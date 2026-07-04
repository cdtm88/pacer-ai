# Phase 8: Trust Model Integrity - Pattern Map

**Mapped:** 2026-07-04
**Files analyzed:** 14
**Analogs found:** 12 / 14

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|--------------------|------|-----------|-----------------|----------------|
| `backend/agent/audit.py` (NEW) | service | CRUD (best-effort write + read) | `backend/sports_science/capability_gap.py` | exact (behavior pattern) + `backend/db.py` (client-acquisition pattern) |
| `backend/agent/tools.py::dispatch_tool` (modify) | service/controller | request-response | itself (`backend/agent/tools.py:559-655`, existing `user_id` injection block) | exact — same file, extend existing pattern |
| `backend/agent/trust.py::scan_buffer` (modify) | utility | transform (pure regex/parse) | itself (`backend/agent/trust.py:94-163`) | exact — same file, replace substring check |
| `backend/agent/loop.py::run_turn` (modify) | service | streaming/event-driven | itself (`backend/agent/loop.py:46-` , `tool_result_values` construction) | exact — same file, add seeding step |
| `backend/routes/_sse.py::sse_generator` (modify) | controller | streaming (SSE) | itself (`backend/routes/_sse.py:34-89`) | exact — same file, thread new kwarg |
| `backend/routes/chat.py` (modify) | controller | request-response/streaming | itself (`backend/routes/chat.py:71-120`) | exact — same file, pass `conversation_id` |
| `backend/routes/onboarding.py` (modify) | controller | request-response | itself (system prompt string + `save_profile` call site) | exact — same file |
| `backend/sports_science/constants.py` (modify) | config | transform | itself (`POWER_ZONE_BOUNDARIES` as sibling constant, lines 8-16) | exact — same file, correct `HR_ZONE_BOUNDARIES` |
| `backend/sports_science/profile.py` (modify) | service | CRUD | itself (`save_profile`, lines 47-94) | exact — same file, add `hr_zones_available` param/column |
| `backend/sports_science/plan.py` (modify) | service | transform (pure compute) | itself (`generate_plan`/`_build_sessions`, lines 73-, 202-250) | exact — same file, wire dead params |
| `supabase/migrations/0009_audit_log_and_hr_zones_flag.sql` (NEW) | migration | batch/DDL | `supabase/migrations/0006_pmc_unique_and_fits_bucket.sql` | exact |
| `tests/agent/test_audit.py` (NEW) | test | CRUD (mocked) | `tests/sports_science/test_capability_gap.py` | exact |
| `tests/sports_science/test_plan.py` (NEW) | test | transform | `tests/sports_science/test_zones.py` / `test_load.py` | role-match |
| `tests/agent/test_loop.py`, `test_tools_phase3.py`, `test_trust.py` (extend) | test | event-driven/request-response | themselves (existing test files) | exact |

## Pattern Assignments

### `backend/agent/audit.py` (NEW — service, CRUD)

**Analogs:** `backend/sports_science/capability_gap.py` (behavior shape) + `backend/db.py` (client acquisition — use this, not a 4th duplicated singleton)

**Client acquisition** (`backend/db.py:24-46`, use directly, do not re-implement):
```python
from backend.db import get_async_supabase
```

**Best-effort insert pattern** (`backend/sports_science/capability_gap.py:73-82`):
```python
try:
    supabase = await _get_async_supabase()
    await supabase.table("capability_gaps").insert({
        "user_id": user_id,
        "method_name": method_name,
        "description": f"Missing tool: {method_name}",
        "context": context,
    }).execute()
except Exception:
    pass  # gap logging is best-effort; never block the fallback response
```

**Apply to `write_audit_entry`:**
```python
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
        pass  # best-effort; mirrors capability_gap.py
```

**`load_prior_audit_values(conversation_id, user_id)` — read side.** No direct analog exists (this is a new read pattern); use the `pmc_history` query shape below as the query-construction template, filtered/ordered by `conversation_id, created_at` and re-enforcing `.eq("user_id", user_id)` app-layer (defense-in-depth, matching `onboarding.py::load_conversation`'s ownership check pattern, WR-08).

---

### `backend/agent/tools.py::dispatch_tool` (modify — service/controller, request-response)

**Analog:** itself — the existing `user_id` injection allowlist at `backend/agent/tools.py:577-597`.

**Existing pattern to extend (lines 577-597):**
```python
if name in {"save_profile", "generate_plan"}:
    inputs = {k: v for k, v in inputs.items() if k != "user_id"}
    if user_id is None:
        error_text = f"server identity required for tool '{name}' (no user_id available)"
        audit_log.append({"tool_use_id": tool_use_id, "name": name, "error": error_text})
        return {"type": "tool_result", "tool_use_id": tool_use_id,
                "content": [{"type": "text", "text": f"Error: {error_text}"}],
                "is_error": True}
    inputs = {**inputs, "user_id": user_id}
```

**Audit-append call sites to convert into durable writes** (lines 586, 601, 629, 642 — `audit_log.append({...})`): each of these four dict-append sites becomes a call to `write_audit_entry(...)` (fire-and-forget best-effort, per D-01), in addition to (not instead of) the existing in-memory `audit_log.append` (same-turn reads in the D-02/D-07 injection block still need the in-memory list).

**New D-02/D-07 injection block** — insert immediately after the existing `if name in {"save_profile", "generate_plan"}:` block, gated to `name == "generate_plan"` only, following the exact `pmc_history` query already proven in `backend/routes/adaptations.py:550-558`:
```python
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

**Function signature to extend:** `dispatch_tool(tool_use_block, audit_log: list, user_id: str | None = None)` gains `conversation_id: str | None = None`, threaded the same way `user_id` was added in commit `b3fcf39` (260702-wev).

---

### `backend/agent/trust.py::scan_buffer` (modify — utility, transform)

**Analog:** itself — `backend/agent/trust.py:94-163`, the exact substring checks to replace:
```python
if not any(
    s in val for val in tool_result_values for s in (matched, bare_number)
):
```
and
```python
attributed = any(
    s in val
    for val in tool_result_values
    for s in [full_match, synthetic, num]
)
```

**Replace with numeric-token + tolerance helper** (per RESEARCH.md Pattern 3):
```python
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
Preserve the surrounding function structure (Pattern A loop, then Pattern B loop, same `TrustViolation` dataclass and `matched_text`/`pattern` fields) — only the attribution boolean expression changes. `handle_violation` (lines 166-195) is unaffected; do not touch it.

---

### `backend/agent/loop.py::run_turn` (modify — service, streaming)

**Analog:** itself — `tool_result_values: list[str] = []` initialization (line 85) and the `dispatch_tool(b, audit_log, user_id=user_id)` call (line 209).

**Seeding insertion point:** immediately after line 85's `tool_result_values: list[str] = []`, before the first `trust_scanner(buffered_text, tool_result_values)` call (line 122):
```python
tool_result_values: list[str] = []
if conversation_id is not None:
    tool_result_values.extend(
        await load_prior_audit_values(conversation_id, user_id=user_id)
    )
```

**Signature/call-site to extend:** `run_turn(..., user_id: str | None = None)` gains `conversation_id: str | None = None`; the `dispatch_tool` call (line 209) gains `conversation_id=conversation_id`:
```python
*[dispatch_tool(b, audit_log, user_id=user_id, conversation_id=conversation_id) for b in unique_blocks]
```

---

### `backend/routes/_sse.py::sse_generator` / `backend/routes/chat.py` (modify — controller)

**Analog:** itself — the existing `user_id` threading precedent.

`_sse.py` (lines 40, 86-89):
```python
user_id: str | None = None,
...
if user_id is not None:
    kwargs["user_id"] = user_id
async for event in fn(messages, client, model, scan_buffer, audit_log, **kwargs):
```
Add identical `conversation_id` parameter + kwargs threading.

`chat.py` (line 110):
```python
async for chunk in sse_generator(messages, model, _run_turn=run_turn, assistant_sink=assistant_sink, user_id=user_id):
```
Add `conversation_id=conversation_id` (already in scope at line 71, `Query(...)`).

`onboarding.py`: same threading pattern at its own `sse_generator` call site; also insert the new LTHR onboarding question into `ONBOARDING_SYSTEM_PROMPT`, following the existing question-flow string convention already used for FTP/back-status questions in that same prompt.

---

### `backend/sports_science/constants.py` (modify — config)

**Analog:** itself — `POWER_ZONE_BOUNDARIES` (lines 8-16) as the sibling convention to follow (contiguous zones, `upper == next.lower`).

**Current (buggy) value to replace** (lines 27-33):
```python
HR_ZONE_BOUNDARIES = [
    {"zone": 1, "name": "Active Recovery", "lower": 0.00, "upper": 0.81},
    {"zone": 2, "name": "Aerobic",         "lower": 0.81, "upper": 0.90},
    {"zone": 3, "name": "Tempo",           "lower": 0.90, "upper": 0.94},
    {"zone": 4, "name": "Threshold",       "lower": 0.94, "upper": 1.00},
    {"zone": 5, "name": "VO2max",          "lower": 1.00, "upper": None},
]
```

**Corrected value (D-06, per RESEARCH.md):**
```python
HR_ZONE_BOUNDARIES = [
    {"zone": 1, "name": "Active Recovery", "lower": 0.00, "upper": 0.68},
    {"zone": 2, "name": "Endurance",       "lower": 0.68, "upper": 0.83},
    {"zone": 3, "name": "Tempo",           "lower": 0.83, "upper": 0.94},
    {"zone": 4, "name": "Threshold",       "lower": 0.94, "upper": 1.05},
    {"zone": 5, "name": "VO2max",          "lower": 1.05, "upper": None},
]
```
`backend/sports_science/zones.py::calculate_hr_zones` (line 31) needs no code change — boundaries flow from `constants.py` alone.

---

### `backend/sports_science/profile.py::save_profile` (modify — service, CRUD)

**Analog:** itself — `save_profile` (lines 47-94), which already has a `preferred_days: list[str]` parameter (line 51) persisted at line 94 (`"preferred_days": preferred_days`). Follow the exact same parameter-then-dict-key pattern to add `hr_zones_available: bool | None = None` alongside it.

---

### `backend/sports_science/plan.py::generate_plan` / `_build_sessions` (modify — service, transform)

**Analog:** itself — `_DEFAULT_DAYS = ["Tuesday", "Thursday", "Saturday", "Sunday"]` (line 17) and its hardcoded use `days = _DEFAULT_DAYS[:n_sessions]` (line 95); `generate_plan(..., current_ctl: float, load_targets: dict, ...)` (lines 202-250) which currently accepts but never reads these params.

**Wiring target — replace line 95's hardcode with:**
```python
days = (preferred_days or _DEFAULT_DAYS)[:n_sessions]
```

**New CTL-gap-aware progression helper (D-07, per RESEARCH.md, `gap_ratio >= 0.5` threshold flagged Claude's Discretion/A3 — confirm during planning):**
```python
def _is_true_beginner_ramp(current_ctl: float, load_targets: dict) -> bool:
    target = load_targets.get("recommended_ctl_target", current_ctl) or 0.0
    if target <= 0:
        return False
    gap_ratio = (target - current_ctl) / target
    return current_ctl <= 0 or gap_ratio >= 0.5
```
Apply inside `_build_sessions`: when true, Weeks 2-3 use the same conservative duration cap as Week 1 (flat volume) instead of the uncapped base_duration; when combined with `back_status == "moderate"`, tighten Week 1's cap further (e.g. `min(20, ...)` instead of `min(30, ...)`).

---

### `supabase/migrations/0009_audit_log_and_hr_zones_flag.sql` (NEW — migration)

**Analog:** `supabase/migrations/0006_pmc_unique_and_fits_bucket.sql` — idempotent `IF NOT EXISTS`/`ADD COLUMN IF NOT EXISTS` style, dated comment header explaining the "why," RLS-aware.

```sql
-- 0006 header style to mirror:
-- -- 0006: Close two live-verification gaps found during Phase 6 UAT (2026-07-03).
-- --
-- -- 1. <problem statement>
-- -- 2. <problem statement>

CREATE TABLE IF NOT EXISTS public.audit_log (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         uuid,
    conversation_id uuid,
    tool_use_id     text NOT NULL,
    tool_name       text NOT NULL,
    inputs          jsonb,
    result          jsonb,
    is_error        boolean NOT NULL DEFAULT false,
    created_at      timestamptz DEFAULT now() NOT NULL
);

ALTER TABLE public.audit_log ENABLE ROW LEVEL SECURITY;

CREATE POLICY "audit_log: own row" ON public.audit_log
    USING (user_id = auth.uid());

CREATE INDEX IF NOT EXISTS audit_log_conversation_created_idx
    ON public.audit_log (conversation_id, created_at);

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS hr_zones_available boolean;
```

---

### Test files (extend/new)

**`tests/agent/test_audit.py` (NEW) — analog `tests/sports_science/test_capability_gap.py`:** mock `backend.db.get_async_supabase` the same way that file mocks `acreate_client` (module-level monkeypatch of the singleton, per `backend/db.py`'s documented "Test monkeypatching" docstring: `import backend.db as db_module; db_module._supabase_client = my_mock_client`).

**`tests/sports_science/test_plan.py` (NEW) — analog `tests/sports_science/test_zones.py`/`test_load.py`:** one-file-per-module convention; extract `generate_plan`'s existing inline tests out of `tests/agent/test_tools_phase3.py` into this new file, add D-07 CTL-gap-ramp + preferred_days parametrized cases.

**`tests/agent/test_loop.py` (extend):** mocking pattern for `test_user_id_injected_server_side_through_run_turn` at line 345 is the exact template for the new `generate_plan` server-injection assertions — patch `TOOL_REGISTRY["generate_plan"]` with `MagicMock`, assert `call_args.kwargs` carries server-sourced values regardless of what the fake tool_use block supplied.

**`tests/sports_science/test_zones.py` (extend):** mirror the existing `test_zone_boundary_no_overlap` (power zones, line 40) with an HR-zone equivalent — none exists today.

## Shared Patterns

### Best-effort DB write (never blocks caller)
**Source:** `backend/sports_science/capability_gap.py:73-82`
**Apply to:** `backend/agent/audit.py::write_audit_entry` (D-01)
```python
try:
    ...
except Exception:
    pass
```

### Centralized Supabase client acquisition
**Source:** `backend/db.py:24-46`
**Apply to:** `backend/agent/audit.py` (do NOT add a 4th duplicated module-level singleton like `capability_gap.py`/`profile.py` predate — use `get_async_supabase()` directly)

### Server-side value injection over trusting LLM tool-call arguments
**Source:** `backend/agent/tools.py:577-597` (the `user_id` allowlist, commit `b3fcf39`/260702-wev)
**Apply to:** `dispatch_tool`'s new `generate_plan`-only interception for `current_ctl`, `ftp_watts`, `ftp_confidence`, `load_targets`, `preferred_days` (D-02/D-07) — same "strip any LLM-supplied value, inject server-verified value" shape, just five more keys on one more tool.

### `user_id`/`conversation_id` threading through the SSE call chain
**Source:** the existing `user_id` chain: `chat.py:110` → `_sse.py:40,86-89` → `loop.py:46-53,209`
**Apply to:** identical threading of `conversation_id` alongside `user_id` at every one of those same call sites (D-01/D-04).

### Ownership re-enforcement on scoped reads (defense-in-depth)
**Source:** `backend/routes/onboarding.py::load_conversation` (line 139) and its `_resolve_conversation_id` ownership check (WR-08)
**Apply to:** `load_prior_audit_values`'s query — RLS handles it, but re-enforce `.eq("user_id", user_id)` at the app layer too, matching this existing pattern.

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `backend/agent/audit.py::load_prior_audit_values` | service | event-driven (cross-turn read) | No existing "reload prior turn's data from a persisted store, scoped by conversation" read pattern exists anywhere in the codebase today; closest partial analog is the `pmc_history` latest-row query shape (`adaptations.py:550-558`) for query construction only, not for the conversation-scoped semantics. Planner should treat this as new-pattern territory guided by RESEARCH.md's Architecture Diagram, not an existing-code copy. |
| LTHR-from-max-HR estimation tool (D-05) | service (pure compute) | transform | No existing tool computes a *derived estimate with explicit low-confidence methodology tagging* from a single scalar input; `estimate_ftp_from_rides`'s `confidence` field is the closest sibling convention (same `ToolResult` shape: `value`, `unit`, `methodology`, `inputs`) but the actual formula has no precedent in this codebase. |

## Metadata

**Analog search scope:** `backend/agent/`, `backend/routes/`, `backend/sports_science/`, `backend/db.py`, `supabase/migrations/`, `tests/agent/`, `tests/sports_science/`
**Files scanned:** `capability_gap.py`, `db.py`, `trust.py`, `tools.py`, `loop.py`, `_sse.py`, `chat.py`, `onboarding.py`, `constants.py`, `profile.py`, `plan.py`, `zones.py`, `0006_pmc_unique_and_fits_bucket.sql`
**Pattern extraction date:** 2026-07-04
