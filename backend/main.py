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

import os

from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.adaptations import router as adaptations_router
from backend.routes.calendar import router as calendar_router
from backend.routes.chat import conversations_router, router as chat_router
from backend.routes.onboarding import router as onboarding_router
from backend.routes.rides import router as rides_router
from backend.routes.sessions import router as sessions_router

app = FastAPI(
    title="PacerAI",
    description=(
        "Evidence-based adaptive AI cycling coach backend. "
        "Provides SSE streaming for multi-turn coaching conversations."
    ),
    version="0.1.0",
)

_frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:5173")
_allowed_origins = [o.strip() for o in _frontend_url.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the chat router.
# All chat endpoints live at /chat/... (e.g. GET /chat/stream).
app.include_router(chat_router, prefix="/chat", tags=["chat"])

# Mount the onboarding router.
# Onboarding endpoints live at /onboarding/... (e.g. POST /onboarding/start).
app.include_router(onboarding_router, prefix="/onboarding", tags=["onboarding"])

# Mount the rides router.
# Ride upload endpoints live at /rides/... (e.g. POST /rides/upload, GET /rides/).
app.include_router(rides_router, prefix="/rides", tags=["rides"])

# Mount the adaptations router.
# Adaptation endpoints live at /adaptations/... (e.g. GET /adaptations/, POST /adaptations/check).
app.include_router(adaptations_router, prefix="/adaptations", tags=["adaptations"])

# Mount the sessions router with no prefix -- handlers use full absolute paths:
#   GET /sessions/today, GET /sessions/upcoming, GET /pmc_history/latest, GET /profiles/me
app.include_router(sessions_router, tags=["sessions"])

# Mount the conversations router with no prefix -- handler path is /conversations/
#   POST /conversations/
app.include_router(conversations_router, tags=["conversations"])

# Mount the calendar router.
# Calendar endpoints live at /calendar/... (e.g. GET /calendar/auth, GET /calendar/settings).
app.include_router(calendar_router, prefix="/calendar", tags=["calendar"])


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Liveness check: returns 200 with status OK if the app is running."""
    return {"status": "ok"}
