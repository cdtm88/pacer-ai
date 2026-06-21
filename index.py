import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from api.main import app  # noqa: F401, E402  — re-exported for Vercel ASGI handler
