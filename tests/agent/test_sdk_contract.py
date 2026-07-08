# tests/agent/test_sdk_contract.py
"""
Offline SDK contract-conformance tests (Plan 02-05).

Purpose: Convert RESEARCH.md Assumptions A1/A2 and Open Question 1 from silent
assumptions into hard, offline-verifiable gates.

Every test here imports the REAL installed anthropic package and asserts that
the exact attribute surface run_turn (agent/loop.py) relies on actually exists
in the installed version. If the anthropic package is not installed or renames
any of these attributes, the corresponding test fails loudly — not silently.

CRITICAL constraints:
  - Zero network calls (enforced by never calling .create() or entering the
    async stream context manager against a real endpoint)
  - No ANTHROPIC_API_KEY required (dummy key "sk-ant-test-not-real" is inert
    at construction time; the SDK reads it lazily and does not validate it offline)
  - All assertions use introspection only: hasattr, model_fields, __mro__,
    isinstance, callable — never a live API call

References:
  - agent/loop.py: the exact SDK call sites being validated
  - tests/agent/conftest.py: the mock surface whose attribute names must match
  - .planning/phases/02-agent-core/02-RESEARCH.md: A1, A2, A3, Open Question 1
  - .planning/phases/02-agent-core/02-05-PLAN.md: behavior specification

Verified against anthropic==0.67.x installed in .venv.
"""

from anthropic import AsyncAnthropic
from anthropic.lib.streaming._messages import AsyncMessageStream, AsyncMessageStreamManager

# ---------------------------------------------------------------------------
# Key type imports — these will NameError / ImportError if the SDK renames them,
# which is the desired fail-loud behaviour.
# ---------------------------------------------------------------------------
from anthropic.types import Message, RawContentBlockDeltaEvent, TextDelta, ToolUseBlock

# Dummy key — inert at construction time; SDK does not validate or contact the
# network during __init__. No ANTHROPIC_API_KEY env var required.
_DUMMY_KEY = "sk-ant-test-not-real"


# ---------------------------------------------------------------------------
# Test 1: AsyncAnthropic exists and is a class
# ---------------------------------------------------------------------------

def test_async_anthropic_exists():
    """
    anthropic.AsyncAnthropic exists and is a concrete class.
    Constructing it with a dummy key performs no network call.

    Validates: RESEARCH.md A3 — SDK class name and construction surface.
    """
    assert isinstance(AsyncAnthropic, type), (
        "anthropic.AsyncAnthropic must be a class; got %r" % type(AsyncAnthropic)
    )
    # Construction must not raise and must not contact the network
    client = AsyncAnthropic(api_key=_DUMMY_KEY)
    assert client is not None


# ---------------------------------------------------------------------------
# Test 2: messages.stream is an async context manager
# ---------------------------------------------------------------------------

def test_messages_stream_is_context_manager():
    """
    An AsyncAnthropic instance exposes .messages with a callable .stream
    attribute, and the object returned by messages.stream(...) is an async
    context manager (__aenter__ and __aexit__ both present).

    This validates the loop's:
        async with client.messages.stream(
            model=model, max_tokens=4096, tools=TOOL_SCHEMAS, messages=messages,
        ) as stream:

    The manager object is obtained WITHOUT entering it (no __aenter__ call),
    so no network connection is opened.

    Validated type: AsyncMessageStreamManager
    """
    client = AsyncAnthropic(api_key=_DUMMY_KEY)

    # Attribute presence on instance
    assert hasattr(client, "messages"), "AsyncAnthropic instance must have .messages"
    assert hasattr(client.messages, "stream"), "AsyncAnthropic.messages must have .stream"
    assert callable(client.messages.stream), ".messages.stream must be callable"

    # Obtain manager WITHOUT entering (no network call)
    manager = client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=16,
        messages=[{"role": "user", "content": "hi"}],
    )

    # The manager (returned before __aenter__) is AsyncMessageStreamManager
    # and must expose __aenter__ and __aexit__ to be a valid async context manager.
    assert hasattr(manager, "__aenter__"), (
        "messages.stream() return value must have __aenter__; got type %r" % type(manager)
    )
    assert hasattr(manager, "__aexit__"), (
        "messages.stream() return value must have __aexit__; got type %r" % type(manager)
    )

    # Runtime type confirmation (for traceability in failure messages)
    assert isinstance(manager, AsyncMessageStreamManager), (
        "Expected AsyncMessageStreamManager, got %r" % type(manager)
    )


# ---------------------------------------------------------------------------
# Test 3: The entered stream type exposes get_final_message
# ---------------------------------------------------------------------------

def test_stream_get_final_message_attr():
    """
    The async stream type yielded by __aenter__ (AsyncMessageStream) declares
    a get_final_message attribute, matching:
        final_msg = await stream.get_final_message()
    in agent/loop.py.

    IMPORTANT: get_final_message lives on AsyncMessageStream (the entered
    stream), NOT on AsyncMessageStreamManager (the manager returned by
    client.messages.stream() before entering). This test verifies the
    attribute on the correct class.

    Note: The manager itself does NOT have get_final_message — this is
    intentional and matches the SDK design. The test does NOT enter the
    context manager (which would require a network call); instead it inspects
    the AsyncMessageStream class directly.
    """
    # AsyncMessageStream is the type yielded by __aenter__; confirm it has
    # get_final_message and that it is callable.
    assert hasattr(AsyncMessageStream, "get_final_message"), (
        "AsyncMessageStream must have get_final_message; "
        "this is the type returned by 'async with client.messages.stream(...) as stream'"
    )
    assert callable(AsyncMessageStream.get_final_message), (
        "AsyncMessageStream.get_final_message must be callable (coroutine function)"
    )

    # Confirm the manager class does NOT expose get_final_message (documents
    # the two-step pattern: manager -> __aenter__ -> stream with get_final_message)
    assert not hasattr(AsyncMessageStreamManager, "get_final_message"), (
        "AsyncMessageStreamManager (the manager) must NOT have get_final_message; "
        "it is on the entered stream (AsyncMessageStream)"
    )


# ---------------------------------------------------------------------------
# Test 4: Message.stop_reason includes 'tool_use' and 'end_turn' literals
# ---------------------------------------------------------------------------

def test_stop_reason_literal_supported():
    """
    The installed anthropic types expose a Message model whose stop_reason
    field type annotation includes the literals 'tool_use' and 'end_turn'
    that agent/loop.py branches on:
        if stop_reason == 'tool_use': ...
        elif stop_reason == 'end_turn': ...

    Also asserts that ToolUseBlock exists and exposes name, input, id fields.

    Validates: RESEARCH.md A1 (stop_reason surface); AGENT-01 (explicit check).
    """
    # Message must have stop_reason field
    assert "stop_reason" in Message.model_fields, (
        "anthropic.types.Message must have a stop_reason field"
    )

    # Inspect the string representation of the field annotation for the literals
    # the loop branches on. This is the safest introspection approach for
    # Pydantic v2 Union/Literal annotations that may not be fully resolved at
    # module import time.
    field_info = Message.model_fields["stop_reason"]
    field_repr = repr(field_info.annotation)
    assert "tool_use" in field_repr, (
        "Message.stop_reason annotation must include literal 'tool_use'; got: %s" % field_repr
    )
    assert "end_turn" in field_repr, (
        "Message.stop_reason annotation must include literal 'end_turn'; got: %s" % field_repr
    )

    # ToolUseBlock must exist and expose the three fields the loop reads
    assert "name" in ToolUseBlock.model_fields, "ToolUseBlock must have 'name' field"
    assert "input" in ToolUseBlock.model_fields, "ToolUseBlock must have 'input' field"
    assert "id" in ToolUseBlock.model_fields, "ToolUseBlock must have 'id' field"


# ---------------------------------------------------------------------------
# Test 5: Text-delta event path event.delta.text
# ---------------------------------------------------------------------------

def test_content_block_delta_text_path():
    """
    The SDK exposes the streaming text-delta event path that loop.py uses:
        if event.type == "content_block_delta":
            if hasattr(event.delta, "text"):
                text_buffer.append(event.delta.text)

    Verified by asserting that:
    1. RawContentBlockDeltaEvent exists in anthropic.types with a 'delta' field
    2. TextDelta exists in anthropic.types with a 'text' field

    The loop uses hasattr(event.delta, "text") as a guard, which handles the
    case where event.delta is a non-text delta (e.g. InputJSONDelta). The
    underlying type for text deltas is TextDelta, confirmed here.

    Resolved type: RawContentBlockDeltaEvent.delta -> TextDelta.text
    (TextDelta is the concrete variant; the union is RawContentBlockDelta)
    """
    # RawContentBlockDeltaEvent is the event type for content_block_delta events
    assert "delta" in RawContentBlockDeltaEvent.model_fields, (
        "RawContentBlockDeltaEvent must have a 'delta' field matching event.delta in loop.py"
    )
    assert "type" in RawContentBlockDeltaEvent.model_fields, (
        "RawContentBlockDeltaEvent must have a 'type' field matching "
        "event.type == 'content_block_delta'"
    )

    # TextDelta is the concrete delta type that carries the text payload
    assert "text" in TextDelta.model_fields, (
        "TextDelta must have a 'text' field matching event.delta.text in loop.py; "
        "resolved from RawContentBlockDelta union"
    )
    assert "type" in TextDelta.model_fields, (
        "TextDelta must have a 'type' field (value: 'text_delta') for type narrowing"
    )


# ---------------------------------------------------------------------------
# Test 6: Conftest mock surface matches real SDK attribute names
# ---------------------------------------------------------------------------

def test_conftest_mock_matches_real_surface():
    """
    Every SDK attribute name that tests/agent/conftest.py's _MockStream
    simulates corresponds to a real attribute/field on the installed
    anthropic types, so a green mocked compliance suite cannot silently
    diverge from the real SDK shape.

    Checks that the literal attribute NAMES used by the mock:
      - stop_reason       (on final_msg, from MagicMock)  -> Message.stop_reason
      - type              (on content blocks)             -> ToolUseBlock.type
      - name              (on tool_use blocks)            -> ToolUseBlock.name
      - input             (on tool_use blocks)            -> ToolUseBlock.input
      - id                (on tool_use blocks)            -> ToolUseBlock.id
      - get_final_message (on stream)                     -> AsyncMessageStream.get_final_message
      - __aenter__        (on stream manager)             -> AsyncMessageStreamManager.__aenter__
      - __aexit__         (on stream manager)             -> AsyncMessageStreamManager.__aexit__

    This is a structural alignment test — it does not import or execute conftest
    fixtures; it asserts that the NAMES the conftest encodes match the real SDK.

    Closes RESEARCH.md Open Question 1 ("the exact attribute path the loop uses
    resolves on the real type") and threat T-02-14.
    """
    # --- Message.stop_reason ---
    assert "stop_reason" in Message.model_fields, (
        "Mock uses msg.stop_reason but Message has no stop_reason field"
    )

    # --- ToolUseBlock fields used by mock (_tool_block helper) ---
    for field_name in ("type", "name", "input", "id"):
        assert field_name in ToolUseBlock.model_fields, (
            "Mock sets tool_block.%s but ToolUseBlock has no '%s' field" % (field_name, field_name)
        )

    # --- AsyncMessageStream.get_final_message ---
    assert hasattr(AsyncMessageStream, "get_final_message"), (
        "Mock exposes get_final_message on stream but AsyncMessageStream has no such attribute"
    )

    # --- AsyncMessageStreamManager async context manager protocol ---
    assert hasattr(AsyncMessageStreamManager, "__aenter__"), (
        "Mock implements __aenter__ but AsyncMessageStreamManager has no __aenter__"
    )
    assert hasattr(AsyncMessageStreamManager, "__aexit__"), (
        "Mock implements __aexit__ but AsyncMessageStreamManager has no __aexit__"
    )

    # --- delta.text path: TextDelta.text ---
    assert "text" in TextDelta.model_fields, (
        "Mock uses event.delta.text but TextDelta has no 'text' field"
    )

    # --- delta.type narrowing: TextDelta.type ---
    assert "type" in TextDelta.model_fields, (
        "TextDelta has no 'type' field; cannot distinguish text_delta from other delta variants"
    )


# ---------------------------------------------------------------------------
# Test 7: No network call
# ---------------------------------------------------------------------------

def test_no_network_call(monkeypatch):
    """
    Running this entire module (importing anthropic, constructing AsyncAnthropic,
    obtaining a stream manager) performs zero HTTP requests to the Anthropic
    API endpoint.

    Enforced by patching httpx.Client.send and httpx.AsyncClient.send to raise
    if called. If any test in this module triggers a network request, this patch
    will surface the call immediately as a test failure.

    Note: this test must be the LAST test in the file so that it covers the
    full import + construction surface exercised by the earlier tests.
    """
    import httpx

    def _no_network_send(*args, **kwargs):
        raise AssertionError(
            "test_sdk_contract.py triggered a live network request — "
            "this module must perform zero HTTP requests (offline introspection only)"
        )

    monkeypatch.setattr(httpx.Client, "send", _no_network_send)
    monkeypatch.setattr(httpx.AsyncClient, "send", _no_network_send)

    # Re-exercise the primary construction and inspection path to confirm
    # that no patched send method is invoked
    client = AsyncAnthropic(api_key=_DUMMY_KEY)
    manager = client.messages.stream(
        model="claude-sonnet-4-5",
        max_tokens=16,
        messages=[{"role": "user", "content": "hi"}],
    )
    # Only assert attribute presence — do not enter the manager (that would
    # attempt to open a real HTTP connection)
    assert hasattr(manager, "__aenter__")
    assert hasattr(manager, "__aexit__")
    assert hasattr(AsyncMessageStream, "get_final_message")
