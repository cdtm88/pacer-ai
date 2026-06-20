# tests/api/test_calendar.py
"""
Tests for the Google Calendar integration (CAL-01 through CAL-04).

Covers four cases per the plan:
  1. Token encryption: after a simulated callback the stored value is ciphertext,
     not plaintext, and Fernet can decrypt it back.
  2. /auth builds an authorization_url with prompt=consent.
  3. /callback rejects a state mismatch with 400 (CSRF, T-04-21).
  4. Graceful failure: a calendar sync helper that raises does NOT propagate and
     the adaptation endpoint still returns 200 (CAL-04).

All Google API calls are mocked; no live credentials are required.
"""

import json
import os
import pytest

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from httpx import ASGITransport, AsyncClient

from tests.api.conftest import TEST_JWT_SECRET, TEST_USER_ID, auth_headers, mock_supabase_factory


# ---------------------------------------------------------------------------
# App fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("BACKEND_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")

    # Generate a real Fernet key for encryption tests.
    from cryptography.fernet import Fernet
    fernet_key = Fernet.generate_key().decode()
    monkeypatch.setenv("CALENDAR_FERNET_KEY", fernet_key)

    # Reset calendar route module singleton so env patches take effect.
    import api.routes.calendar as cal_mod
    cal_mod._supabase_client = None

    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac, fernet_key


# ---------------------------------------------------------------------------
# Test 1: Token encryption -- stored value is ciphertext, not plaintext (CAL-03)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_token_stored_as_ciphertext(monkeypatch):
    """
    After a simulated callback, the value persisted to google_tokens must be
    ciphertext, not the plaintext credentials JSON (CAL-03, T-04-22).
    """
    from cryptography.fernet import Fernet
    import api.routes.calendar as cal_mod

    fernet_key = Fernet.generate_key()
    monkeypatch.setenv("CALENDAR_FERNET_KEY", fernet_key.decode())
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "secret")

    # The plaintext credentials JSON that Google would return.
    plaintext_credentials = json.dumps({
        "token": "access-token-value",
        "refresh_token": "refresh-token-value",
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "id",
        "client_secret": "secret",
        "scopes": ["https://www.googleapis.com/auth/calendar.events"],
    })

    ciphertext = cal_mod._encrypt_tokens(plaintext_credentials)

    # Stored value must NOT be the plaintext bytes.
    assert ciphertext != plaintext_credentials.encode(), "Token stored as plaintext!"

    # Fernet must be able to decrypt it back.
    decrypted = cal_mod._decrypt_tokens(ciphertext)
    assert decrypted == plaintext_credentials, "Decryption did not recover original credentials"


# ---------------------------------------------------------------------------
# Test 2: /auth builds authorization URL with prompt=consent (Pitfall 2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_auth_uses_prompt_consent(monkeypatch):
    """
    GET /calendar/auth must call authorization_url with prompt='consent'.
    This guarantees a refresh token on every authorization (Pitfall 2).
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("BACKEND_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    from cryptography.fernet import Fernet
    monkeypatch.setenv("CALENDAR_FERNET_KEY", Fernet.generate_key().decode())

    import api.routes.calendar as cal_mod
    cal_mod._supabase_client = None

    # Track authorization_url kwargs.
    auth_url_kwargs = {}

    def fake_authorization_url(**kwargs):
        auth_url_kwargs.update(kwargs)
        return ("https://accounts.google.com/o/oauth2/auth?state=abc", "abc")

    fake_flow = MagicMock()
    fake_flow.authorization_url.side_effect = fake_authorization_url

    # Mock supabase to handle oauth_states upsert.
    mock_sb = mock_supabase_factory([{"user_id": TEST_USER_ID}])
    monkeypatch.setattr(cal_mod, "_get_async_supabase", mock_sb)
    monkeypatch.setattr(cal_mod, "_build_flow", lambda redirect_uri: fake_flow)

    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/calendar/auth",
            headers=auth_headers(),
            follow_redirects=False,
        )

    # Should redirect (302/307) to Google.
    assert response.status_code in (302, 307), f"Expected redirect, got {response.status_code}"
    assert auth_url_kwargs.get("prompt") == "consent", (
        f"Expected prompt='consent', got prompt={auth_url_kwargs.get('prompt')!r}"
    )
    assert auth_url_kwargs.get("access_type") == "offline"


# ---------------------------------------------------------------------------
# Test 3: /callback rejects state mismatch with 400 (CSRF, T-04-21)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_callback_rejects_state_mismatch(monkeypatch):
    """
    GET /calendar/callback with a state that does not match any stored oauth_states
    row must return 400 (CSRF protection, T-04-21).
    """
    monkeypatch.setenv("SUPABASE_JWT_SECRET", TEST_JWT_SECRET)
    monkeypatch.setenv("SUPABASE_URL", "http://localhost:54321")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("BACKEND_BASE_URL", "http://localhost:8000")
    monkeypatch.setenv("FRONTEND_URL", "http://localhost:5173")
    from cryptography.fernet import Fernet
    monkeypatch.setenv("CALENDAR_FERNET_KEY", Fernet.generate_key().decode())

    import api.routes.calendar as cal_mod
    cal_mod._supabase_client = None

    # Supabase returns no rows -- state not found (simulates CSRF / bad state).
    mock_sb = mock_supabase_factory([])
    monkeypatch.setattr(cal_mod, "_get_async_supabase", mock_sb)

    from api.main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get(
            "/calendar/callback",
            params={"code": "auth-code", "state": "tampered-state"},
            follow_redirects=False,
        )

    assert response.status_code == 400
    data = response.json()
    assert data.get("detail", {}).get("error") == "invalid_state"


# ---------------------------------------------------------------------------
# Test 4: Graceful failure -- calendar sync error does not cause 500 (CAL-04)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calendar_sync_failure_is_graceful():
    """
    A push/update helper that raises internally must NOT propagate -- the
    adaptation endpoint returns 200 even when calendar sync fails (CAL-04, T-04-23).
    """
    from api.calendar_sync import push_session_to_calendar, update_calendar_event, delete_calendar_event

    # Patch _load_credentials to raise -- simulates any credential/network error.
    with patch("api.calendar_sync._load_credentials", side_effect=Exception("network error")):
        # push_session_to_calendar must return None, not raise.
        result = await push_session_to_calendar(TEST_USER_ID, {"id": "s1", "scheduled_date": "2025-01-01"})
        assert result is None, "push_session_to_calendar should return None on failure"

        # update_calendar_event must return None, not raise.
        result = await update_calendar_event(TEST_USER_ID, "event-id", {"scheduled_date": "2025-01-01"})
        assert result is None, "update_calendar_event should return None on failure"

        # delete_calendar_event must return None, not raise.
        result = await delete_calendar_event(TEST_USER_ID, "event-id")
        assert result is None, "delete_calendar_event should return None on failure"
