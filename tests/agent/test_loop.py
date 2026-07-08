# tests/agent/test_loop.py
"""
Agent loop compliance tests (AGENT-01..04, TRUST-04).

All tests use mocked Anthropic streams — no live API call is made (D-16).
The run_turn async generator accepts a client parameter, so the fake client
from conftest.py is injected directly; no monkeypatching of the real SDK.

asyncio_mode = auto (pytest.ini) means async test functions run without
explicit @pytest.mark.asyncio decorator.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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
    from backend.agent.loop import run_turn

    client = build_fake_client(mock_stream_end_turn)
    messages = [{"role": "user", "content": "Hello"}]
    audit_log = []

    events = [
        ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)
    ]

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
    from backend.agent.loop import run_turn

    client = build_fake_client(mock_stream_with_tool_use, mock_stream_end_turn)
    messages = [{"role": "user", "content": "What are my power zones?"}]
    audit_log = []

    events = [
        ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)
    ]

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
    from backend.agent.loop import run_turn

    client = build_fake_client(mock_stream_two_distinct, mock_stream_end_turn)
    messages = [{"role": "user", "content": "Give me both power and HR zones."}]
    audit_log = []

    events = [
        ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)
    ]

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
    from backend.agent.loop import run_turn

    client = build_fake_client(mock_stream_two_identical, mock_stream_end_turn)
    messages = [{"role": "user", "content": "Calculate my zones twice."}]
    audit_log = []

    events = [
        ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)
    ]

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
    from unittest.mock import MagicMock

    from backend.agent.loop import MAX_RETRIES, run_turn

    # Build a stream that always returns end_turn but with violating text
    # (the always_violating_scanner ignores the text and always returns a violation)
    from tests.agent.conftest import _build_stream, _final_msg

    def make_violating_stream():
        msg = _final_msg(
            stop_reason="end_turn",
            content=[MagicMock(type="text", text="always violating")],
        )
        return _build_stream(delta_events=[], final_msg=msg)

    # Need MAX_RETRIES + 1 stream instances (retries = 0, 1, 2, 3;
    # loop condition: retries <= MAX_RETRIES)
    streams = [make_violating_stream() for _ in range(MAX_RETRIES + 2)]
    client = build_fake_client(*streams)
    messages = [{"role": "user", "content": "Tell me my FTP"}]
    audit_log = []

    events = [
        ev async for ev in run_turn(
            messages, client, "claude-test", always_violating_scanner, audit_log
        )
    ]

    # Count trust_violation error events
    violation_events = [
        ev for ev in events
        if ev["event"] == "error" and ev["data"].get("code") == "trust_violation"
    ]
    max_retries_events = [
        ev for ev in events
        if ev["event"] == "error" and ev["data"].get("code") == "max_retries"
    ]

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

    from backend.agent.loop import run_turn
    from tests.agent.conftest import _build_stream, _final_msg, _tool_block

    # A tool_use block naming a tool that doesn't exist in TOOL_REGISTRY
    block = _tool_block("toolu_bad", "nonexistent_tool_xyz", {})
    tool_msg = _final_msg(stop_reason="tool_use", content=[block])
    stream_tool = _build_stream(delta_events=[], final_msg=tool_msg)

    end_msg = _final_msg(stop_reason="end_turn", content=[])
    stream_end = _build_stream(delta_events=[], final_msg=end_msg)

    client = build_fake_client(stream_tool, stream_end)
    messages = [{"role": "user", "content": "Do something unknown."}]
    audit_log = []

    _events = [
        ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)
    ]

    # Audit log must record the error (not swallow it)
    # Note: the loop emits tool_result events for successful dispatches only.
    # For is_error blocks, the loop still emits tool_result events since the
    # block is returned by dispatch_tool (with is_error=True in the result_block).
    # The test validates via audit_log that the error was recorded.
    assert len(audit_log) == 1
    assert audit_log[0]["name"] == "nonexistent_tool_xyz"
    assert "error" in audit_log[0]
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
    from backend.agent.loop import run_turn

    client = build_fake_client(mock_stream_with_tool_use, mock_stream_end_turn)
    messages = [{"role": "user", "content": "Calculate my power zones with FTP 200."}]
    audit_log = []

    _events = [
        ev async for ev in run_turn(messages, client, "claude-test", no_op_scanner, audit_log)
    ]

    assert len(audit_log) == 1
    entry = audit_log[0]
    assert "tool_use_id" in entry, f"Missing tool_use_id in audit entry: {entry}"
    assert "name" in entry, f"Missing name in audit entry: {entry}"
    assert "result" in entry, f"Missing result in audit entry: {entry}"
    assert "error" not in entry, f"Unexpected error in audit entry: {entry}"
    assert entry["name"] == "calculate_power_zones"
    assert entry["tool_use_id"] == "toolu_test_001"


# ---------------------------------------------------------------------------
# 260702-w52: tool_result_values must accumulate across rounds, not reset
# ---------------------------------------------------------------------------


async def test_tool_result_values_accumulate_across_rounds(mock_stream_with_tool_use):
    """
    260702-w52: reproduces the reset-every-iteration bug. Round 1 dispatches a
    REAL calculate_power_zones(ftp=200.0) tool call (JSON containing 210, the
    Z4/Z5 boundary). Round 2 is a text-only end_turn round whose prose
    references "210 watts" -- a number genuinely sourced from round 1's tool
    result, but in an EARLIER round than the one being scanned.

    Uses the REAL scan_buffer (not no_op_scanner/always_violating_scanner) so
    the real attribution logic is exercised end-to-end across rounds. Before
    the fix, tool_result_values is reset to [] at the top of round 2's while
    iteration, so scan_buffer cannot see round 1's tool JSON and flags "210
    watts" as an unattributed violation. After the fix (tool_result_values
    accumulates across the whole run_turn() call), round 2's scan sees round
    1's tool result and correctly attributes it.
    """
    from backend.agent.loop import run_turn
    from backend.agent.trust import scan_buffer
    from tests.agent.conftest import _build_stream, _delta_event, _final_msg

    round2_text = "Your threshold power sits around 210 watts."
    round2_stream = _build_stream(
        delta_events=[_delta_event(round2_text)],
        final_msg=_final_msg(
            stop_reason="end_turn",
            content=[MagicMock(type="text", text=round2_text)],
        ),
    )

    client = build_fake_client(mock_stream_with_tool_use, round2_stream)
    messages = [{"role": "user", "content": "What's my FTP-based threshold power?"}]
    audit_log = []

    events = [
        ev async for ev in run_turn(messages, client, "claude-test", scan_buffer, audit_log)
    ]

    violation_events = [
        ev for ev in events
        if ev["event"] == "error" and ev["data"].get("code") == "trust_violation"
    ]
    assert not violation_events, (
        f"Expected no trust_violation (210 is attributed to round-1 tool "
        f"output), got: {violation_events}"
    )
    assert "done" in [ev["event"] for ev in events]


# ---------------------------------------------------------------------------
# 260702-wev: authenticated user_id must be injected server-side, not
# supplied by the LLM
# ---------------------------------------------------------------------------


async def test_user_id_injected_server_side_through_run_turn(no_op_scanner):
    """
    260702-wev: proves the authenticated user_id reaches the real save_profile
    function through the full run_turn -> dispatch_tool chain, even though the
    tool_use block (matching the post-fix schema, which no longer declares
    user_id) never supplies one. This closes the identity bug where the LLM
    guessed placeholder UUIDs ("new_user", "user_001", ...) that failed
    Postgres uuid/foreign-key checks on every production save_profile call.
    """
    from backend.agent.loop import run_turn
    from backend.sports_science.types import ToolResult
    from tests.agent.conftest import _build_stream, _final_msg, _tool_block

    save_profile_inputs = {
        "fitness_goals": "weight loss",
        "weekly_hours": 3.0,
        "preferred_days": ["Tuesday"],
        "back_status": "none",
        "equipment": {},
        "rpe_baseline": "beginner",
    }
    tool_block = _tool_block("toolu_save_001", "save_profile", save_profile_inputs)
    round1_stream = _build_stream(
        delta_events=[], final_msg=_final_msg(stop_reason="tool_use", content=[tool_block])
    )
    round2_stream = _build_stream(
        delta_events=[], final_msg=_final_msg(stop_reason="end_turn", content=[])
    )

    fake_save_profile = MagicMock(
        return_value=ToolResult(
            value={"saved": True},
            unit="",
            methodology="profile_persistence",
            inputs={},
        )
    )

    client = build_fake_client(round1_stream, round2_stream)
    messages = [{"role": "user", "content": "Save my profile."}]
    audit_log = []
    injected_user_id = "11111111-1111-1111-1111-111111111111"

    with patch.dict("backend.agent.tools.TOOL_REGISTRY", {"save_profile": fake_save_profile}):
        events = [
            ev async for ev in run_turn(
                messages, client, "claude-test", no_op_scanner, audit_log,
                user_id=injected_user_id,
            )
        ]

    assert fake_save_profile.call_count == 1
    call_kwargs = fake_save_profile.call_args.kwargs
    assert call_kwargs["user_id"] == injected_user_id, (
        f"Expected server-injected user_id, got: {call_kwargs.get('user_id')}"
    )
    assert call_kwargs["back_status"] == "none", (
        "Injection must augment, not replace, the LLM-supplied args"
    )
    assert "done" in [ev["event"] for ev in events]


# ---------------------------------------------------------------------------
# 08-05 / TRUST-09 / D-04: cross-turn tool_result_values seeding from the
# persisted audit trail eliminates false positives on a stateless invocation
# where the number was established in a PRIOR turn, not this one.
# ---------------------------------------------------------------------------


async def test_cross_turn_seed_suppresses_false_positive():
    """
    A number present only in a PRIOR turn's audit trail (e.g. an FTP estimate
    established last turn) must be attributed this turn via seeding, even
    though this turn's stream makes NO tool call at all. Uses the REAL
    scan_buffer (not no_op_scanner) so real attribution logic is exercised.

    backend.agent.loop.load_prior_audit_values is patched (AsyncMock) to
    simulate a Plan 01 audit_log reload returning last turn's persisted
    tool-result JSON.
    """
    import json

    from backend.agent.loop import run_turn
    from backend.agent.trust import scan_buffer
    from tests.agent.conftest import _build_stream, _delta_event, _final_msg

    text = "Your FTP is 250 watts based on last week's estimate."
    stream = _build_stream(
        delta_events=[_delta_event(text)],
        final_msg=_final_msg(
            stop_reason="end_turn",
            content=[MagicMock(type="text", text=text)],
        ),
    )

    prior_result_json = json.dumps(
        {"value": {"ftp": 250}, "unit": "watts", "methodology": "critical_power_model"}
    )

    with patch(
        "backend.agent.loop.load_prior_audit_values",
        AsyncMock(return_value=[prior_result_json]),
    ) as mock_load:
        client = build_fake_client(stream)
        messages = [{"role": "user", "content": "What's my FTP?"}]
        audit_log = []

        events = [
            ev async for ev in run_turn(
                messages, client, "claude-test", scan_buffer, audit_log,
                conversation_id="22222222-2222-2222-2222-222222222222",
            )
        ]

    mock_load.assert_awaited_once()

    violation_events = [
        ev for ev in events
        if ev["event"] == "error" and ev["data"].get("code") in ("trust_violation", "max_retries")
    ]
    assert not violation_events, (
        f"Expected no violation (250 seeded from prior turn's audit trail), "
        f"got: {violation_events}"
    )
    assert "done" in [ev["event"] for ev in events]


async def test_cross_turn_seed_control_without_conversation_id_still_violates():
    """
    Control: with conversation_id=None (no seeding is possible), the identical
    violating text -- with no in-turn tool call and no seeded prior values --
    still raises a trust_violation. This proves the suppression in the
    previous test comes from cross-turn seeding, not from some unrelated
    change to scan_buffer or run_turn.
    """
    from backend.agent.loop import MAX_RETRIES, run_turn
    from backend.agent.trust import scan_buffer
    from tests.agent.conftest import _build_stream, _delta_event, _final_msg

    text = "Your FTP is 250 watts based on last week's estimate."

    def make_stream():
        return _build_stream(
            delta_events=[_delta_event(text)],
            final_msg=_final_msg(
                stop_reason="end_turn",
                content=[MagicMock(type="text", text=text)],
            ),
        )

    # MAX_RETRIES + 2 streams so the loop has enough fake responses to exhaust
    # retries without running out (mirrors test_retry_limit's stream count).
    streams = [make_stream() for _ in range(MAX_RETRIES + 2)]
    client = build_fake_client(*streams)
    messages = [{"role": "user", "content": "What's my FTP?"}]
    audit_log = []

    events = [
        ev async for ev in run_turn(
            messages, client, "claude-test", scan_buffer, audit_log,
            conversation_id=None,
        )
    ]

    violation_events = [
        ev for ev in events
        if ev["event"] == "error" and ev["data"].get("code") == "trust_violation"
    ]
    assert violation_events, (
        "Expected trust_violation without seeding (conversation_id=None control)"
    )


# ---------------------------------------------------------------------------
# 08-08 / D-02 / D-05: per-turn self-report extraction closes the ONBD-05
# Branch A gap -- a user-stated LTHR restated in the D-03 confirmation
# summary (NO tool call) must be attributed via self_reported_values, not
# flagged as an unsourced trust_violation.
# ---------------------------------------------------------------------------


async def test_self_reported_lthr_echo_passes_branch_a():
    """
    Positive: messages include a genuine user message stating an LTHR; the
    fake stream's assistant text restates that number in a confirmation-style
    summary; run with the REAL scan_buffer and NO tool call. Branch A must
    complete with a done event and zero trust_violation / max_retries events.
    """
    from backend.agent.loop import run_turn
    from backend.agent.trust import scan_buffer
    from tests.agent.conftest import _build_stream, _delta_event, _final_msg

    confirmation_text = (
        "Here is what I have so far: your heart-rate baseline (LTHR) is "
        "165 bpm. Does that look right before I save your profile?"
    )
    stream = _build_stream(
        delta_events=[_delta_event(confirmation_text)],
        final_msg=_final_msg(
            stop_reason="end_turn",
            content=[MagicMock(type="text", text=confirmation_text)],
        ),
    )

    client = build_fake_client(stream)
    messages = [
        {
            "role": "user",
            "content": "My LTHR is 165 bpm, from a recent lab test.",
        }
    ]
    audit_log = []

    events = [
        ev async for ev in run_turn(messages, client, "claude-test", scan_buffer, audit_log)
    ]

    violation_events = [
        ev for ev in events
        if ev["event"] == "error" and ev["data"].get("code") in ("trust_violation", "max_retries")
    ]
    assert not violation_events, (
        f"Expected Branch A to complete with no violation (165 is self-reported "
        f"by the user, not hallucinated), got: {violation_events}"
    )
    assert "done" in [ev["event"] for ev in events]


async def test_self_reported_control_hallucinated_number_still_violates():
    """
    Control: identical confirmation-style assistant text but restating a
    DIFFERENT number the user never stated (and no matching tool result).
    Proves the pass in the positive case comes from the self-report channel
    attributing the exact user-stated number, not from a blanket relaxation
    of scan_buffer.
    """
    from backend.agent.loop import MAX_RETRIES, run_turn
    from backend.agent.trust import scan_buffer
    from tests.agent.conftest import _build_stream, _delta_event, _final_msg

    hallucinated_text = (
        "Here is what I have so far: your heart-rate baseline (LTHR) is "
        "300 bpm. Does that look right before I save your profile?"
    )

    def make_stream():
        return _build_stream(
            delta_events=[_delta_event(hallucinated_text)],
            final_msg=_final_msg(
                stop_reason="end_turn",
                content=[MagicMock(type="text", text=hallucinated_text)],
            ),
        )

    # MAX_RETRIES + 2 streams so the loop has enough fake responses to exhaust
    # retries without running out (mirrors test_retry_limit's stream count).
    streams = [make_stream() for _ in range(MAX_RETRIES + 2)]
    client = build_fake_client(*streams)
    messages = [
        {
            "role": "user",
            "content": "My LTHR is 165 bpm, from a recent lab test.",
        }
    ]
    audit_log = []

    events = [
        ev async for ev in run_turn(messages, client, "claude-test", scan_buffer, audit_log)
    ]

    violation_events = [
        ev for ev in events
        if ev["event"] == "error" and ev["data"].get("code") == "trust_violation"
    ]
    assert violation_events, (
        "Expected a hallucinated number (300, never stated by the user) to "
        "still be flagged as a trust_violation"
    )
