# tests/api/test_chat.py
"""
CR-03 regression tests for GET /chat/stream conversation_id validation
(08-REVIEW.md).

Before this fix, chat_stream threaded a raw, unvalidated client-supplied
conversation_id straight into load_conversation, sse_generator (audit_log
writes via dispatch_tool), and save_messages. These tests assert that
chat_stream now reuses onboarding.py's _resolve_conversation_id (format +
ownership validation, WR-08/phase 07) and rejects a malformed or foreign
conversation_id with an SSE error frame instead of proceeding.

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
from unittest.mock import AsyncMock, MagicMock

from tests.api.conftest import TEST_USER_ID, TEST_JWT_SECRET, auth_headers, parse_sse_frames


async def _mock_chat_run_turn(messages, client, model, trust_scanner, audit_log, **kwargs):
    """Deterministic mock of run_turn for chat_stream SSE tests."""
    yield {"event": "token", "data": {"text": "Here's your update."}}
    yield {"event": "done", "data": {}}


class _MockChain:
    """Chainable select/insert query stub returning a fixed data list."""

    def __init__(self, data):
        self._data = data

    def select(self, *args, **kwargs):
        return self

    def eq(self, *args, **kwargs):
        return self

    def order(self, *args, **kwargs):
        return self

    def limit(self, *args, **kwargs):
        return self

    def insert(self, *args, **kwargs):
        return self

    async def execute(self):
        return MagicMock(data=self._data)


def _make_chat_mock_supabase(conversations_data: list, messages_data: list):
    """
    Async callable producing a mock Supabase client that routes by table name:
    "conversations" -> conversations_data (ownership check), "messages" ->
    messages_data (load_conversation / save_messages).
    """

    class _MockClient:
        def table(self, name):
            if name == "conversations":
                return _MockChain(conversations_data)
            if name == "messages":
                return _MockChain(messages_data)
            raise AssertionError(f"unexpected table queried: {name}")

    async def _get_mock():
        return _MockClient()

    return _get_mock


async def test_chat_stream_rejects_malformed_conversation_id(monkeypatch):
    """
    CR-03: a malformed (non-UUID) conversation_id must be rejected with an
    SSE error frame, and must never reach load_conversation/save_messages/
    Supabase at all (format validation fails before any DB query).
    """
    import httpx
    from httpx import ASGITransport
    from backend.main import app
    import backend.routes.onboarding as onboarding_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    async def _unexpected_supabase():
        raise AssertionError("must not query Supabase for a malformed conversation_id")

    monkeypatch.setattr(onboarding_module, "_get_async_supabase", _unexpected_supabase)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/chat/stream",
            params={"conversation_id": "not-a-uuid", "message": "hi"},
            headers=auth_headers(),
        )

    assert response.status_code == 200
    frames = parse_sse_frames(response.text)
    event_types = [f["event"] for f in frames]
    assert event_types == ["error"], f"Expected only an error frame, got: {event_types}"
    assert frames[0]["data"]["code"] == "invalid_conversation_id"


async def test_chat_stream_rejects_foreign_conversation_id(monkeypatch):
    """
    CR-03: a well-formed conversation_id that does not belong to the
    requesting user (ownership check returns no rows) must be rejected with
    an SSE error frame -- a client must not be able to point the audit trail
    or message history at another user's conversation_id.
    """
    import httpx
    from httpx import ASGITransport
    from backend.main import app
    import backend.routes.onboarding as onboarding_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    foreign_id = "11111111-1111-1111-1111-111111111111"
    mock_factory = _make_chat_mock_supabase(conversations_data=[], messages_data=[])
    monkeypatch.setattr(onboarding_module, "_get_async_supabase", mock_factory)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/chat/stream",
            params={"conversation_id": foreign_id, "message": "hi"},
            headers=auth_headers(),
        )

    assert response.status_code == 200
    frames = parse_sse_frames(response.text)
    event_types = [f["event"] for f in frames]
    assert event_types == ["error"], f"Expected only an error frame, got: {event_types}"
    assert frames[0]["data"]["code"] == "invalid_conversation_id"


async def test_chat_stream_proceeds_with_owned_conversation_id(monkeypatch):
    """
    CR-03 (happy path): a well-formed conversation_id owned by the requesting
    user (ownership check returns a row) is retained, and chat_stream proceeds
    normally through sse_generator -- token/done frames are emitted.
    """
    import httpx
    from httpx import ASGITransport
    from backend.main import app
    import backend.routes.onboarding as onboarding_module
    import backend.routes.chat as chat_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    owned_id = "22222222-2222-2222-2222-222222222222"
    mock_factory = _make_chat_mock_supabase(
        conversations_data=[{"id": owned_id}], messages_data=[]
    )
    monkeypatch.setattr(onboarding_module, "_get_async_supabase", mock_factory)
    monkeypatch.setattr(chat_module, "run_turn", _mock_chat_run_turn)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/chat/stream",
            params={"conversation_id": owned_id, "message": "how am I doing?"},
            headers=auth_headers(),
        )

    assert response.status_code == 200
    frames = parse_sse_frames(response.text)
    event_types = [f["event"] for f in frames]
    assert "token" in event_types, f"Expected a token frame, got: {event_types}"
    assert "done" in event_types, f"Expected a done frame, got: {event_types}"
    assert "error" not in event_types, f"Unexpected error frame: {event_types}"
