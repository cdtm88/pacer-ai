---
phase: 02-agent-core
plan: "04"
subsystem: agent-compliance-test-suite
status: complete
tags: [tdd, pytest, compliance, trust-model, sse, asyncio, mocks, agent-loop]
completed: "2026-06-20"
duration: "5 min"

dependency_graph:
  requires:
    - 02-01 (fastapi, anthropic installed; agent/__init__.py, tools.py)
    - 02-02 (agent/loop.py: run_turn signature, event shapes, MAX_RETRIES)
    - 02-03 (agent/trust.py: scan_buffer, TrustViolation, handle_violation; api/main.py, api/routes/chat.py)
    - 01-xx (sports_science functions used as real tool dispatch targets in parallel/dedup tests)
  provides:
    - tests/agent/conftest.py: _MockStream class, mock stream fixtures, build_fake_client, scanner fixtures
    - tests/agent/test_loop.py: AGENT-01..04 + TRUST-04 loop compliance tests (8 tests)
    - tests/agent/test_trust.py: added TestTrustLoopCompliance (3 tests) to existing 28 scan_buffer tests
    - tests/agent/test_sse.py: AGENT-05 SSE event-sequence tests via ASGITransport (8 tests)
  affects:
    - 02-05 (SDK contract tests can reuse conftest fixtures)
    - 02-06 (trust corpus tests build on same mock infrastructure)
    - All future phases: 47-test agent compliance suite is the regression gate

tech_stack:
  added: []
  patterns:
    - "_MockStream class: native async context manager + __aiter__ async generator; avoids AsyncMock __aiter__ method-call bug"
    - "build_fake_client: streams consumed in sequence; last stream repeated if more calls than provided"
    - "monkeypatch.setattr on api.routes.chat.run_turn for SSE tests; preserves real scan_buffer wiring"
    - "parse_sse_frames: line-by-line SSE body parser returning list[{event, data}]"
    - "httpx.AsyncClient(transport=ASGITransport(app=app)) for no-server integration tests"

key_files:
  created:
    - tests/agent/conftest.py (_MockStream, fixtures for 6 stream scenarios, build_fake_client, scanner fixtures)
    - tests/agent/test_loop.py (8 tests: no_agent_sdk, stop_reason routing, parallel dispatch, dedup, retry cap, failed tool, audit log)
    - tests/agent/test_sse.py (8 tests: content-type, frame format, ordering text-only, ordering with tools, token data, done data, no-live-api, 422 validation)
  modified:
    - tests/agent/test_trust.py (appended TestTrustLoopCompliance: 3 tests for trust_violation_triggers_retry, attributed_number_passes, capability_gap_fallback)
    - agent/loop.py (Rule 1 fix: moved token event emission from inside stream iteration to after trust scan passes)

decisions:
  - "_MockStream class instead of AsyncMock for __aiter__: AsyncMock wraps __aiter__ as a bound method (passing self as first arg), which breaks the async generator protocol. A plain class with __aiter__ returning a native async generator is the correct approach."
  - "Retry cap assertion: loop runs while retries <= MAX_RETRIES (0..3), so MAX_RETRIES+1 trust_violation events are emitted before max_retries. Test updated to reflect actual loop invariant."
  - "Token emission moved post-trust-scan (Rule 1): the existing loop.py comment said 'Do NOT yield token events here -- buffer first' but the code yielded them anyway. Fixed to match the RESEARCH.md Pitfall anti-pattern requirement."
  - "monkeypatch.setattr(chat_module, 'run_turn', mock) for SSE tests: patches run_turn in the routes module namespace so sse_generator calls the mock, never instantiating a real AsyncAnthropic client."

metrics:
  duration: "5 min"
  tasks_completed: 2
  files_modified: 5
---

# Phase 02 Plan 04: Agent Compliance Test Suite Summary

47-test agent compliance suite (AGENT-06 gate) proving the raw-SDK loop with stop_reason discipline, parallel tool dispatch, dedup by (name, args_hash), 3-retry cap, trust scanner intercepting unsourced physiological numbers, capability-gap logging, and typed SSE event sequence -- all against mocked Anthropic streams with zero live API calls.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 (TDD) | Mock stream fixtures + loop compliance tests | 6281e35 | tests/agent/conftest.py, tests/agent/test_loop.py |
| 2 (TDD) | Trust scanner + SSE compliance tests | f652dd7 | tests/agent/test_trust.py, tests/agent/test_sse.py, agent/loop.py |

## Verification

- `pytest tests/agent/test_loop.py -x -q` -- 8 passed
- `pytest tests/agent/test_loop.py::test_no_agent_sdk -x -q` -- 1 passed
- `pytest tests/agent/test_loop.py::test_parallel_tool_dispatch -x -q` -- 1 passed
- `pytest tests/agent/test_loop.py::test_tool_deduplication -x -q` -- 1 passed
- `pytest tests/agent/test_loop.py::test_retry_limit -x -q` -- 1 passed
- `pytest tests/agent/test_loop.py::test_audit_log -x -q` -- 1 passed
- `grep -ci 'anthropic.com' tests/agent/test_loop.py` -- 0
- `pytest tests/agent/test_trust.py -x -q` -- 31 passed
- `pytest tests/agent/test_sse.py -x -q` -- 8 passed
- `pytest tests/agent/test_trust.py::TestTrustLoopCompliance::test_trust_violation_triggers_retry -x -q` -- 1 passed
- `pytest tests/agent/test_trust.py::TestTrustLoopCompliance::test_capability_gap_fallback -x -q` -- 1 passed
- `pytest tests/agent/ -x -q` -- 47 passed (AGENT-06 gate)
- `pytest tests/ -x -q` -- 115 passed (whole project suite green)
- `grep -ci 'anthropic.com' tests/agent/test_sse.py tests/agent/test_trust.py` -- 0
- `python -c "import claude_agent_sdk"` -- ModuleNotFoundError (AGENT-01 confirmed)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] AsyncMock `__aiter__` method-call protocol incompatibility**
- **Found during:** Task 1 RED -- `test_stop_reason_end_turn` failed with `TypeError: _build_stream.<locals>._aiter() takes 0 positional arguments but 1 was given`
- **Issue:** Setting `stream.__aiter__ = async_gen_fn` on an AsyncMock causes the mock to call it as a bound method, passing the mock object as `self`. Python's `async for` protocol expects `__aiter__` to return an async iterator, not to be called with the instance.
- **Fix:** Replaced the `_build_stream` helper function + AsyncMock approach with a `_MockStream` class implementing the full async context manager and `__aiter__` as a proper async generator method.
- **Files modified:** tests/agent/conftest.py
- **Commit:** 6281e35

**2. [Rule 1 - Bug] Retry count assertion off by one**
- **Found during:** Task 1 -- `test_retry_limit` asserted `len(violation_events) == MAX_RETRIES` (3) but got 4.
- **Issue:** The loop runs `while retries <= MAX_RETRIES` so it executes when retries=0,1,2,3 (four iterations), each yielding a trust_violation event. The count is MAX_RETRIES+1, not MAX_RETRIES.
- **Fix:** Updated test assertion to `expected_violations = MAX_RETRIES + 1` with a comment explaining the loop invariant.
- **Files modified:** tests/agent/test_loop.py
- **Commit:** 6281e35

**3. [Rule 1 - Bug] Token events emitted before trust scan in agent/loop.py**
- **Found during:** Task 2 -- `test_trust_violation_triggers_retry` failed because the violating text "250 watts" appeared in token events that were forwarded to the consumer before the trust scan ran.
- **Issue:** `agent/loop.py` contained a comment "Do NOT yield token events here -- buffer first, trust-scan later" but the code directly below yielded token events during streaming iteration. This contradicted the RESEARCH.md Pitfall anti-pattern and TRUST-03 requirement ("violating number never reaches the SSE stream").
- **Fix:** Removed the premature `yield {"event": "token", ...}` from inside the stream iteration loop. Added a post-scan token emission pass that yields all buffered chunks after the trust scan confirms the text is clean.
- **Files modified:** agent/loop.py
- **Commit:** f652dd7

## TDD Gate Compliance

| Gate | Commit | Status |
|------|--------|--------|
| RED (test commit) | 6281e35 | test(02-04): add loop compliance tests and mock stream fixtures |
| GREEN (feat/fix commit) | f652dd7 | test(02-04): add trust+SSE compliance tests; fix loop token-buffering |
| REFACTOR | n/a | No refactor needed |

Note: This plan is type=tdd with test-only deliverables. The GREEN commit adds the remaining tests (Task 2) and the Rule 1 fix to agent/loop.py that the compliance tests exposed. Both commits are in the test(02-04) namespace since the primary output is the test suite.

## Known Stubs

None. The compliance suite has no stubs -- all tests assert on real behavior with deterministic mocks.

## Threat Surface Scan

Files created are test-only and introduce no new network endpoints, auth paths, or schema changes. The Rule 1 fix to agent/loop.py changes when token events are emitted (post-scan vs. during-scan) but introduces no new trust boundary. No new surface outside the plan's threat register.

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-02-11 | test_trust_violation_triggers_retry proves violating text never reaches forwarded frames | Implemented |
| T-02-12 | No live Anthropic or Supabase calls in any test (all mocked) | Implemented |
| T-02-13 | test_audit_log asserts tool_use_id + name + result in every audit entry | Implemented |

## Self-Check: PASSED
