---
phase: 02-agent-core
reviewed: 2026-06-20T00:00:00Z
depth: standard
files_reviewed: 9
files_reviewed_list:
  - agent/__init__.py
  - agent/loop.py
  - agent/tools.py
  - agent/trust.py
  - api/__init__.py
  - api/main.py
  - api/routes/chat.py
  - api/routes/__init__.py
  - sports_science/capability_gap.py
findings:
  critical: 3
  warning: 4
  info: 2
  total: 9
status: clean
---

# Phase 02: Code Review Report

**Reviewed:** 2026-06-20
**Depth:** standard
**Files Reviewed:** 9
**Status:** needs-fix

## Summary

The agent core implementation is structurally sound and correctly follows the raw-SDK, explicit-stop-reason, parallel-dispatch pattern required by AGENT-01 and AGENT-02. The trust scanner regex patterns are well-reasoned and the module separation is clean.

Three critical defects make the implementation unshippable:

1. The trust attribution check is completely broken due to a type mismatch between `loop.py` and `scan_buffer`: the scanner receives `list[dict]` but operates expecting `set[str]`. The `in` operator on a dict tests key membership, never string content. Every tool-result-echoed number will falsely trigger as a violation, and no real attribution ever occurs.

2. `handle_violation` is never called from anywhere. The DB-backed capability-gap log that satisfies TRUST-05 is dead code: trust violations are detected but never logged.

3. The `while` loop has no bound on tool-use iterations. The `retries` counter only increments on trust violations; an infinite `stop_reason == "tool_use"` cycle from the model is unbounded.

---

## Critical Issues

### CR-01: `tool_result_values` type mismatch breaks trust attribution entirely

**File:** `agent/loop.py:67,169` and `agent/trust.py:96`

**Issue:** `loop.py` initializes `tool_result_values` as `list[dict]` (line 67) and appends full `result_block` dicts (line 169). `scan_buffer` declares its parameter as `set[str]` and performs `matched in val` for each `val` in the collection. When `val` is a `dict`, Python's `in` operator tests key membership, not string content. The result: numbers echoed verbatim from tool results are never attributed (always flagged as violations), while the attribution guard against fabricated numbers produces meaningless true/false results based on whether the matched text happens to be a dict key name like `"type"` or `"content"`. The entire attribution logic is inoperative.

Concrete example: Claude echoes `"150 watts"` from a `calculate_power_zones` result. `result_block` has keys `["type", "tool_use_id", "content", "is_error"]`. `"150 watts" in result_block` is `False` (not a key). The scanner fires a false positive trust violation.

Note also that `tool_result_values` is reset to `[]` at the top of each while-loop iteration (line 67), so even if the type were correct, turn-N text echoing turn-(N-1) tool results would always fail attribution. The per-turn reset is consistent with D-09, but compounds the risk when combined with the type bug.

**Fix:** In `loop.py`, populate `tool_result_values` with the extracted JSON text string, not the raw dict. Move the string extraction before the append, and collect `content_text` into a `list[str]`:

```python
# Replace lines 169-174 in loop.py:
content_text = None
content_list = result_block.get("content", [])
if content_list and isinstance(content_list[0], dict):
    content_text = content_list[0].get("text")
if content_text:
    tool_result_values.append(content_text)   # list[str], not list[dict]
```

Change `tool_result_values: list[dict] = []` (line 67) to `tool_result_values: list[str] = []`.

In `scan_buffer` (trust.py:96), update the type annotation from `set[str]` to `list[str]` to match:
```python
def scan_buffer(text: str, tool_result_values: list[str]) -> Optional[TrustViolation]:
```

---

### CR-02: `handle_violation` never called -- TRUST-05 audit log is dead code

**File:** `agent/loop.py:102-123` (violation branch), `agent/trust.py:158-186`

**Issue:** TRUST-05 requires that the capability-gap log fires on every TRUST-03 detection. `handle_violation` in `trust.py` is the async hook that calls `log_capability_gap` to write the DB record. It is never imported or called from `loop.py` or anywhere else. Trust violations are detected and the retry path executes, but the DB audit entry is never created. The compliance requirement is not met: there is no audit trail for trust violations.

**Fix:** Import and await `handle_violation` in `loop.py` inside the violation branch:

```python
# In agent/loop.py, add to imports:
from agent.trust import handle_violation

# In the violation branch (after line 102):
if violation:
    retries += 1
    await handle_violation(violation)   # TRUST-05: log capability gap
    messages.append({...})
    yield {"event": "error", ...}
    continue
```

`handle_violation` is already best-effort (its internal `log_capability_gap` swallows DB errors), so `await`-ing it does not risk blocking the retry path.

---

### CR-03: Infinite tool-use loop -- no iteration cap on `stop_reason == "tool_use"`

**File:** `agent/loop.py:65`

**Issue:** The `while retries <= MAX_RETRIES` condition only bounds trust-violation retries. If the model returns `stop_reason == "tool_use"` every turn and the trust scanner never fires (the normal, correct path), `retries` is never incremented and the loop runs forever. A misbehaving model, an agentic loop bug, or a runaway tool chain will cause an unbounded server-side loop consuming Anthropic API credits and blocking the SSE connection indefinitely.

**Fix:** Introduce a separate `tool_turns` counter bounded by a reasonable maximum (e.g. 10):

```python
MAX_TOOL_TURNS: int = 10

async def run_turn(...):
    retries: int = 0
    tool_turns: int = 0

    while retries <= MAX_RETRIES:
        ...
        if stop_reason == "tool_use":
            tool_turns += 1
            if tool_turns > MAX_TOOL_TURNS:
                yield {
                    "event": "error",
                    "data": {
                        "code": "max_tool_turns",
                        "message": f"Tool-use turn limit ({MAX_TOOL_TURNS}) exceeded",
                    },
                }
                return
            messages.append(...)
            ...
        elif stop_reason == "end_turn":
            ...
```

---

## Warnings

### WR-01: All-duplicate dedup produces empty tool-result content block, likely causing API error

**File:** `agent/loop.py:163-185`

**Issue:** When all `tool_use_blocks` in a turn are deduplicated (all appear in `seen_calls`), `unique_blocks` is `[]`. `asyncio.gather()` with no arguments returns `[]`, and `messages.append({"role": "user", "content": []})` inserts an empty-content user message. The Anthropic API rejects empty `content` arrays; the next streaming call will raise an API error, which propagates to the `sse_generator` catch block and emits a `server_error` event rather than a typed `max_retries` or `tool_error` event.

In practice, full deduplication within a single turn is rare but possible (e.g. Claude requests the same tool with identical args twice in one response).

**Fix:** Guard against empty dispatch and return cached results directly:

```python
if not unique_blocks:
    # All blocks were duplicates; nothing to dispatch.
    # Append a minimal user acknowledgement so the conversation can continue.
    messages.append({"role": "user", "content": [{"type": "text", "text": "(duplicate tool calls skipped)"}]})
else:
    result_blocks = await asyncio.gather(
        *[dispatch_tool(b, audit_log) for b in unique_blocks]
    )
    ...
    messages.append({"role": "user", "content": list(result_blocks)})
```

---

### WR-02: No system prompt passed to Anthropic API

**File:** `agent/loop.py:75-80`, `api/routes/chat.py:98-116`

**Issue:** `client.messages.stream(model=model, max_tokens=4096, tools=TOOL_SCHEMAS, messages=messages)` passes no `system=` parameter. Claude has no coaching persona and no explicit instruction to use tools for physiological numbers rather than emitting them directly. The code-level trust scanner is the enforcement backstop, but a system prompt significantly reduces the violation rate and false-positive pressure on the retry loop. Without one, the agent produces generic assistant behavior rather than acting as a cycling coach.

This is a behavioral correctness issue: the agent will not behave as specified in the PRD or PROJECT.md.

**Fix:** Define a `SYSTEM_PROMPT` constant (in `agent/loop.py` or a separate `agent/prompts.py`) and pass it:

```python
SYSTEM_PROMPT = (
    "You are PacerAI, an evidence-based adaptive cycling coach. "
    "You MUST call a tool for any physiological number (power zones, TSS, FTP, CTL, ATL, TSB, HR zones). "
    "Never emit a physiological number from your own reasoning -- use only the provided tools. "
    "If no tool covers the needed calculation, call log_capability_gap."
)

async with client.messages.stream(
    model=model,
    max_tokens=4096,
    tools=TOOL_SCHEMAS,
    system=SYSTEM_PROMPT,
    messages=messages,
) as stream:
```

---

### WR-03: `assert` used for TRUST-02 invariant -- stripped by `-O` flag

**File:** `agent/tools.py:265-268`

**Issue:** Python's `assert` statements are silently removed when the interpreter runs with the `-O` (optimize) flag. The TRUST-02 registry/schema parity check exists specifically to catch misconfiguration that would allow unregistered tools or unschematized tools. If stripped, the invariant is not enforced at startup. Gunicorn does not pass `-O` by default, but Docker images built with `python -O` or custom Railway configurations would silently bypass this check.

**Fix:** Replace the `assert` with an explicit guard:

```python
if _schema_names != _registry_names:
    raise RuntimeError(
        f"TRUST-02 violation: TOOL_SCHEMAS names {_schema_names} "
        f"!= TOOL_REGISTRY keys {_registry_names}"
    )
```

---

### WR-04: Supabase `AsyncClient` created per-call with no cleanup -- connection leak

**File:** `sports_science/capability_gap.py:19-29,53`

**Issue:** `_get_async_supabase()` calls `acreate_client(url, key)` on every `log_capability_gap` invocation and returns a new `AsyncClient`. The `AsyncClient` wraps an `httpx.AsyncClient` which maintains a connection pool. The client is never closed (no `await supabase.close()`, no async context manager). Under any load, each gap-log call leaks a file descriptor and HTTP connection. `log_capability_gap` is called on every trust violation (once CR-02 is fixed) and every capability-gap tool invocation, so this leak is exercised in normal operation.

**Fix:** Use an async context manager pattern or close the client after use:

```python
async def log_capability_gap(method_name: str, context: dict, user_id: str | None = None) -> ToolResult:
    try:
        supabase = await _get_async_supabase()
        try:
            await supabase.table("capability_gaps").insert({...}).execute()
        finally:
            await supabase.aclose()  # release connection pool
    except Exception:
        pass
```

Alternatively, consider a module-level singleton client initialized in the FastAPI lifespan (deferred to Phase 3 per CONTEXT.md, but noted here as the correct long-term fix).

---

## Info

### IN-01: `loop.py` docstring describes wrong type for `trust_scanner` parameter

**File:** `agent/loop.py:22`

**Issue:** The module docstring at line 22 states the trust_scanner signature is `trust_scanner(text: str, tool_result_values: list[dict]) -> TrustViolation | None`. The actual `scan_buffer` signature (trust.py:96) is `set[str]`. Neither matches the `list[dict]` actually passed. The docstring encodes the wrong contract and will mislead anyone writing a test mock or alternate scanner.

**Fix:** After resolving CR-01 (changing to `list[str]`), update the docstring to match: `trust_scanner(text: str, tool_result_values: list[str]) -> TrustViolation | None`.

---

### IN-02: Percentage-of-threshold phrasings bypass both regex patterns

**File:** `agent/trust.py:43-80`

**Issue:** Neither `PHYSIO_PATTERN_A` nor `PHYSIO_PATTERN_B` catches phrases like `"ride at 75% of FTP"`, `"80% of threshold"`, or `"90% of your max heart rate"`. These are physiological intensity prescriptions that could encode fabricated targets. The current patterns require the unit keyword adjacent to a bare number (`250 watts`, `FTP 250`), so percentage-qualified descriptions bypass detection entirely.

This is likely an intentional design tradeoff (percentages are qualitative-ish and the doc notes the pattern can be tuned), but it should be explicitly documented as a known limitation rather than a silent gap.

**Fix (optional):** Add a third pattern for `\b\d{1,3}%\s+of\b` or extend `PHYSIO_PATTERN_A` to include `%\s*(?:FTP|HR|LTHR|threshold|max)` constructions. At minimum, add a comment to `trust.py` documenting this as a known bypass vector.

---

_Reviewed: 2026-06-20_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
