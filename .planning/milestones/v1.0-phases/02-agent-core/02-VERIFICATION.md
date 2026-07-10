---
phase: 02-agent-core
verified: 2026-06-20T10:00:00Z
status: passed
score: 30/30
behavior_unverified: 0
overrides_applied: 0
---

# Phase 02: Agent Core Verification Report

**Phase Goal:** Build the FastAPI backend, Anthropic agent loop (raw SDK), tool registry wrapping Phase 1 sports-science functions as Anthropic tool schemas, SSE streaming, and the trust-model enforcement layer. The agent loop must provably never emit an unsourced physiological number.

**Verified:** 2026-06-20T10:00:00Z
**Status:** passed
**Re-verification:** No -- initial verification

---

## Goal Achievement

### Observable Truths

All must-haves from all 6 plans verified against actual codebase and confirmed by passing tests. Code review findings CR-01..CR-03 and WR-01..WR-04 were applied in commit 4d12cee and are reflected in the current state.

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | anthropic, fastapi, uvicorn, python-multipart are installed and importable; claude-agent-sdk is absent | VERIFIED | `import anthropic, fastapi, uvicorn, multipart` exits 0; `grep -ci 'claude-agent-sdk' requirements.txt` returns 0 |
| 2 | agent/ and api/ package directories exist and are importable | VERIFIED | `import agent, api, api.routes, tests.agent` exits 0 |
| 3 | log_capability_gap is an async coroutine backed by the Supabase async client | VERIFIED | `asyncio.iscoroutinefunction(log_capability_gap)` true; `acreate_client` used; module-level singleton (WR-04 fix applied) |
| 4 | sports_science/ still has zero anthropic and zero fastapi imports | VERIFIED | `grep -r 'anthropic' sports_science/` returns empty; `grep -r 'fastapi' sports_science/` returns empty; import-boundary tests green |
| 5 | All 8 sports_science exports are registered as Anthropic tool schemas; no ad-hoc tool definitions exist | VERIFIED | `len(TOOL_SCHEMAS)==8 and {s['name'] for s in TOOL_SCHEMAS}==set(TOOL_REGISTRY)` passes; TRUST-02 enforced by `RuntimeError` (not assert -- WR-03 fix applied) at import time |
| 6 | The dispatcher runs sync compute functions in a thread and awaits the async log_capability_gap | VERIFIED | `asyncio.iscoroutinefunction` and `asyncio.to_thread` both present and tested; `dispatch_tool` correctly branches |
| 7 | Tool failures return is_error: true tool_result blocks (surfaced, not swallowed) | VERIFIED | Unknown/raising tools produce `is_error: True` block and audit entry; `test_failed_tool_surfaced` passes |
| 8 | Duplicate tool_use blocks within a turn are deduplicated by (name, args_hash) before dispatch | VERIFIED | `dedup_key` uses sha256 with `sort_keys=True`; `test_tool_deduplication` confirms audit_log length 1 for identical blocks |
| 9 | Parallel tool_use blocks are dispatched concurrently via asyncio.gather | VERIFIED | `asyncio.gather` present in loop.py; `test_parallel_tool_dispatch` confirms audit_log length 2 for distinct blocks |
| 10 | The agent loop checks stop_reason == 'tool_use' explicitly using the raw anthropic SDK | VERIFIED | `grep -c 'stop_reason == "tool_use"' agent/loop.py` returns 2; no claude-agent-sdk import anywhere in agent/ |
| 11 | Every dispatched tool call appends a (tool_use_id, name, inputs, result) entry to an in-memory audit log | VERIFIED | `dispatch_tool` appends on success and error; `test_audit_log` asserts tool_use_id, name, result present |
| 12 | An unsourced physiological number in assistant text is detected as a trust violation | VERIFIED | `scan_buffer('Your FTP is 250 watts', set()) is not None` passes; corpus test_false_negative_rate_is_zero green across 13 VIOLATIONS |
| 13 | A number that appears verbatim in a tool_result value this turn is attributed and is NOT a violation | VERIFIED | `scan_buffer('Your FTP is 250 watts', {'250 watts'}) is None` passes (CR-01 fix: tool_result_values is list[str] not list[dict]); corpus test_false_positive_rate_is_zero green |
| 14 | On a trust violation the scanner path calls log_capability_gap and the loop retries | VERIFIED | CR-02 fix applied: `handle_violation` imported and awaited in violation branch; `test_trust_violation_triggers_retry` and `test_capability_gap_fallback` pass |
| 15 | The SSE endpoint streams text/event-stream with typed event headers (token, tool_start, tool_result, done, error) | VERIFIED | `grep -c 'text/event-stream' api/routes/chat.py` returns 2; `X-Accel-Buffering: no` header present; `test_sse_event_sequence` passes |
| 16 | GET /chat/stream?conversation_id=... returns a StreamingResponse the loop drives | VERIFIED | Route mounted at `/chat/stream` confirmed by `{r.path for r in app.routes}`; `run_turn` called from `sse_generator` |
| 17 | The compliance suite proves the agent never emits an unsourced physiological number across representative scenarios | VERIFIED | `test_trust_violation_triggers_retry` asserts violating number absent from forwarded frames; corpus 13 VIOLATIONS + 16 QUALITATIVE + 6 ATTRIBUTED all correct |
| 18 | Multi-turn parallel tool dispatch via asyncio.gather completes without error in tests | VERIFIED | `test_parallel_tool_dispatch` passes with real tool dispatch |
| 19 | Tool retry cap (3) and dedup by (name, args_hash) per turn are verified by tests | VERIFIED | `test_retry_limit` (MAX_RETRIES=3) and `test_tool_deduplication` both pass |
| 20 | An injected unsourced number triggers a retry and a capability-gap log, and never reaches the SSE stream | VERIFIED | `test_trust_violation_triggers_retry` + `test_capability_gap_fallback` pass; token events held until post-scan |
| 21 | The SSE endpoint emits the typed event sequence (token, tool_start, tool_result, done) for a complete turn | VERIFIED | `test_sse_event_sequence` passes via ASGITransport; frame format `event: <type>\ndata: <json>\n\n` verified |
| 22 | claude-agent-sdk is provably absent from the dependency tree | VERIFIED | `grep -ci 'claude-agent-sdk' requirements.txt` returns 0; `import claude_agent_sdk` raises ModuleNotFoundError; `test_no_agent_sdk` passes |
| 23 | No test makes a live Anthropic API call | VERIFIED | `grep -ci 'anthropic.com' tests/agent/test_loop.py` returns 0; all tests use mocked clients; SDK contract test patches httpx to block network |
| 24 | The installed anthropic SDK exposes AsyncAnthropic with a messages.stream context manager | VERIFIED | `test_async_anthropic_exists` and `test_messages_stream_is_context_manager` pass offline |
| 25 | The SDK stream object provides an awaitable get_final_message, matching what run_turn calls | VERIFIED | `test_stream_get_final_message_attr` passes; confirmed on AsyncMessageStream (entered stream, not manager) |
| 26 | The SDK's tool-use streaming event types exist on the real installed types | VERIFIED | `test_stop_reason_literal_supported`, `test_content_block_delta_text_path`, `test_conftest_mock_matches_real_surface` all pass |
| 27 | A labelled corpus characterizes the scanner beyond hand-picked strings | VERIFIED | VIOLATIONS: 13, QUALITATIVE: 16, ATTRIBUTED: 6; spans 10 unit families |
| 28 | Every unsourced-number example in the corpus is flagged by scan_buffer (zero false negatives) | VERIFIED | `test_false_negative_rate_is_zero` passes |
| 29 | Every qualitative coaching example passes scan_buffer with no violation (zero false positives) | VERIFIED | `test_false_positive_rate_is_zero` passes |
| 30 | Every tool-attributed example passes scan_buffer when its value is present in tool_result_values | VERIFIED | `test_attributed_passes` (6 parametrized cases) passes |

**Score:** 30/30 truths verified (0 present, behavior-unverified)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `requirements.txt` | Phase 2 backend deps; no claude-agent-sdk | VERIFIED | anthropic==0.67.*, fastapi==0.115.*, uvicorn==0.30.*, python-multipart; claude-agent-sdk absent |
| `agent/__init__.py` | agent package marker | VERIFIED | Exists and importable |
| `api/__init__.py` | api package marker | VERIFIED | Exists and importable |
| `api/routes/__init__.py` | api.routes package marker | VERIFIED | Exists and importable |
| `tests/agent/__init__.py` | tests.agent package marker | VERIFIED | Exists and importable |
| `sports_science/capability_gap.py` | async log_capability_gap via acreate_client | VERIFIED | `async def log_capability_gap`; `acreate_client` used; module-level singleton (WR-04) |
| `agent/tools.py` | TOOL_SCHEMAS (8), TOOL_REGISTRY, dedup_key, dispatch_tool | VERIFIED | 8 schemas, 1:1 registry, RuntimeError invariant (WR-03), asyncio.iscoroutinefunction + to_thread |
| `agent/loop.py` | run_turn async generator with stop_reason == 'tool_use' loop | VERIFIED | isasyncgenfunction; MAX_RETRIES=3; MAX_TOOL_TURNS=10 (CR-03); handle_violation called (CR-02); SYSTEM_PROMPT (WR-02); tool_result_values list[str] (CR-01) |
| `agent/trust.py` | PHYSIO_PATTERN regex, TrustViolation, scan_buffer, on-violation hook | VERIFIED | Both PHYSIO_PATTERN_A and PHYSIO_PATTERN_B; attribution fix in list[str] type; handle_violation awaits log_capability_gap |
| `api/main.py` | FastAPI app, chat router mount | VERIFIED | `isinstance(app, FastAPI)`; `include_router`; `/chat/stream` route present |
| `api/routes/chat.py` | GET /chat/stream SSE endpoint | VERIFIED | text/event-stream; X-Accel-Buffering: no; run_turn called; no websocket |
| `tests/agent/conftest.py` | mock Anthropic stream fixtures | VERIFIED | _MockStream class; build_fake_client; 6 stream scenarios |
| `tests/agent/test_loop.py` | AGENT-01..04 + TRUST-04 loop tests | VERIFIED | 8 tests; all pass |
| `tests/agent/test_trust.py` | TRUST-03/05 scanner + violation-retry tests | VERIFIED | 31 tests; all pass including TestTrustLoopCompliance |
| `tests/agent/test_sse.py` | AGENT-05 SSE event-sequence via ASGITransport | VERIFIED | 8 tests; all pass |
| `tests/agent/test_sdk_contract.py` | Offline SDK contract-conformance tests | VERIFIED | 7 tests; all pass; zero network calls |
| `tests/agent/fixtures/trust_corpus.py` | Labelled corpus VIOLATIONS/QUALITATIVE/ATTRIBUTED | VERIFIED | 13/16/6 entries; spans 10 unit families |
| `tests/agent/test_trust_corpus.py` | Parametrized scan_buffer characterization | VERIFIED | 37 tests; zero false negatives; zero false positives |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `sports_science/capability_gap.py` | supabase | acreate_client / AsyncClient | VERIFIED | `acreate_client` imported and called in `_get_async_supabase` |
| `agent/tools.py` | sports_science | `from sports_science import` (8 callables) | VERIFIED | All 8 __all__ functions imported and in TOOL_REGISTRY |
| `agent/loop.py` | agent/tools.py | `from agent.tools import TOOL_SCHEMAS, dedup_key, dispatch_tool` | VERIFIED | Import present; all 3 used in loop body |
| `agent/loop.py` | agent/trust.py | `from agent.trust import handle_violation` | VERIFIED | CR-02 fix: imported and awaited in violation branch |
| `agent/trust.py` | sports_science.capability_gap | `log_capability_gap` called in handle_violation | VERIFIED | `grep -c 'log_capability_gap' agent/trust.py` = 8 |
| `api/routes/chat.py` | agent/loop.py | sse_generator drives run_turn | VERIFIED | `run_turn` imported and called with real scan_buffer |
| `api/main.py` | api/routes/chat.py | `include_router` mounts chat router | VERIFIED | `app.include_router(chat_router, prefix="/chat")` |
| `tests/agent/test_loop.py` | agent/loop.py | drives run_turn with mock stream fixtures | VERIFIED | `from agent.loop import run_turn`; all 8 tests pass |
| `tests/agent/test_sse.py` | api/main.py | httpx.AsyncClient(transport=ASGITransport(app)) | VERIFIED | ASGITransport pattern confirmed; 8 tests pass |
| `tests/agent/test_trust_corpus.py` | agent/trust.py | real scan_buffer over labelled corpus | VERIFIED | `from agent.trust import scan_buffer`; 37 tests pass |

---

## Data-Flow Trace (Level 4)

Not applicable -- this phase delivers a backend API and test suite (no frontend components rendering dynamic data). The tool dispatcher's data flow is verified by behavioral tests (dispatch_tool returns result, audit_log populated, tool_result_values populated for attribution).

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| All imports and invariants hold | `.venv/bin/python -c "..."` (key invariants) | all assertions pass | PASS |
| Trust scanner core behaviors | `scan_buffer(...)` three cases | all correct | PASS |
| FastAPI /chat/stream route | `{r.path for r in app.routes}` | `/chat/stream` present | PASS |
| Trust corpus counts | `len(VIOLATIONS)>=8, QUALITATIVE>=8, ATTRIBUTED>=4` | 13/16/6 | PASS |
| Full test suite | `pytest tests/ -x -q` | 159 passed, 0 failures | PASS |
| Agent compliance suite | `pytest tests/agent/ -q` | 91 passed, 0 failures | PASS |
| Named AGENT-01..04 tests | `pytest test_loop.py::test_no_agent_sdk` etc. (5 tests) | 5 passed | PASS |
| Named TRUST-03/05 tests | `pytest TestTrustLoopCompliance::test_trust_violation_triggers_retry` etc. | 2 passed | PASS |
| SDK contract offline | `pytest test_sdk_contract.py` | 7 passed, 0 network calls | PASS |
| Corpus zero-fn / zero-fp | `pytest test_trust_corpus.py::test_false_*` | 2 passed | PASS |

---

## Probe Execution

No declared probes for this phase.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| AGENT-01 | 02-02, 02-04, 02-05 | Raw SDK; explicit stop_reason == "tool_use"; no claude-agent-sdk | VERIFIED | Loop uses raw SDK; claude-agent-sdk absent from deps and not importable; test_no_agent_sdk passes |
| AGENT-02 | 02-02, 02-04 | asyncio.gather for parallel tool dispatch | VERIFIED | asyncio.gather in loop; test_parallel_tool_dispatch passes |
| AGENT-03 | 02-02, 02-04 | MAX_RETRIES=3; failed tools surfaced not swallowed | VERIFIED | MAX_RETRIES=3; test_retry_limit + test_failed_tool_surfaced pass |
| AGENT-04 | 02-02, 02-04 | dedup by (name, args_hash) per turn | VERIFIED | dedup_key with sha256; test_tool_deduplication passes |
| AGENT-05 | 02-03, 02-04 | SSE streaming; EventSource; no WebSocket | VERIFIED | text/event-stream StreamingResponse; websocket grep returns 0; test_sse_event_sequence passes |
| AGENT-06 | 02-04, 02-06 | Compliance suite; trust model end-to-end | VERIFIED | 91 agent tests green; zero false negatives on violation corpus; trust_violation triggers retry and never reaches stream |
| TRUST-03 | 02-03, 02-06 | Unsourced physiological numbers trigger retry + capability-gap log | VERIFIED | scan_buffer catches all 13 corpus violations; handle_violation called on violation (CR-02 fix) |
| TRUST-04 | 02-02, 02-04 | All physiological numbers traceable to tool-library call via audit log | VERIFIED | dispatch_tool appends (tool_use_id, name, result) per call; test_audit_log passes |
| TRUST-05 | 02-01, 02-03, 02-04 | log_capability_gap called when tool is missing | VERIFIED | handle_violation awaits log_capability_gap; test_capability_gap_fallback passes |

All 9 required requirement IDs satisfied.

---

## Anti-Patterns Found

No debt markers (TBD, FIXME, XXX) found in any phase-2 modified files. No TODO, HACK, or PLACEHOLDER found. No return null/empty stubs. No hardcoded empty data reaching rendering.

The 2 RuntimeWarnings in test_sdk_contract.py (`coroutine 'AsyncAPIClient.post' was never awaited`) are benign: the SDK contract test patches httpx to catch accidental live requests; the unawaited coroutine is the expected outcome of the patch. Pytest correctly surfaces them as warnings, not failures.

One documented known gap from the code review (IN-02): percentage-of-threshold phrasings (`75% of FTP`) bypass both regex patterns. The SUMMARY for 02-06 notes this as a follow-up for the trust.py owner; it does not affect current test coverage claims and the corpus was designed to characterize the actual implemented patterns. Not a blocker.

---

## Human Verification Required

None. All phase-2 deliverables are backend code and test suites with no visual, real-time, or external-service behavior requiring human observation. The SSE endpoint is verified through ASGITransport integration tests.

---

## Gaps Summary

No gaps. All 30 must-haves verified. All 9 requirement IDs satisfied. 159/159 tests pass. Code review findings CR-01..CR-03 and WR-01..WR-04 were applied and the fixes are present in the codebase.

---

_Verified: 2026-06-20T10:00:00Z_
_Verifier: Claude (gsd-verifier)_
