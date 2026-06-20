# api/auth.py
"""
JWT authentication dependency for PacerAI (D-03, T-04-02).

Exports `get_current_user`, a FastAPI Depends() callable that verifies the
Supabase JWT from either the Authorization Bearer header or a ?token= query
param (SSE fallback -- EventSource cannot send headers; see Pitfall 1).

Security requirements enforced:
  - HS256 algorithm only (T-04-02)
  - audience="authenticated" required (Supabase issues this claim; T-04-02)
  - Secret is read from SUPABASE_JWT_SECRET env var, never the anon key (Pitfall 6)
  - Missing or invalid token -> HTTP 401 with structured error detail
  - Valid token returns {"user_id": payload["sub"], "email": payload.get("email")}

Usage:
    from api.auth import get_current_user
    from fastapi import Depends

    @router.get("/")
    async def my_endpoint(current_user: dict = Depends(get_current_user)):
        user_id = current_user["user_id"]

SSE usage (token in query string because EventSource cannot send headers):
    GET /chat/stream?conversation_id=...&token=<jwt>
"""

import os

import jwt
from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# ---------------------------------------------------------------------------
# JWT dependency
# ---------------------------------------------------------------------------


async def get_current_user(
    cred: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False)),
    token: str | None = Query(None),  # SSE fallback: ?token= query param (Pitfall 1)
) -> dict:
    """
    Verify a Supabase JWT and return the authenticated user's identity.

    Accepts the JWT from:
      1. Authorization: Bearer <jwt>  (standard REST requests)
      2. ?token=<jwt>                 (SSE endpoints; EventSource cannot send headers)

    Args:
        cred:  HTTPBearer credential extracted from the Authorization header.
               auto_error=False means FastAPI does NOT raise on missing header;
               we handle that case below to produce a structured 401 error.
        token: Optional ?token= query param for SSE clients.

    Returns:
        {"user_id": str, "email": str | None}

    Raises:
        HTTPException 401 if the token is missing, malformed, expired, or
        signed with the wrong secret / wrong audience.
    """
    # Prefer Authorization header; fall back to ?token= for SSE clients.
    raw = cred.credentials if cred else token
    if not raw:
        raise HTTPException(
            status_code=401,
            detail={"error": "unauthorized", "detail": "Missing authentication token"},
        )

    # Read secret at call time (not at module import) so the env var can be
    # injected by tests via monkeypatch.setenv without import-order issues.
    secret = os.environ.get("SUPABASE_JWT_SECRET")
    if not secret:
        raise HTTPException(
            status_code=500,
            detail={"error": "server_error", "detail": "SUPABASE_JWT_SECRET not configured"},
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
