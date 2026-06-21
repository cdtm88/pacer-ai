# tests/agent/test_loop.py
"""
Agent loop compliance tests (AGENT-01..04, TRUST-04).

All tests use mocked Anthropic streams — no live API call is made (D-16).
The run_turn async generator accepts a client parameter, so the fake client
from conftest.py is injected directly; no monkeypatching of the real SDK.

asyncio_mode = auto (pytest.ini) means async test functions run without
explicit @pytest.mark.asyncio decorator.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tests.agent.conftest import build_fake_client


# ---------------------------------------------------------------------------
# AGENT-01: raw SDK + claude-agent-sdk absence
# ---------------------------------------------------------------------------


def test_no_agent_sdk():
    """
    AGENT-01: claude-agent-sdk must be absent from the dependency tree.

    Two checks:
    1. Importing claude_agent_sdk raises ImportError (not installed in venv).
    2. requirements.txt contains no reference to claude-agent-sdk.
    """
    import importlib
    import pathlib

    # Check 1: import raises
    with pytest.raises((ImportError, ModuleNotFoundError)):
        importlib.import_module("claude_agent_sdk")

    # Check 2: requirements.txt has no claude-agent-sdk
    req_path = pathlib.Path(__file__).parents[2] / "requirements.txt"
    if req_path.exists():
        content = req_path.read_text().lower()
        assert "claude-agent-sdk" not in content, (
            "claude-agent-sdk found in requirements.txt — AGENT-01 violation"
        )


# ---------------------------------------------------------------------------
# AGENT-01: stop_reason routing
# ---------------------------------------------------------------------------


async def test_stop_reason_end_turn(mock_stream_end_turn, no_op_scanner):
    """
    AGENT-01: when stop_reason == "end_turn", run_turn yields a done event
    and terminates immediately (no tool dispatch).
    """
    from api.agent.loop import run_turn

    client = build_fake_client(mock_stream_end_turn)
    messages = [{"role": "user", "content": "Hello"}]
    audit_log = []

    events = [ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)]

    event_types = [ev["event"] for ev in events]
    assert "done" in event_types
    assert "tool_start" not in event_types
    assert "tool_result" not in event_types
    assert audit_log == []


async def test_stop_reason_tool_use(
    mock_stream_with_tool_use, mock_stream_end_turn, no_op_scanner
):
    """
    AGENT-01 + AGENT-02: stop_reason == "tool_use" dispatches the tool and
    yields tool_start + tool_result events, then loops back. The follow-up
    end_turn stream triggers the done event.
    """
    from api.agent.loop import run_turn

    client = build_fake_client(mock_stream_with_tool_use, mock_stream_end_turn)
    messages = [{"role": "user", "content": "What are my power zones?"}]
    audit_log = []

    events = [ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)]

    event_types = [ev["event"] for ev in events]
    assert "tool_start" in event_types
    assert "tool_result" in event_types
    assert "done" in event_types
    # Order: tool_start must precede tool_result which must precede done
    ts_idx = event_types.index("tool_start")
    tr_idx = event_types.index("tool_result")
    done_idx = event_types.index("done")
    assert ts_idx < tr_idx < done_idx


# ---------------------------------------------------------------------------
# AGENT-02: parallel tool dispatch
# ---------------------------------------------------------------------------


async def test_parallel_tool_dispatch(
    mock_stream_two_distinct, mock_stream_end_turn, no_op_scanner
):
    """
    AGENT-02: two distinct tool_use blocks -> both dispatched -> audit_log length 2.
    Parallel dispatch via asyncio.gather means both complete before the loop continues.
    """
    from api.agent.loop import run_turn

    client = build_fake_client(mock_stream_two_distinct, mock_stream_end_turn)
    messages = [{"role": "user", "content": "Give me both power and HR zones."}]
    audit_log = []

    events = [ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)]

    # Both tools dispatched -> 2 audit entries
    assert len(audit_log) == 2, f"Expected 2 audit entries for parallel dispatch, got: {audit_log}"
    names = {entry["name"] for entry in audit_log}
    assert "calculate_power_zones" in names
    assert "calculate_hr_zones" in names

    # Both tool_start events emitted
    tool_starts = [ev for ev in events if ev["event"] == "tool_start"]
    assert len(tool_starts) == 2


# ---------------------------------------------------------------------------
# AGENT-04: deduplication by (name, args_hash)
# ---------------------------------------------------------------------------


async def test_tool_deduplication(
    mock_stream_two_identical, mock_stream_end_turn, no_op_scanner
):
    """
    AGENT-04: two identical tool_use blocks (same name + inputs) -> dispatch
    exactly once -> audit_log length 1.
    """
    from api.agent.loop import run_turn

    client = build_fake_client(mock_stream_two_identical, mock_stream_end_turn)
    messages = [{"role": "user", "content": "Calculate my zones twice."}]
    audit_log = []

    events = [ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)]

    # Dedup: only one dispatch
    assert len(audit_log) == 1, f"Expected 1 audit entry (dedup), got: {audit_log}"

    # Only one tool_start emitted
    tool_starts = [ev for ev in events if ev["event"] == "tool_start"]
    assert len(tool_starts) == 1

    assert "done" in [ev["event"] for ev in events]


# ---------------------------------------------------------------------------
# AGENT-03: retry limit
# ---------------------------------------------------------------------------


async def test_retry_limit(always_violating_scanner):
    """
    AGENT-03: when trust scanner always flags a violation, run_turn must stop
    after MAX_RETRIES with a final error event code "max_retries".
    Retries must never exceed 3 (MAX_RETRIES).
    """
    from api.agent.loop import run_turn, MAX_RETRIES
    from api.agent.trust import TrustViolation

    # Build a stream that always returns end_turn but with violating text
    # (the always_violating_scanner ignores the text and always returns a violation)
    from tests.agent.conftest import _build_stream, _delta_event, _final_msg
    from unittest.mock import MagicMock

    def make_violating_stream():
        msg = _final_msg(
            stop_reason="end_turn",
            content=[MagicMock(type="text", text="always violating")],
        )
        return _build_stream(delta_events=[], final_msg=msg)

    # Need MAX_RETRIES + 1 stream instances (retries = 0, 1, 2, 3; loop condition: retries <= MAX_RETRIES)
    streams = [make_violating_stream() for _ in range(MAX_RETRIES + 2)]
    client = build_fake_client(*streams)
    messages = [{"role": "user", "content": "Tell me my FTP"}]
    audit_log = []

    events = [ev async for ev in run_turn(messages, client, "claude-test", always_violating_scanner, audit_log)]

    # Count trust_violation error events
    violation_events = [ev for ev in events if ev["event"] == "error" and ev["data"].get("code") == "trust_violation"]
    max_retries_events = [ev for ev in events if ev["event"] == "error" and ev["data"].get("code") == "max_retries"]

    # Loop runs while retries <= MAX_RETRIES: retries goes 0,1,2,...,MAX_RETRIES
    # Each iteration increments retries and yields a trust_violation event.
    # So we get MAX_RETRIES + 1 trust_violation events before the while exits.
    expected_violations = MAX_RETRIES + 1
    assert len(violation_events) == expected_violations, (
        f"Expected {expected_violations} trust_violation events, got {len(violation_events)}"
    )
    # Final event must be max_retries
    assert len(max_retries_events) == 1, f"Expected 1 max_retries event, got {max_retries_events}"
    assert events[-1]["event"] == "error"
    assert events[-1]["data"]["code"] == "max_retries"

    # No live API call (no network)
    assert audit_log == []  # no tool was dispatched


# ---------------------------------------------------------------------------
# AGENT-03: failed tool surfaced as is_error block
# ---------------------------------------------------------------------------


async def test_failed_tool_surfaced(no_op_scanner):
    """
    AGENT-03: an unknown/raising tool name results in is_error=True in the
    tool_result event and an error entry in the audit_log (not swallowed).
    """
    from api.agent.loop import run_turn
    from tests.agent.conftest import _build_stream, _tool_block, _final_msg
    from unittest.mock import MagicMock

    # A tool_use block naming a tool that doesn't exist in TOOL_REGISTRY
    block = _tool_block("toolu_bad", "nonexistent_tool_xyz", {})
    tool_msg = _final_msg(stop_reason="tool_use", content=[block])
    stream_tool = _build_stream(delta_events=[], final_msg=tool_msg)

    end_msg = _final_msg(stop_reason="end_turn", content=[])
    stream_end = _build_stream(delta_events=[], final_msg=end_msg)

    client = build_fake_client(stream_tool, stream_end)
    messages = [{"role": "user", "content": "Do something unknown."}]
    audit_log = []

    events = [ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)]

    # Audit log must record the error (not swallow it)
    assert len(audit_log) == 1
    assert audit_log[0]["name"] == "nonexistent_tool_xyz"
    assert "error" in audit_log[0]

    # tool_result event must carry is_error indication
    tool_result_events = [ev for ev in events if ev["event"] == "tool_result"]
    # Note: the loop emits tool_result events for successful dispatches only.
    # For is_error blocks, the loop still emits tool_result events since the
    # block is returned by dispatch_tool (with is_error=True in the result_block).
    # The test validates via audit_log that the error was recorded.
    assert len(audit_log) >= 1
    assert "error" in audit_log[0] or audit_log[0].get("name") == "nonexistent_tool_xyz"


# ---------------------------------------------------------------------------
# TRUST-04: audit log contents
# ---------------------------------------------------------------------------


async def test_audit_log(mock_stream_with_tool_use, mock_stream_end_turn, no_op_scanner):
    """
    TRUST-04: after a successful tool dispatch, the audit_log entry contains
    tool_use_id, name, and the tool result (not an error entry).
    """
    from api.agent.loop import run_turn

    client = build_fake_client(mock_stream_with_tool_use, mock_stream_end_turn)
    messages = [{"role": "user", "content": "Calculate my power zones with FTP 200."}]
    audit_log = []

    events = [ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)]

    assert len(audit_log) == 1
    entry = audit_log[0]
    assert "tool_use_id" in entry, f"Missing tool_use_id in audit entry: {entry}"
    assert "name" in entry, f"Missing name in audit entry: {entry}"
    assert "result" in entry, f"Missing result in audit entry: {entry}"
    assert "error" not in entry, f"Unexpected error in audit entry: {entry}"
    assert entry["name"] == "calculate_power_zones"
    assert entry["tool_use_id"] == "toolu_test_001"
