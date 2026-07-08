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

import pytest

import backend.rate_limit as rate_limit_module
from tests.api.conftest import TEST_USER_ID, TEST_JWT_SECRET, auth_headers, parse_sse_frames


@pytest.fixture(autouse=True)
def _reset_rate_limit_log():
    """Item 6: reset the rate-limit module's request log between tests so
    exhausting the budget in one test doesn't bleed into another (this file's
    tests share TEST_USER_ID)."""
    rate_limit_module._request_log.clear()
    yield
    rate_limit_module._request_log.clear()


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


# ---------------------------------------------------------------------------
# GET /conversations/{id}/messages (09-07 Task 1, item 4 / D-04)
#
# Backs the frontend's cache-miss reload fix: after the client's
# ['active-conversation'] query cache is GC'd, the queryFn refetches the
# EXISTING conversation's history via this endpoint instead of creating a
# new empty conversation row. T-09-07-01 (IDOR): the endpoint wraps
# load_conversation (app-layer user_id ownership filter) rather than issuing
# a new unscoped SELECT.
# ---------------------------------------------------------------------------


async def test_get_conversation_messages_returns_owned_messages(monkeypatch):
    """
    Happy path: a valid JWT and a conversation_id owned by the requesting
    user returns that conversation's {role, content} messages, in
    chronological order (load_conversation reverses the DESC DB order).
    """
    import httpx
    from httpx import ASGITransport
    from backend.main import app
    import backend.routes.onboarding as onboarding_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    owned_id = "22222222-2222-2222-2222-222222222222"
    # Mock rows are returned as-is (DESC/newest-first, mirroring the real
    # query's .order("created_at", desc=True)); load_conversation reverses
    # them to chronological order before returning.
    messages_data = [
        {"role": "assistant", "content": "hello!", "created_at": "t2"},
        {"role": "user", "content": "hi", "created_at": "t1"},
    ]
    mock_factory = _make_chat_mock_supabase(
        conversations_data=[{"id": owned_id}], messages_data=messages_data
    )
    monkeypatch.setattr(onboarding_module, "_get_async_supabase", mock_factory)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/conversations/{owned_id}/messages",
            headers=auth_headers(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "hello!"},
        ]
    }


async def test_get_conversation_messages_foreign_id_returns_empty_list(monkeypatch):
    """
    T-09-07-01 (IDOR mitigation): a well-formed conversation_id that does not
    belong to the requesting user must not leak any messages. load_conversation's
    app-layer WHERE user_id=<requesting user> filter excludes foreign rows, so
    the endpoint returns an empty list (not another user's data, not a 404 that
    would allow conversation-id enumeration).
    """
    import httpx
    from httpx import ASGITransport
    from backend.main import app
    import backend.routes.onboarding as onboarding_module

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    foreign_id = "11111111-1111-1111-1111-111111111111"
    # Simulates the DB's ownership filter excluding rows belonging to another user.
    mock_factory = _make_chat_mock_supabase(conversations_data=[], messages_data=[])
    monkeypatch.setattr(onboarding_module, "_get_async_supabase", mock_factory)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            f"/conversations/{foreign_id}/messages",
            headers=auth_headers(),
        )

    assert response.status_code == 200
    assert response.json() == {"messages": []}


async def test_get_conversation_messages_rejects_malformed_id(monkeypatch):
    """
    A malformed (non-UUID) conversation_id must be rejected with HTTP 400
    before it ever reaches load_conversation/Supabase (format validation via
    validate_uuid fails before any DB query) -- the same defence-in-depth
    pattern used elsewhere (rides.py, adaptations.py, chat_stream's
    _resolve_conversation_id).
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
            "/conversations/not-a-uuid/messages",
            headers=auth_headers(),
        )

    assert response.status_code == 400
    assert response.json()["detail"]["error"] == "invalid_id"


# ---------------------------------------------------------------------------
# Item 6 (D-02/D-03): rate limiting on GET /chat/stream
# ---------------------------------------------------------------------------


async def test_chat_stream_over_limit_returns_sse_rate_limited_frame(monkeypatch):
    """
    Item 6: an over-limit GET /chat/stream returns HTTP 200 with a single SSE
    `error` frame whose code is `rate_limited` -- not an HTTP 429 -- proving
    the streaming-safe path (a 429 cannot be raised once StreamingResponse
    iteration begins).
    """
    import httpx
    from httpx import ASGITransport
    from backend.main import app
    import backend.routes.onboarding as onboarding_module
    import backend.routes.chat as chat_module
    from backend.rate_limit import MAX_REQUESTS_PER_WINDOW

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
        # Exhaust the window for TEST_USER_ID.
        for _ in range(MAX_REQUESTS_PER_WINDOW):
            r = await client.get(
                "/chat/stream",
                params={"conversation_id": owned_id, "message": "hi"},
                headers=auth_headers(),
            )
            assert r.status_code == 200

        # The (N+1)th request must be rejected via an SSE error frame, not a 429.
        response = await client.get(
            "/chat/stream",
            params={"conversation_id": owned_id, "message": "hi"},
            headers=auth_headers(),
        )

    assert response.status_code == 200
    frames = parse_sse_frames(response.text)
    event_types = [f["event"] for f in frames]
    assert event_types == ["error"], f"Expected only a rate_limited error frame, got: {event_types}"
    assert frames[0]["data"]["code"] == "rate_limited"
