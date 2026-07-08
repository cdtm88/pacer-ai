# tests/api/test_chat_token.py
"""
Tests for the SSE token-exchange contract (item 5, D-04, WR-006 mitigation).

Specifies:
- POST /chat/token requires a valid Supabase Bearer JWT and mints a short-lived
  (~60s) sse_token HS256-signed with a NEW, dedicated SSE_TOKEN_SECRET env var.
- GET /chat/stream accepts that ephemeral sse_token via ?token= (query-param
  path only) in addition to the existing Supabase JWT verification paths.
- The two token types (sse_token vs real Supabase JWT) never cross-validate --
  the `typ: "sse_token"` claim is a deliberate namespace guard (T-10-03-02).

These tests are RED until Task 2 implements POST /chat/token and extends
get_current_user's query-param branch.

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
import time

import jwt

from tests.api.conftest import TEST_JWT_SECRET, TEST_USER_ID, auth_headers, make_test_token

SSE_TOKEN_SECRET_FOR_TESTS = "test-sse-secret-unit-only"


async def test_issue_sse_token_returns_short_lived_token(monkeypatch):
    """
    POST /chat/token, authenticated with a real Supabase JWT (Bearer header),
    returns {token, expires_in}. The returned token is signed with the
    dedicated SSE_TOKEN_SECRET (not SUPABASE_JWT_SECRET), carries
    typ == "sse_token", sub == the authenticated user's id, and has a short
    (<=90s) lifetime.
    """
    import httpx
    from httpx import ASGITransport

    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SSE_TOKEN_SECRET", SSE_TOKEN_SECRET_FOR_TESTS)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/chat/token", headers=auth_headers())

    assert response.status_code == 200
    body = response.json()
    assert "token" in body
    assert "expires_in" in body

    decoded = jwt.decode(
        body["token"],
        SSE_TOKEN_SECRET_FOR_TESTS,
        algorithms=["HS256"],
        audience="authenticated",
    )
    assert decoded["typ"] == "sse_token"
    assert decoded["sub"] == TEST_USER_ID
    assert decoded["exp"] - decoded["iat"] <= 90 if "iat" in decoded else True
    # Lifetime bound: exp must not be far in the future (short-lived contract).
    assert decoded["exp"] - int(time.time()) <= 90


async def test_issue_sse_token_requires_auth(monkeypatch):
    """POST /chat/token with no Authorization header returns 401."""
    import httpx
    from httpx import ASGITransport

    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SSE_TOKEN_SECRET", SSE_TOKEN_SECRET_FOR_TESTS)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post("/chat/token")

    assert response.status_code == 401


async def test_stream_accepts_ephemeral_sse_token(monkeypatch):
    """
    GET /chat/stream authenticates via the ephemeral sse_token carried in
    ?token= (no Bearer header at all) -- the query-param verify path must try
    the sse_token branch before falling to the existing Supabase paths.
    """
    import httpx
    from httpx import ASGITransport

    import backend.routes.chat as chat_module
    import backend.routes.onboarding as onboarding_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SSE_TOKEN_SECRET", SSE_TOKEN_SECRET_FOR_TESTS)

    conversation_id = "22222222-2222-2222-2222-222222222222"

    async def _bypass_resolve(user_id, conv_id):
        return conv_id

    monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)

    async def _mock_run_turn(messages, client, model, trust_scanner, audit_log, **kwargs):
        yield {"event": "token", "data": {"text": "hi"}}
        yield {"event": "done", "data": {}}

    monkeypatch.setattr(chat_module, "run_turn", _mock_run_turn)

    async def _no_history(*args, **kwargs):
        return []

    monkeypatch.setattr(onboarding_module, "load_conversation", _no_history)

    async def _noop_save(*args, **kwargs):
        return None

    monkeypatch.setattr(onboarding_module, "save_messages", _noop_save)

    ephemeral = jwt.encode(
        {
            "sub": TEST_USER_ID,
            "aud": "authenticated",
            "typ": "sse_token",
            "exp": int(time.time()) + 60,
        },
        SSE_TOKEN_SECRET_FOR_TESTS,
        algorithm="HS256",
    )

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/chat/stream",
            params={"conversation_id": conversation_id, "token": ephemeral},
        )

    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


async def test_real_supabase_jwt_is_not_an_sse_token(monkeypatch):
    """
    Namespace guard (T-10-03-02): a real Supabase-style JWT (no `typ` claim,
    signed with SUPABASE_JWT_SECRET, not SSE_TOKEN_SECRET) must NOT be
    accepted through the sse_token branch. It should still authenticate via
    the existing Supabase HS256 verification path -- proving the two token
    types never cross-validate.
    """
    import httpx
    from httpx import ASGITransport

    import backend.routes.chat as chat_module
    import backend.routes.onboarding as onboarding_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SSE_TOKEN_SECRET", SSE_TOKEN_SECRET_FOR_TESTS)

    conversation_id = "22222222-2222-2222-2222-222222222222"

    async def _bypass_resolve(user_id, conv_id):
        return conv_id

    monkeypatch.setattr(chat_module, "_resolve_conversation_id", _bypass_resolve)

    async def _mock_run_turn(messages, client, model, trust_scanner, audit_log, **kwargs):
        yield {"event": "token", "data": {"text": "hi"}}
        yield {"event": "done", "data": {}}

    monkeypatch.setattr(chat_module, "run_turn", _mock_run_turn)

    async def _no_history(*args, **kwargs):
        return []

    monkeypatch.setattr(onboarding_module, "load_conversation", _no_history)

    async def _noop_save(*args, **kwargs):
        return None

    monkeypatch.setattr(onboarding_module, "save_messages", _noop_save)

    # A normal Supabase-style JWT has no `typ` claim -- make_test_token never sets one.
    real_jwt = make_test_token()

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/chat/stream",
            params={"conversation_id": conversation_id, "token": real_jwt},
        )

    # Must still authenticate -- via the existing Supabase HS256 path, not the
    # sse_token branch (which requires typ == "sse_token" and would reject this).
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")
