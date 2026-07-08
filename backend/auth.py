# api/auth.py
"""
JWT authentication dependency for PacerAI (D-03, T-04-02).

Exports `get_current_user`, a FastAPI Depends() callable that verifies the
Supabase JWT from either the Authorization Bearer header or a ?token= query
param (SSE fallback -- EventSource cannot send headers; see Pitfall 1).

Newer Supabase projects issue ES256 (ECDSA) tokens verified via JWKS.
Older projects use HS256 with SUPABASE_JWT_SECRET. Both are supported:
  - ES256 path: JWKS fetched from SUPABASE_URL/auth/v1/.well-known/jwks.json
  - HS256 path: SUPABASE_JWT_SECRET env var (fallback for legacy projects)

Security requirements enforced:
  - ES256 or HS256 algorithms only
  - audience="authenticated" required (Supabase issues this claim; T-04-02)
  - Missing or invalid token -> HTTP 401 with structured error detail
  - Valid token returns {"user_id": payload["sub"], "email": payload.get("email")}

Usage:
    from backend.auth import get_current_user
    from fastapi import Depends

    @router.get("/")
    async def my_endpoint(current_user: dict = Depends(get_current_user)):
        user_id = current_user["user_id"]

SSE usage (token in query string because EventSource cannot send headers):
    GET /chat/stream?conversation_id=...&token=<jwt>
"""

import os

import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# ---------------------------------------------------------------------------
# JWKS client (cached singleton -- fetches public keys on first use)
# ---------------------------------------------------------------------------

_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient | None:
    global _jwks_client
    supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    if not supabase_url:
        return None
    if _jwks_client is None:
        jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


# ---------------------------------------------------------------------------
# JWT dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    # WR-006 (item 5, D-04): The ?token= query param fallback is required for
    # SSE clients (EventSource cannot send Authorization headers). Full Supabase
    # JWTs previously appeared in server access logs for SSE endpoints. This is
    # now mitigated -- POST /chat/token issues a short-lived (~60s) namespaced
    # sse_token (see the verify branch below), and sseUrl() carries only that
    # ephemeral token, limiting the exposure window in logs to ~60s.
    token: str | None = Query(None),  # SSE fallback: ?token= query param (Pitfall 1)
) -> dict:
    """
    Verify a Supabase JWT and return the authenticated user's identity.

    Accepts the JWT from:
      1. Authorization: Bearer <jwt>  (standard REST requests)
      2. ?token=<jwt>                 (SSE endpoints; EventSource cannot send headers)

    Tries ES256 via JWKS first (new Supabase projects), then falls back to
    HS256 with SUPABASE_JWT_SECRET (legacy projects).

    Returns:
        {"user_id": str, "email": str | None}

    Raises:
        HTTPException 401 if the token is missing, malformed, expired, or fails
        both verification paths.
    """
    raw = cred.credentials if cred else token
    if not raw:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "detail": "Missing authentication token"},
        )

    # --- Ephemeral SSE-token verify path (item 5, D-04; T-10-03-01/02) ---
    # Query-param path ONLY -- never attempted for the Authorization header.
    # Uses a dedicated SSE_TOKEN_SECRET (never SUPABASE_JWT_SECRET) and the
    # typ=="sse_token" claim as a namespace guard so a real Supabase JWT can
    # never be misinterpreted as one, and vice versa (T-10-03-02). On any
    # failure (wrong secret, expired, missing typ claim), fall through
    # unchanged to the existing ES256/HS256 Supabase verification below.
    if token and not cred:
        sse_secret = os.environ.get("SSE_TOKEN_SECRET")
        if sse_secret:
            try:
                sse_payload = jwt.decode(
                    token,
                    sse_secret,
                    algorithms=["HS256"],
                    audience="authenticated",
                )
                if sse_payload.get("typ") == "sse_token":
                    return {"user_id": sse_payload["sub"], "email": None}
            except jwt.PyJWTError:
                pass  # not an sse_token (or expired) -- fall through to Supabase verification

    # --- ES256 path via JWKS (preferred for new Supabase projects) ---
    jwks_client = _get_jwks_client()
    if jwks_client is not None:
        try:
            signing_key = jwks_client.get_signing_key_from_jwt(raw)
            payload = jwt.decode(
                raw,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                audience="authenticated",
            )
            return {"user_id": payload["sub"], "email": payload.get("email")}
        except jwt.PyJWTError:
            pass  # fall through to HS256 path

    # --- HS256 path via SUPABASE_JWT_SECRET (legacy projects) ---
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise HTTPException(
            status_code=500,
            detail={"error": "server_error", "detail": "No valid auth configuration (SUPABASE_URL or SUPABASE_JWT_SECRET required)"},
        )

    try:
        payload = jwt.decode(
            raw,
            secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "detail": f"Invalid token: {exc}"},
        ) from exc

    return {
        "user_id": payload["sub"],
        "email": payload.get("email"),
    }
