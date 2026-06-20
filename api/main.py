# api/main.py
"""
FastAPI application entry point for PacerAI.

Creates the FastAPI app, mounts the chat router, and exposes a health check
endpoint so the app is verifiably constructable in tests and production.

Architecture (D-01, D-02):
  - api/ is the HTTP transport layer; it imports from agent/ (transport-agnostic).
  - Mounting via include_router keeps routes modular and testable.

Deferred (per CONTEXT.md):
  - Auth middleware: Phase 4 (Supabase JWT verification).
  - Bidirectional transport: AGENT-05 mandates SSE only; no alternate transport.
  - Lifespan for Supabase singleton: Phase 3 (per-request in Phase 2, Open Question 3).
"""

from fastapi import FastAPI

from api.routes.chat import router as chat_router
from api.routes.onboarding import router as onboarding_router

app = FastAPI(
    title="PacerAI",
    description=(
        "Evidence-based adaptive AI cycling coach backend. "
        "Provides SSE streaming for multi-turn coaching conversations."
    ),
    version="0.1.0",
)

# Mount the chat router.
# All chat endpoints live at /chat/... (e.g. GET /chat/stream).
app.include_router(chat_router, prefix="/chat", tags=["chat"])

# Mount the onboarding router.
# Onboarding endpoints live at /onboarding/... (e.g. POST /onboarding/start).
app.include_router(onboarding_router, prefix="/onboarding", tags=["onboarding"])


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Liveness check: returns 200 with status OK if the app is running."""
    return {"status": "ok"}
