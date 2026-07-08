# api/routes/calendar.py
"""
Google Calendar OAuth2 integration for PacerAI (CAL-01 through CAL-04).

Endpoints:
  GET  /calendar/auth        -- build OAuth2 authorization URL, redirect to Google (CAL-01)
  GET  /calendar/callback    -- exchange code for tokens, encrypt, store in users.google_tokens
  GET  /calendar/settings    -- return {"connected": bool} for the Settings UI (D-04)
  POST /calendar/disconnect  -- clear google_tokens for the user

Security (CAL-03, T-04-21, T-04-22, T-04-24):
  - SCOPES uses calendar.events only (least privilege, T-04-24)
  - access_type=offline + prompt=consent guarantees a refresh token every time (Pitfall 2)
  - OAuth state parameter stored server-side in Supabase oauth_states table (T-04-21, CSRF)
  - Tokens encrypted with Fernet (authenticated AES) before storage; never plaintext (T-04-22)
  - Token values never logged

Architecture (stub mode):
  - All env vars read at call time, not module import, so tests can monkeypatch safely.
  - Google API calls wrapped in asyncio.to_thread (Pitfall 4: google-auth is synchronous).
  - Graceful no-op when env vars absent (CAL-04 principle).
"""

import asyncio
import hashlib
import hmac
import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse

from backend.auth import get_current_user
from backend.db import get_async_supabase as _get_async_supabase

logger = logging.getLogger(__name__)

router = APIRouter()

# Google Calendar scope -- least privilege (T-04-24).
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]


# ---------------------------------------------------------------------------
# Fernet helper -- lazy init so tests can monkeypatch CALENDAR_FERNET_KEY
# ---------------------------------------------------------------------------


def _get_fernet():
    """
    Return a Fernet instance initialised from CALENDAR_FERNET_KEY env var.

    Raises RuntimeError when the key is absent so the caller can surface a
    structured 500 instead of a cryptic AttributeError.
    """
    from cryptography.fernet import Fernet

    key = os.environ.get("CALENDAR_FERNET_KEY")
    if not key:
        raise RuntimeError("CALENDAR_FERNET_KEY env var is not set")
    return Fernet(key.encode() if isinstance(key, str) else key)


def _encrypt_tokens(credentials_json: str) -> bytes:
    """Encrypt credentials JSON string with Fernet (authenticated AES). CAL-03."""
    return _get_fernet().encrypt(credentials_json.encode())


def _decrypt_tokens(ciphertext: bytes) -> str:
    """Decrypt Fernet ciphertext back to credentials JSON. CAL-03."""
    return _get_fernet().decrypt(ciphertext).decode()


# ---------------------------------------------------------------------------
# OAuth Flow builder
# ---------------------------------------------------------------------------


def _build_flow(redirect_uri: str):
    """
    Build a google_auth_oauthlib Flow from env-var client config.

    Reads GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET at call time.
    Returns None when either is absent (stub mode / env not configured).
    """
    from google_auth_oauthlib.flow import Flow  # type: ignore[import-untyped]

    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    if not client_id or not client_secret:
        return None

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    flow = Flow.from_client_config(client_config, scopes=SCOPES)
    flow.redirect_uri = redirect_uri
    return flow


# ---------------------------------------------------------------------------
# Credential loader (shared by calendar_sync.py)
# ---------------------------------------------------------------------------


async def _load_credentials(user_id: str):
    """
    Load, decrypt, and return a google.oauth2.credentials.Credentials object
    for the given user, or None if no tokens are stored.
    """
    from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]

    supabase = await _get_async_supabase()
    result = await (
        supabase.table("users")
        .select("google_tokens")
        .eq("id", user_id)
        .execute()
    )
    rows = result.data or []
    if not rows or not rows[0].get("google_tokens"):
        return None

    raw = rows[0]["google_tokens"]
    # raw may be bytes (Fernet output) or a string (already bytes-decoded at storage)
    if isinstance(raw, str):
        raw = raw.encode()
    credentials_json = _decrypt_tokens(raw)
    return Credentials.from_authorized_user_json(credentials_json)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


def _build_oauth_state(user_id: str) -> str:
    """
    Build a HMAC-signed OAuth state parameter embedding the user_id (CR-007).

    Format: "{nonce}.{user_id}.{hmac_hex}"

    The HMAC binds the nonce to the user_id using SUPABASE_JWT_SECRET so that
    an attacker who observes the state value cannot substitute a different user_id
    at the callback. The callback verifies the HMAC before trusting the user_id.
    """
    secret = os.environ.get("SUPABASE_JWT_SECRET", "")
    nonce = secrets.token_urlsafe(32)
    sig = hmac.new(
        secret.encode(),
        f"{nonce}:{user_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{nonce}.{user_id}.{sig}"


@router.get("/auth-redirect-url")
async def calendar_auth_redirect_url(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Return the Google OAuth2 authorization URL as JSON without performing a redirect.

    The frontend calls this endpoint with the JWT in the Authorization header (safe),
    then redirects the browser to the returned URL. This keeps the access token out of
    the browser URL bar, server access logs, CDN logs, and Referer headers (CR-002).

    Returns:
        {"url": <google_oauth_url>}
    """
    user_id = current_user["user_id"]
    backend_base = os.environ.get("BACKEND_BASE_URL")
    if not backend_base:
        raise HTTPException(
            status_code=503,
            detail={"error": "server_misconfigured", "detail": "BACKEND_BASE_URL must be set"},
        )
    redirect_uri = f"{backend_base}/calendar/callback"

    flow = _build_flow(redirect_uri)
    if flow is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "not_configured",
                "detail": "Google OAuth credentials are not configured on this server",
            },
        )

    # Generate HMAC-signed state embedding user_id (CR-007, T-04-21).
    state = _build_oauth_state(user_id)
    supabase = await _get_async_supabase()
    # Store only the nonce (first segment) keyed to user_id for CSRF tracking.
    nonce = state.split(".")[0]
    await supabase.table("oauth_states").upsert(
        {"user_id": user_id, "state": nonce}
    ).execute()

    auth_url, _returned_state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=state,
    )
    return {"url": auth_url}


@router.get("/auth")
async def calendar_auth(
    current_user: dict = Depends(get_current_user),
) -> RedirectResponse:
    """
    Build the Google OAuth2 authorization URL and redirect the user to Google.

    Security (T-04-21): generates a random `state` token, stores it in the
    oauth_states table keyed to user_id so the callback can verify CSRF.

    OAuth params:
      - access_type=offline: guarantees a refresh token is returned
      - prompt=consent: forces the consent screen every time so the refresh
        token is never omitted for previously-consented users (Pitfall 2)
      - scope: calendar.events only (least privilege, T-04-24)
    """
    user_id = current_user["user_id"]
    backend_base = os.environ.get("BACKEND_BASE_URL")
    if not backend_base:
        raise HTTPException(
            status_code=503,
            detail={"error": "server_misconfigured", "detail": "BACKEND_BASE_URL must be set"},
        )
    redirect_uri = f"{backend_base}/calendar/callback"

    flow = _build_flow(redirect_uri)
    if flow is None:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "not_configured",
                "detail": "Google OAuth credentials are not configured on this server",
            },
        )

    # Generate HMAC-signed state embedding user_id (CR-007, T-04-21).
    state = _build_oauth_state(user_id)
    supabase = await _get_async_supabase()
    # Store only the nonce (first segment) keyed to user_id for CSRF tracking.
    nonce = state.split(".")[0]
    await supabase.table("oauth_states").upsert(
        {"user_id": user_id, "state": nonce}
    ).execute()

    auth_url, _returned_state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
        state=state,
    )
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def calendar_callback(
    code: str = Query(...),
    state: str = Query(...),
) -> RedirectResponse:
    """
    Handle the Google OAuth2 callback.

    Verifies the CSRF state, exchanges the authorization code for tokens,
    encrypts the credentials with Fernet, and upserts into users.google_tokens.
    Tokens are never logged (CAL-03, T-04-22).
    """
    frontend_url = os.environ.get("FRONTEND_URL")
    backend_base = os.environ.get("BACKEND_BASE_URL")
    if not frontend_url or not backend_base:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "server_misconfigured",
                "detail": "FRONTEND_URL and BACKEND_BASE_URL must be set",
            },
        )
    redirect_uri = f"{backend_base}/calendar/callback"

    # --- CSRF state verification with HMAC binding (CR-007, T-04-21) ---
    # State format: "{nonce}.{user_id}.{hmac_hex}"
    parts = state.split(".")
    if len(parts) != 3:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_state", "detail": "Malformed OAuth state parameter"},
        )
    nonce, claimed_user_id, received_sig = parts

    # Verify HMAC to ensure state was issued by this server for this user_id.
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise HTTPException(
            status_code=500,
            detail={"error": "server_misconfigured", "detail": "SUPABASE_JWT_SECRET is required"},
        )
    expected_sig = hmac.new(
        secret.encode(),
        f"{nonce}:{claimed_user_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(received_sig, expected_sig):
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_state", "detail": "OAuth state HMAC verification failed"},
        )

    # Verify the nonce was issued by this server (anti-replay, T-04-21).
    supabase = await _get_async_supabase()
    state_result = await (
        supabase.table("oauth_states")
        .select("user_id")
        .eq("state", nonce)
        .eq("user_id", claimed_user_id)
        .execute()
    )
    rows = state_result.data or []
    if not rows:
        raise HTTPException(
            status_code=400,
            detail={"error": "invalid_state", "detail": "OAuth state mismatch; possible CSRF"},
        )
    user_id = claimed_user_id

    # --- Token exchange (synchronous google-auth wrapped in asyncio.to_thread, Pitfall 4) ---
    flow = _build_flow(redirect_uri)
    if flow is None:
        raise HTTPException(
            status_code=503,
            detail={"error": "not_configured", "detail": "Google OAuth credentials not configured"},
        )

    def _exchange_code() -> str:
        flow.fetch_token(code=code)
        return flow.credentials.to_json()

    credentials_json = await asyncio.to_thread(_exchange_code)

    # --- Encrypt and store tokens (CAL-03, T-04-22 -- never store plaintext) ---
    ciphertext = _encrypt_tokens(credentials_json)
    # Store as string (base64-encoded Fernet output is safe ASCII).
    ciphertext_str = ciphertext.decode()

    await supabase.table("users").upsert(
        {"id": user_id, "google_tokens": ciphertext_str}
    ).execute()

    # Clear the consumed nonce (T-04-21 cleanup).
    await supabase.table("oauth_states").delete().eq("state", nonce).execute()

    return RedirectResponse(url=f"{frontend_url}/settings?calendar=connected")


@router.get("/settings")
async def calendar_settings(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Return Google Calendar connection status for the Settings UI (D-04).

    Returns {"connected": bool}.
    """
    user_id = current_user["user_id"]
    supabase = await _get_async_supabase()
    result = await (
        supabase.table("users")
        .select("google_tokens")
        .eq("id", user_id)
        .execute()
    )
    rows = result.data or []
    if not rows or not rows[0].get("google_tokens"):
        return {"connected": False}

    # Decrypt and verify refresh token health.
    try:
        raw = rows[0]["google_tokens"]
        if isinstance(raw, str):
            raw = raw.encode()
        credentials_json = _decrypt_tokens(raw)
        import json as _json
        parsed = _json.loads(credentials_json)
        connected = bool(parsed.get("refresh_token"))
    except Exception:
        connected = False

    return {"connected": connected}


@router.post("/disconnect")
async def calendar_disconnect(
    current_user: dict = Depends(get_current_user),
) -> dict:
    """
    Disconnect Google Calendar by clearing the stored tokens.

    Sets users.google_tokens to null for the current user.
    """
    user_id = current_user["user_id"]
    supabase = await _get_async_supabase()
    await supabase.table("users").update(
        {"google_tokens": None}
    ).eq("id", user_id).execute()
    return {}
