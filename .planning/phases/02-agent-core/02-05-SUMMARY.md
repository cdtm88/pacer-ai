---
phase: 02-agent-core
plan: "05"
subsystem: agent-sdk-contract
status: complete
tags: [contract-test, anthropic-sdk, offline, introspection, streaming, tool-use]
completed: "2026-06-20"
duration: "4 min"

dependency_graph:
  requires:
    - 02-02 (agent/loop.py: run_turn call sites — messages.stream, get_final_message, stop_reason, delta.text)
    - 02-04 (tests/agent/conftest.py: _MockStream attribute surface whose names are validated here)
  provides:
    - tests/agent/test_sdk_contract.py: 7 offline SDK contract-conformance tests
  affects:
    - All future plans: RESEARCH.md A1/A2/Open Question 1 now backed by hard offline gate; SDK upgrade will fail loudly not silently

tech_stack:
  added: []
  patterns:
    - "Offline type introspection: hasattr, model_fields, isinstance, class MRO inspection — never a network call"
    - "Two-stage stream model: AsyncMessageStreamManager (manager, no get_final_message) -> AsyncMessageStream (entered stream, has get_final_message)"
    - "httpx.Client.send + httpx.AsyncClient.send patched in test_no_network_call to catch any accidental live requests"
    - "Literal annotation introspection via repr(field_info.annotation) for Pydantic v2 Union/Literal types"

key_files:
  created:
    - tests/agent/test_sdk_contract.py (7 offline SDK contract tests; 334 lines)
  modified: []

decisions:
  - "get_final_message lives on AsyncMessageStream (the entered stream), NOT AsyncMessageStreamManager (the pre-entry manager) — the contract test documents and asserts this two-stage distinction"
  - "Text-delta path confirmed as RawContentBlockDeltaEvent.delta (union) -> TextDelta.text, validated via TextDelta.model_fields"
  - "stop_reason annotation confirmed via repr(Message.model_fields['stop_reason'].annotation) which includes both 'tool_use' and 'end_turn' literals"

metrics:
  duration: "4 min"
  tasks_completed: 1
  files_modified: 1
---

# Phase 02 Plan 05: SDK Contract-Conformance Tests Summary

Offline contract suite proving the real installed anthropic==0.67.x type surface matches every attribute run_turn and the conftest mocks depend on: AsyncAnthropic construction, messages.stream async context manager, AsyncMessageStream.get_final_message, Message.stop_reason with tool_use/end_turn literals, ToolUseBlock name/input/id, and the RawContentBlockDeltaEvent->TextDelta.text delta path.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Offline anthropic SDK contract-conformance tests | e58ebb3 | tests/agent/test_sdk_contract.py |

## Verification

- `pytest tests/agent/test_sdk_contract.py -x -q` -- 7 passed
- `pytest tests/agent/ -x -q` -- 54 passed (47 pre-existing + 7 new; AGENT-06 gate still green)
- `grep -c 'import anthropic' tests/agent/test_sdk_contract.py` returns 1
- `grep -c 'get_final_message' tests/agent/test_sdk_contract.py` returns 20
- `grep -c 'stop_reason' tests/agent/test_sdk_contract.py` returns 16
- `grep -ci 'api.anthropic.com' tests/agent/test_sdk_contract.py` returns 0
- `grep -c '.messages.create' tests/agent/test_sdk_contract.py` returns 0
- `.venv/bin/python -c "import anthropic; from anthropic import AsyncAnthropic; assert isinstance(AsyncAnthropic, type)"` exits 0

## Key Findings from SDK Introspection

These convert RESEARCH.md assumptions from LOW/ASSUMED to VERIFIED:

| Assumption | Resolved Shape | Status |
|------------|---------------|--------|
| A1: `client.messages.stream()` returns an async context manager | `AsyncMessageStreamManager` with `__aenter__`/`__aexit__` | VERIFIED |
| A2: `stream.get_final_message()` callable after async-for | On `AsyncMessageStream` (entered stream); NOT on the manager | VERIFIED |
| A3: SDK streaming delta event carries `event.delta.text` | `RawContentBlockDeltaEvent.delta` union -> `TextDelta.text` field | VERIFIED |
| Open Q1: exact attribute path for text delta | `event.delta.text` is correct; narrowed via `TextDelta.model_fields['text']` | CLOSED |

**Critical shape finding:** `get_final_message` is on `AsyncMessageStream` (the type yielded by `__aenter__`), not on `AsyncMessageStreamManager` (the pre-entry manager). `agent/loop.py` uses the correct pattern: `async with client.messages.stream(...) as stream: ... final_msg = await stream.get_final_message()`.

## Deviations from Plan

None. The plan specified exactly 7 test behaviors and all were implemented as described. No unexpected SDK shape mismatches found — the assumed API surface was correct.

## Known Stubs

None. The test file is complete and exercises real SDK types.

## Threat Surface Scan

No new network endpoints, auth paths, or schema changes introduced. Test file is offline-only.

| Threat ID | Mitigation | Status |
|-----------|------------|--------|
| T-02-14 | test_conftest_mock_matches_real_surface: every mock attribute name maps to real SDK field | Implemented |
| T-02-15 | Dummy key + no context-manager entry = zero live network requests; enforced by httpx patch | Implemented |
| T-02-16 | Future SDK upgrade that renames streaming surface will fail loudly at test_sdk_contract.py | Accepted (gate installed) |

## Self-Check: PASSED
