# tests/api/test_auth.py
"""
JWT middleware behavior tests (Phase 4 / D-03, T-04-02).

Tests cover the get_current_user dependency from api/auth.py:
  AUTH-01: Missing token (no header, no ?token=) -> 401
  AUTH-02: Garbage/malformed bearer token -> 401
  AUTH-03: Token signed by wrong secret -> 401
  AUTH-04: Valid token resolves user_id == TEST_USER_ID
  AUTH-05: Valid token via ?token= query param (SSE path) also authenticates
  AUTH-06: Wrong audience in token -> 401
  AUTH-07: Valid token header path returns structured user dict

Uses direct unit calls to get_current_user where constructing a full HTTP
request is unnecessary; uses AsyncClient against the FastAPI app for
HTTP-level 401 tests.

All Supabase calls are mocked; no live DB connections are made.
asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
from unittest.mock import MagicMock

import httpx
import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport

from tests.api.conftest import (
    TEST_JWT_SECRET,
    TEST_USER_ID,
    auth_headers,
    make_test_token,
    mock_supabase_factory,
)

WRONG_SECRET = "this-is-definitely-the-wrong-secret-key"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_bearer_cred(token: str) -> HTTPAuthorizationCredentials:
    """Create an HTTPAuthorizationCredentials mock with scheme='Bearer'."""
    cred = MagicMock(spec=HTTPAuthorizationCredentials)
    cred.scheme = "Bearer"
    cred.credentials = token
    return cred


# ---------------------------------------------------------------------------
# AUTH-01: Missing token -> 401
# ---------------------------------------------------------------------------


async def test_missing_token_raises_401(monkeypatch):
    """
    AUTH-01: GET /adaptations/ with no Authorization header and no ?token= returns 401.
    Tests the HTTP-level behavior against the FastAPI app.
    """
    import backend.routes.adaptations as adapt_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(adapt_module, "_get_async_supabase", mock_supabase_factory([]))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/adaptations/")

    assert response.status_code == 401, (
        f"Expected 401 for missing token, got {response.status_code}: {response.text}"
    )
    detail = response.json().get("detail", {})
    assert detail.get("error") == "unauthorized", (
        f"Expected error='unauthorized' in detail, got: {detail}"
    )


# ---------------------------------------------------------------------------
# AUTH-02: Garbage/malformed bearer token -> 401
# ---------------------------------------------------------------------------


async def test_garbage_token_raises_401(monkeypatch):
    """
    AUTH-02: A request with a malformed/garbage bearer token returns 401.
    """
    import backend.routes.adaptations as adapt_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(adapt_module, "_get_async_supabase", mock_supabase_factory([]))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/adaptations/",
            headers={"Authorization": "Bearer not.a.valid.jwt.at.all"},
        )

    assert response.status_code == 401, (
        f"Expected 401 for garbage token, got {response.status_code}: {response.text}"
    )
    detail = response.json().get("detail", {})
    assert detail.get("error") == "unauthorized", (
        f"Expected error='unauthorized' in detail, got: {detail}"
    )


# ---------------------------------------------------------------------------
# AUTH-03: Token signed by wrong secret -> 401
# ---------------------------------------------------------------------------


async def test_wrong_secret_token_raises_401(monkeypatch):
    """
    AUTH-03: A token signed by a different secret returns 401 (signature mismatch).
    """
    import backend.routes.adaptations as adapt_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setattr(adapt_module, "_get_async_supabase", mock_supabase_factory([]))

    bad_token = make_test_token(secret=WRONG_SECRET)

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/adaptations/",
            headers={"Authorization": f"Bearer {bad_token}"},
        )

    assert response.status_code == 401, (
        f"Expected 401 for wrong-secret token, got {response.status_code}: {response.text}"
    )
    detail = response.json().get("detail", {})
    assert detail.get("error") == "unauthorized", (
        f"Expected error='unauthorized' in detail, got: {detail}"
    )


# ---------------------------------------------------------------------------
# AUTH-04: Valid token via header resolves user_id == TEST_USER_ID (unit test)
# ---------------------------------------------------------------------------


async def test_valid_token_resolves_user_id(monkeypatch):
    """
    AUTH-04: Calling get_current_user directly with a valid token returns
    {"user_id": TEST_USER_ID, "email": ...}.

    This tests the dependency function in isolation without an HTTP request.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    from backend.auth import get_current_user

    token = make_test_token(user_id=TEST_USER_ID, email="test@example.com")
    cred = _make_bearer_cred(token)

    result = await get_current_user(cred=cred, token=None)

    assert result["user_id"] == TEST_USER_ID, (
        f"Expected user_id={TEST_USER_ID}, got: {result['user_id']}"
    )
    assert result["email"] == "test@example.com", (
        f"Expected email='test@example.com', got: {result['email']}"
    )


# ---------------------------------------------------------------------------
# AUTH-05: Valid token via ?token= query param (SSE path) authenticates
# ---------------------------------------------------------------------------


async def test_valid_token_via_query_param(monkeypatch):
    """
    AUTH-05: A valid JWT passed as ?token= (SSE path) authenticates successfully.

    Tests get_current_user directly with no bearer header (cred=None) and
    a valid token in the query param position.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    from backend.auth import get_current_user

    token = make_test_token(user_id=TEST_USER_ID)

    # Simulate the SSE case: no Authorization header, token only in ?token=
    result = await get_current_user(cred=None, token=token)

    assert result["user_id"] == TEST_USER_ID, (
        f"SSE path (?token=) should resolve user_id={TEST_USER_ID}, got: {result['user_id']}"
    )


# ---------------------------------------------------------------------------
# AUTH-06: Wrong audience in token -> 401
# ---------------------------------------------------------------------------


async def test_wrong_audience_raises_401(monkeypatch):
    """
    AUTH-06: A token with aud != 'authenticated' is rejected with 401.

    Supabase JWTs must carry aud='authenticated'; a token without this claim
    (e.g., a service-role token or a token from a different provider) must fail.
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    from backend.auth import get_current_user

    # Encode a token with wrong audience
    wrong_aud_token = jwt.encode(
        {"sub": TEST_USER_ID, "email": "test@example.com", "aud": "service_role"},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )

    cred = _make_bearer_cred(wrong_aud_token)

    with pytest.raises(HTTPException) as exc_info:
        await get_current_user(cred=cred, token=None)

    assert exc_info.value.status_code == 401, (
        f"Expected 401 for wrong audience, got {exc_info.value.status_code}"
    )


# ---------------------------------------------------------------------------
# AUTH-07: Valid token full HTTP path (integration via /adaptations/)
# ---------------------------------------------------------------------------


async def test_valid_token_full_http_path(monkeypatch):
    """
    AUTH-07: A valid JWT in the Authorization header reaches the endpoint handler
    and returns 200 with expected data (proves auth does not block valid requests).
    """
    import backend.routes.adaptations as adapt_module
    from backend.main import app

    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)

    mock_rows = [
        {
            "id": "adapt-auth-test",
            "user_id": TEST_USER_ID,
            "trigger": "missed",
            "scope": "micro",
            "signal_count": 1,
            "explanation_text": "Auth test adaptation.",
            "before_snapshot": {},
            "after_snapshot": {},
            "created_at": "2026-06-20T10:00:00Z",
        }
    ]
    monkeypatch.setattr(adapt_module, "_get_async_supabase", mock_supabase_factory(mock_rows))

    async with httpx.AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/adaptations/",
            headers=auth_headers(),
        )

    assert response.status_code == 200, (
        f"Expected 200 with valid token, got {response.status_code}: {response.text}"
    )
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["id"] == "adapt-auth-test"
