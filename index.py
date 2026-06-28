import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from backend.main import app as _backend_app  # noqa: E402

# Vercel ASGI entry point.
# Mounts the backend at /api so the rewrite "/api/(.*) -> index.py" coexists
# with the React SPA at "/(.*) -> index.html".
# Vite proxy in dev strips /api before forwarding to localhost:8000, keeping
# the backend dev server prefix-free (uvicorn backend.main:app).
app = FastAPI()
app.mount("/api", _backend_app)
