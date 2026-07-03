import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from backend.main import app as _backend_app  # noqa: E402

# Vercel `services` entry point for the backend service (vercel.json
# services.backend.entrypoint = "index:app"). Per Vercel's services routing
# model the service receives the ORIGINAL request path -- GET /api/rides
# reaches this service as /api/rides, not /rides -- so this /api mount is
# what strips the prefix for the inner FastAPI routers. The SPA is now
# served by the separate `frontend` static service defined in vercel.json,
# not by this function.
app = FastAPI()
app.mount("/api", _backend_app)
