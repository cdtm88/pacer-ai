# tests/api/conftest.py
"""
Shared fixtures for tests/api/ test suite.

Provides:
- TEST_USER_ID: fixed UUID for all API tests
- TEST_JWT_SECRET: shared JWT secret used by make_test_token and test_auth.py
- make_test_token: generates a valid Supabase-style JWT for test requests
- auth_headers: ready-made Authorization header dict for use in test requests
- mock_supabase_factory: creates async-compatible mock Supabase clients
- parse_sse_frames: re-export from test_sse.py for use in onboarding tests

asyncio_mode = auto (pytest.ini) -- no @pytest.mark.asyncio needed.
"""
import os
import jwt
import pytest
from unittest.mock import AsyncMock, MagicMock

# Fixed test user UUID -- used across all tests/api/ files
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"

# Shared JWT secret used in all auth tests and fixtures.
# Must be set as SUPABASE_JWT_SECRET env var for the auth middleware to accept tokens.
TEST_JWT_SECRET = "test-supabase-jwt-secret-for-unit-tests-only"


def make_test_token(
    user_id: str = TEST_USER_ID,
    email: str = "test@example.com",
    secret: str = TEST_JWT_SECRET,
) -> str:
    """
    Generate a valid Supabase-style JWT for use in test requests.

    The token is signed with TEST_JWT_SECRET and uses audience="authenticated"
    to match the get_current_user dependency's expected claims.

    Args:
        user_id: UUID string for the sub claim (default TEST_USER_ID).
        email:   Email for the email claim.
        secret:  Signing secret (default TEST_JWT_SECRET).

    Returns:
        Encoded JWT string suitable for use in Authorization: Bearer headers.
    """
    return jwt.encode(
        {"sub": user_id, "email": email, "aud": "authenticated"},
        secret,
        algorithm="HS256",
    )


def auth_headers(
    user_id: str = TEST_USER_ID,
    email: str = "test@example.com",
) -> dict:
    """
    Return an Authorization: Bearer header dict with a valid test JWT.

    Usage in tests:
        response = await client.get("/endpoint/", headers=auth_headers())

    The SUPABASE_JWT_SECRET env var must be set to TEST_JWT_SECRET before the
    request is made. Use with monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET).
    """
    token = make_test_token(user_id=user_id, email=email)
    return {"Authorization": f"Bearer {token}"}


def mock_supabase_factory(return_rows: list):
    """
    Return an async-callable that produces a mock Supabase client.

    The mock client supports the chained call pattern:
        await supabase.table(...).select/insert/upsert/eq/order/execute()

    All chain methods return the same mock to allow arbitrary chaining.
    The terminal .execute() method returns an async mock whose .data attribute
    is set to return_rows.

    Usage:
        monkeypatch.setattr(module, "_get_async_supabase", mock_supabase_factory([]))

    Args:
        return_rows: List of row dicts that .execute() will return in .data
    """
    execute_result = MagicMock()
    execute_result.data = return_rows

    mock_client = MagicMock()
    # All chain methods return the same mock so arbitrary chaining works
    mock_client.table.return_value = mock_client
    mock_client.select.return_value = mock_client
    mock_client.insert.return_value = mock_client
    mock_client.upsert.return_value = mock_client
    mock_client.eq.return_value = mock_client
    mock_client.order.return_value = mock_client
    mock_client.execute = AsyncMock(return_value=execute_result)

    async def _get_mock_client():
        return mock_client

    return _get_mock_client


def parse_sse_frames(body: str) -> list[dict]:
    """
    Parse a raw SSE body string into a list of frame dicts.

    Re-exported from tests/agent/test_sse.py pattern for reuse in API tests.
    Each frame is a pair of lines:
      event: <type>
      data: <json>
    Followed by a blank line.

    Returns list of {"event": str, "data": dict} per frame.
    Skips blank lines and comment lines (starting with ':').
    """
    import json
    frames = []
    current: dict = {}
    for line in body.splitlines():
        line = line.rstrip("\r")
        if not line:
            if "event" in current and "data" in current:
                frames.append(current)
            current = {}
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            current["event"] = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_str = line[len("data:"):].strip()
            try:
                current["data"] = json.loads(data_str)
            except json.JSONDecodeError:
                current["data"] = data_str
    if "event" in current and "data" in current:
        frames.append(current)
    return frames
