# tests/agent/test_sse.py
"""
SSE event-sequence compliance tests (AGENT-05, AGENT-06).

Drives the FastAPI app at GET /chat/stream via httpx.AsyncClient with
ASGITransport -- no real server is started and no live Anthropic API
call is made (D-16).

The loop/client used by api/routes/chat.py is patched so a deterministic
mock run_turn drives the response, yielding a known event sequence:
  token ... tool_start tool_result done

Tests assert:
  - Content-Type: text/event-stream
  - Frame format: "event: <type>\\ndata: <json>\\n\\n"
  - Event ordering: token events appear before tool_start, tool_result, done
  - No live Anthropic API call

asyncio_mode = auto (pytest.ini) means async tests need no @mark.asyncio.
"""

import json
import pytest
import httpx
from httpx import ASGITransport

from tests.api.conftest import TEST_JWT_SECRET, TEST_USER_ID, auth_headers


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def parse_sse_frames(body: str) -> list[dict]:
    """
    Parse a raw SSE body string into a list of frame dicts.

    Each frame is a pair of lines:
      event: <type>
      data: <json>
    Followed by a blank line.

    Returns list of {"event": str, "data": dict} per frame.
    Skips blank lines and comment lines (starting with ':').
    """
    frames = []
    current: dict = {}
    for line in body.splitlines():
        line = line.rstrip("\r")
        if not line:
            # Blank line: end of frame
            if "event" in current and "data" in current:
                frames.append(current)
            current = {}
            continue
        if line.startswith(":"):
            # SSE comment / keepalive — ignore
            continue
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            try:
                current["data"] = json.loads(data_str)
            except json.JSONDecodeError:
                current["data"] = data_str
    # Flush any trailing frame without final blank line
    if "event" in current and "data" in current:
        frames.append(current)
    return frames


# ---------------------------------------------------------------------------
# Mock run_turn: deterministic event sequence for SSE tests
# ---------------------------------------------------------------------------


async def _mock_run_turn_text_only(messages, client, model, trust_scanner, audit_log, **kwargs):
    """
    Deterministic mock of run_turn for SSE sequence tests.
    Yields: token, done (text-only turn, no tool use).

    Accepts **kwargs because sse_generator (backend/routes/_sse.py) always
    forwards user_id/conversation_id kwargs for a resolved conversation.
    """
    yield {"event": "token", "data": {"text": "Hello, "}}
    yield {"event": "token", "data": {"text": "let me help you."}}
    yield {"event": "done", "data": {}}


async def _mock_run_turn_with_tools(messages, client, model, trust_scanner, audit_log, **kwargs):
    """
    Deterministic mock of run_turn with tool dispatch.
    Yields: token, tool_start, tool_result, done (in order).

    Accepts **kwargs because sse_generator (backend/routes/_sse.py) always
    forwards user_id/conversation_id kwargs for a resolved conversation.
    """
    yield {"event": "token", "data": {"text": "Calculating your zones."}}
    yield {"event": "tool_start", "data": {"name": "calculate_power_zones", "tool_use_id": "toolu_test_001"}}
    yield {"event": "tool_result", "data": {
        "tool_use_id": "toolu_test_001",
        "name": "calculate_power_zones",
        "value": "{\"zone_1\": {\"min\": 0, \"max\": 114}}",
    }}
    yield {"event": "done", "data": {}}


async def _mock_run_turn_token_then_error(messages, client, model, trust_scanner, audit_log, **kwargs):
    """
    WR-06: deterministic mock of run_turn terminating on an error event after
    one token. Mirrors run_turn's max_tool_turns/unexpected_stop/max_retries
    paths -- each yields `event: error` and then returns normally (a normal
    generator exit, NOT a raised exception).

    Accepts **kwargs because sse_generator (backend/routes/_sse.py) always
    forwards user_id/conversation_id kwargs for a resolved conversation.
    """
    yield {"event": "token", "data": {"text": "partial reply before failure"}}
    yield {"event": "error", "data": {"code": "unexpected_stop", "message": "boom"}}


async def _mock_run_turn_token_then_done(messages, client, model, trust_scanner, audit_log, **kwargs):
    """
    WR-06: deterministic mock of run_turn completing normally after one token.

    Accepts **kwargs because sse_generator (backend/routes/_sse.py) always
    forwards user_id/conversation_id kwargs for a resolved conversation.
    """
    yield {"event": "token", "data": {"text": "complete reply"}}
    yield {"event": "done", "data": {}}


async def _bypass_resolve(user_id, conversation_id):
    """
    Test-only bypass for CR-03's conversation-ownership check.

    These tests exercise SSE framing mechanics, not conversation ownership
    (ownership is already covered by tests/api/test_chat.py's CR-03-specific
    tests). Returns conversation_id unchanged so the placeholder
    "test-001"-style ids used throughout this file resolve successfully.
    """
    return conversation_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSSEEventSequence:
    """AGENT-05: SSE endpoint event-sequence compliance."""

    async def test_sse_content_type(self, monkeypatch):
        """
        AGENT-05: GET /chat/stream returns Content-Type: text/event-stream.
        """
        from backend.main import app
        import backend.routes.chat as chat_module

        monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
        monkeypatch.setattr(chat_module, "run_turn", _mock_run_turn_text_only)
        monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/chat/stream",
                params={"conversation_id": "test-001", "user_id": "test-user-001"},
                headers=auth_headers(),
            )

        assert response.status_code == 200
        content_type = response.headers.get("content-type", "")
        assert "text/event-stream" in content_type, (
            f"Expected text/event-stream, got: {content_type}"
        )

    async def test_sse_frame_format(self, monkeypatch):
        """
        AGENT-05: SSE frames are well-formed: event: <type>\\ndata: <json>\\n\\n
        """
        from backend.main import app
        import backend.routes.chat as chat_module

        monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
        monkeypatch.setattr(chat_module, "run_turn", _mock_run_turn_text_only)
        monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/chat/stream",
                params={"conversation_id": "test-001", "user_id": "test-user-001"},
                headers=auth_headers(),
            )

        body = response.text
        # Each frame must be terminated by a blank line
        # Check raw body contains double-newlines separating frames
        assert "\n\n" in body, "SSE body must contain frame separators (blank lines)"

        frames = parse_sse_frames(body)
        assert len(frames) > 0, "No SSE frames parsed from response body"

        for frame in frames:
            assert "event" in frame, f"Frame missing 'event' field: {frame}"
            assert "data" in frame, f"Frame missing 'data' field: {frame}"
            assert frame["event"] in ("token", "tool_start", "tool_result", "done", "error"), (
                f"Unknown event type: {frame['event']}"
            )

    async def test_sse_event_ordering_text_only(self, monkeypatch):
        """
        AGENT-05: text-only turn yields token events then done -- in order.
        """
        from backend.main import app
        import backend.routes.chat as chat_module

        monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
        monkeypatch.setattr(chat_module, "run_turn", _mock_run_turn_text_only)
        monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/chat/stream",
                params={"conversation_id": "test-001", "user_id": "test-user-001"},
                headers=auth_headers(),
            )

        frames = parse_sse_frames(response.text)
        event_types = [f["event"] for f in frames]

        assert "done" in event_types, f"No done event in: {event_types}"
        assert event_types[-1] == "done", f"done must be the last event, got: {event_types}"
        # All token events come before done
        if "token" in event_types:
            done_idx = event_types.index("done")
            token_indices = [i for i, t in enumerate(event_types) if t == "token"]
            assert all(i < done_idx for i in token_indices), (
                f"Token events must precede done: {event_types}"
            )

    async def test_sse_event_ordering_with_tools(self, monkeypatch):
        """
        AGENT-05: turn with tool use yields events in order:
        token..., tool_start, tool_result, done
        """
        from backend.main import app
        import backend.routes.chat as chat_module

        monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
        monkeypatch.setattr(chat_module, "run_turn", _mock_run_turn_with_tools)
        monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/chat/stream",
                params={"conversation_id": "test-001", "user_id": "test-user-001"},
                headers=auth_headers(),
            )

        frames = parse_sse_frames(response.text)
        event_types = [f["event"] for f in frames]

        assert "token" in event_types, f"Expected token events, got: {event_types}"
        assert "tool_start" in event_types, f"Expected tool_start event, got: {event_types}"
        assert "tool_result" in event_types, f"Expected tool_result event, got: {event_types}"
        assert "done" in event_types, f"Expected done event, got: {event_types}"

        # Ordering: token < tool_start < tool_result < done
        token_idx = event_types.index("token")
        ts_idx = event_types.index("tool_start")
        tr_idx = event_types.index("tool_result")
        done_idx = event_types.index("done")
        assert token_idx < ts_idx, f"token must precede tool_start: {event_types}"
        assert ts_idx < tr_idx, f"tool_start must precede tool_result: {event_types}"
        assert tr_idx < done_idx, f"tool_result must precede done: {event_types}"

    async def test_sse_token_data_has_text_field(self, monkeypatch):
        """Token events carry a 'text' field in their data payload."""
        from backend.main import app
        import backend.routes.chat as chat_module

        monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
        monkeypatch.setattr(chat_module, "run_turn", _mock_run_turn_text_only)
        monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/chat/stream",
                params={"conversation_id": "test-001", "user_id": "test-user-001"},
                headers=auth_headers(),
            )

        frames = parse_sse_frames(response.text)
        token_frames = [f for f in frames if f["event"] == "token"]

        assert len(token_frames) > 0, "Expected at least one token frame"
        for frame in token_frames:
            assert isinstance(frame["data"], dict), f"Token data must be a dict: {frame}"
            assert "text" in frame["data"], f"Token data must have 'text' key: {frame}"

    async def test_sse_done_data_is_empty_object(self, monkeypatch):
        """Done event data is an empty object {}."""
        from backend.main import app
        import backend.routes.chat as chat_module

        monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
        monkeypatch.setattr(chat_module, "run_turn", _mock_run_turn_text_only)
        monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/chat/stream",
                params={"conversation_id": "test-001", "user_id": "test-user-001"},
                headers=auth_headers(),
            )

        frames = parse_sse_frames(response.text)
        done_frames = [f for f in frames if f["event"] == "done"]

        assert len(done_frames) == 1, f"Expected exactly one done frame, got {len(done_frames)}"
        assert done_frames[0]["data"] == {}, f"Done data must be {{}}, got: {done_frames[0]['data']}"

    async def test_sse_no_live_anthropic_call(self, monkeypatch):
        """
        D-16: the SSE endpoint test makes no live call to the Anthropic API.
        This is guaranteed by patching run_turn -- the real AsyncAnthropic
        client in sse_generator is never invoked when run_turn is mocked.
        """
        from backend.main import app
        import backend.routes.chat as chat_module

        monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
        monkeypatch.setattr(chat_module, "run_turn", _mock_run_turn_text_only)
        monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)

        # If run_turn is patched, the fake is called instead of the real one.
        # We verify the mock is actually used by checking the events are the
        # deterministic ones from _mock_run_turn_text_only.
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/chat/stream",
                params={"conversation_id": "test-001", "user_id": "test-user-001"},
                headers=auth_headers(),
            )

        frames = parse_sse_frames(response.text)
        # The mock yields "Hello, " and "let me help you." tokens -- verify that.
        token_frames = [f for f in frames if f["event"] == "token"]
        token_texts = [f["data"].get("text", "") for f in token_frames]
        assert any("Hello" in t for t in token_texts), (
            "Expected mock token text 'Hello' -- live API would return different text. "
            f"Got tokens: {token_texts}"
        )

    async def test_sse_requires_conversation_id(self, monkeypatch):
        """
        T-02-09: conversation_id is required. Missing param returns 422 (FastAPI
        validation error), not a 500 or empty stream.
        """
        from backend.main import app
        import backend.routes.chat as chat_module

        monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
        monkeypatch.setattr(chat_module, "run_turn", _mock_run_turn_text_only)

        async with httpx.AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            # No ownership-check bypass needed: omitting conversation_id with
            # valid auth still correctly returns 422 via FastAPI's own
            # required-Query validation, which fires before any dependency
            # body (ownership check) runs.
            response = await client.get("/chat/stream", headers=auth_headers())  # no conversation_id

        assert response.status_code == 422, (
            f"Expected 422 for missing conversation_id, got {response.status_code}"
        )


class TestAssistantSinkGating:
    """
    WR-06: sse_generator must append to assistant_sink only when run_turn's
    LAST yielded event is `done`. run_turn's abnormal paths (max_tool_turns,
    unexpected_stop, max_retries) all yield `event: error` and then `return`
    normally -- a normal generator exit, not a raised exception -- so gating
    on "the loop exited without exception" is insufficient; the terminal
    event type must be tracked explicitly.

    These tests drive sse_generator directly (imported from
    backend.routes._sse) rather than through the HTTP endpoint, since the
    behavior under test lives entirely in sse_generator's post-loop gating
    logic and does not require the FastAPI/auth layer.
    """

    async def test_sink_not_appended_on_error_terminated_turn(self):
        """
        A turn that ends on an error event (mirroring max_tool_turns /
        unexpected_stop / max_retries) must leave assistant_sink empty --
        no partial/truncated text is persisted as if the turn completed.
        """
        from backend.routes._sse import sse_generator

        sink: list = []
        async for _ in sse_generator(
            messages=[],
            model="test-model",
            _run_turn=_mock_run_turn_token_then_error,
            assistant_sink=sink,
        ):
            pass

        assert sink == [], (
            f"expected assistant_sink to stay empty after an error-terminated turn, got: {sink}"
        )

    async def test_sink_appended_on_normal_completion(self):
        """A done-terminated turn still persists the accumulated assistant text."""
        from backend.routes._sse import sse_generator

        sink: list = []
        async for _ in sse_generator(
            messages=[],
            model="test-model",
            _run_turn=_mock_run_turn_token_then_done,
            assistant_sink=sink,
        ):
            pass

        assert sink == ["complete reply"], (
            f"expected assistant_sink to hold the accumulated token text, got: {sink}"
        )
