import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from backend.main import app as _backend_app  # noqa: E402

# Vercel zero-config ASGI entry point (api/index.py → /api/*).
# Mounts the backend at /api so Vercel's function routing coexists with
# the React SPA at /* → index.html.
app = FastAPI()
app.mount("/api", _backend_app)
