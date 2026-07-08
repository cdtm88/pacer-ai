# tests/agent/conftest.py
"""
Mock Anthropic stream fixtures for agent compliance tests (AGENT-06, D-15, D-16).

All fixtures produce AsyncMock objects implementing the async context manager
protocol (__aenter__/__aexit__) and async iteration (__aiter__), mimicking the
shape of anthropic.AsyncAnthropic.messages.stream().

Fixture inventory:
  mock_stream_text_only       - stop_reason="end_turn", no tool use, no deltas
  mock_stream_with_tool_use   - stop_reason="tool_use", one calculate_power_zones block
  mock_stream_trust_violation - stop_reason="end_turn", text delta with unsourced number
  mock_stream_two_distinct    - stop_reason="tool_use", two different tool_use blocks (AGENT-02)
  mock_stream_two_identical   - stop_reason="tool_use", two identical tool_use blocks (AGENT-04)
  mock_stream_end_turn        - alias for text_only; explicit end_turn with no deltas
  fake_client                 - helper fixture returning a fake AsyncAnthropic client
                                whose messages.stream() returns a given stream fixture

All fixtures avoid any network call (D-16).
"""

from unittest.mock import MagicMock

import pytest

import backend.rate_limit as rate_limit_module


@pytest.fixture(autouse=True)
def _reset_rate_limit_log():
    """WR-01 (10-REVIEW.md): reset the rate-limit module's request log between
    tests so exhausting the budget in one test doesn't bleed into another.
    test_sse.py's TestSSEEventSequence drives /chat/stream with the same
    TEST_USER_ID (via auth_headers()) across many tests; without this reset,
    correctness would depend on collection order and sibling test files'
    teardown running first, rather than being self-contained."""
    rate_limit_module._request_log.clear()
    yield
    rate_limit_module._request_log.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _MockStream:
    """
    Minimal async context manager + async iterator for mocking
    anthropic.AsyncAnthropic.messages.stream().

    Supports:
      async with client.messages.stream(...) as stream:
          async for event in stream:
              ...
          final_msg = await stream.get_final_message()
    """

    def __init__(self, delta_events: list, final_msg: MagicMock):
        self._events = list(delta_events)
        self._final_msg = final_msg

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def __aiter__(self):
        return self._async_gen()

    async def _async_gen(self):
        for ev in self._events:
            yield ev

    async def get_final_message(self):
        return self._final_msg


def _build_stream(delta_events: list, final_msg: MagicMock) -> "_MockStream":
    """
    Build a mock stream that implements the async context manager protocol
    and async iteration, mimicking anthropic.AsyncAnthropic.messages.stream().
    """
    return _MockStream(delta_events=delta_events, final_msg=final_msg)


def _delta_event(text: str) -> MagicMock:
    """Build a content_block_delta event carrying a text delta."""
    event = MagicMock()
    event.type = "content_block_delta"
    event.delta = MagicMock()
    event.delta.text = text
    return event


def _tool_block(tool_use_id: str, name: str, inputs: dict) -> MagicMock:
    """Build a tool_use content block as returned in final_msg.content."""
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_use_id
    block.name = name
    block.input = inputs
    return block


def _final_msg(stop_reason: str, content: list) -> MagicMock:
    """Build a final message mock with stop_reason and content."""
    msg = MagicMock()
    msg.stop_reason = stop_reason
    msg.content = content
    return msg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_stream_text_only():
    """
    Simulates a Claude response with only text (no tool use).
    stop_reason = "end_turn", no delta events, no tool blocks.
    """
    msg = _final_msg(
        stop_reason="end_turn",
        content=[MagicMock(type="text", text="Great workout today!")],
    )
    return _build_stream(delta_events=[], final_msg=msg)


@pytest.fixture
def mock_stream_end_turn():
    """
    Alias for mock_stream_text_only. Explicit end_turn with no deltas.
    Used by test_stop_reason tests for the end_turn branch.
    """
    msg = _final_msg(
        stop_reason="end_turn",
        content=[MagicMock(type="text", text="End turn response.")],
    )
    return _build_stream(delta_events=[], final_msg=msg)


@pytest.fixture
def mock_stream_with_tool_use():
    """
    Simulates a tool_use response for calculate_power_zones with ftp=200.
    stop_reason = "tool_use", one calculate_power_zones block.
    After dispatching the tool, a follow-up end_turn message is expected
    (the loop will call messages.stream() again; the fake_client fixture
    handles cycling to a text-only stream for the second call).
    """
    tool_block = _tool_block(
        tool_use_id="toolu_test_001",
        name="calculate_power_zones",
        inputs={"ftp": 200.0},
    )
    msg = _final_msg(stop_reason="tool_use", content=[tool_block])
    return _build_stream(delta_events=[], final_msg=msg)


@pytest.fixture
def mock_stream_trust_violation():
    """
    Simulates an assistant response with an unsourced physiological number.
    stop_reason = "end_turn" but text delta carries "Your FTP is 250 watts..."
    which PHYSIO_PATTERN_A will flag as a violation.
    """
    delta = _delta_event("Your FTP is 250 watts based on your history.")
    msg = _final_msg(
        stop_reason="end_turn",
        content=[MagicMock(type="text", text="Your FTP is 250 watts based on your history.")],
    )
    return _build_stream(delta_events=[delta], final_msg=msg)


@pytest.fixture
def mock_stream_two_distinct():
    """
    Two DISTINCT tool_use blocks (AGENT-02 / parallel dispatch test).
    stop_reason = "tool_use", two different tool names + distinct inputs.
    Tools: calculate_power_zones(ftp=200) and calculate_hr_zones(max_hr_or_lthr=160).
    """
    block_a = _tool_block("toolu_001", "calculate_power_zones", {"ftp": 200.0})
    block_b = _tool_block("toolu_002", "calculate_hr_zones", {"max_hr_or_lthr": 160.0})
    msg = _final_msg(stop_reason="tool_use", content=[block_a, block_b])
    return _build_stream(delta_events=[], final_msg=msg)


@pytest.fixture
def mock_stream_two_identical():
    """
    Two IDENTICAL tool_use blocks (AGENT-04 / deduplication test).
    Same name and inputs; dedup by (name, args_hash) should reduce to one dispatch.
    """
    block_a = _tool_block("toolu_001", "calculate_power_zones", {"ftp": 200.0})
    block_b = _tool_block("toolu_002", "calculate_power_zones", {"ftp": 200.0})
    msg = _final_msg(stop_reason="tool_use", content=[block_a, block_b])
    return _build_stream(delta_events=[], final_msg=msg)


# ---------------------------------------------------------------------------
# Fake client helper
# ---------------------------------------------------------------------------


def build_fake_client(*streams):
    """
    Return a fake AsyncAnthropic-shaped client whose messages.stream()
    returns streams in sequence (first call returns streams[0], second returns
    streams[1], etc.).

    Usage:
        client = build_fake_client(mock_stream_tool_use, mock_stream_end_turn)
        events = [ev async for ev in run_turn(messages, client, model, scanner, [])]

    The stream context manager is handled by the stream fixtures themselves
    (they implement __aenter__ / __aexit__).
    """
    stream_queue = list(streams)
    call_count = [0]

    def _stream_side_effect(**kwargs):
        idx = call_count[0]
        call_count[0] += 1
        if idx < len(stream_queue):
            return stream_queue[idx]
        # If more calls than provided streams, repeat the last one
        return stream_queue[-1]

    fake_messages = MagicMock()
    fake_messages.stream = MagicMock(side_effect=_stream_side_effect)

    fake_client = MagicMock()
    fake_client.messages = fake_messages
    return fake_client


@pytest.fixture
def no_op_scanner():
    """A trust scanner that never returns a violation (for non-trust tests)."""
    def _scanner(text, tool_result_values, self_reported_values=None):
        return None
    return _scanner


@pytest.fixture
def always_violating_scanner():
    """A trust scanner that always returns a TrustViolation (for retry-cap tests)."""
    from backend.agent.trust import TrustViolation

    def _scanner(text, tool_result_values, self_reported_values=None):
        return TrustViolation(
            matched_text="250 watts",
            pattern="test",
        )
    return _scanner
