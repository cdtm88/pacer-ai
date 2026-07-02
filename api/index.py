import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from backend.main import app as _backend_app  # noqa: E402

# Vercel zero-config ASGI entry point (api/index.py → /api/*).
# Mounts the backend at /api so Vercel's function routing coexists with
# the React SPA at /* → index.html.
app = FastAPI()
app.mount("/api", _backend_app)

logger = logging.getLogger(__name__)

# Resolve the built frontend directory. Under Vercel's fastapi Framework
# Preset every non-API request is routed to this function, so FastAPI must
# serve the built SPA itself; vercel.json rewrites are ignored for non-API
# paths. The runtime cwd/layout under Vercel is uncertain, so try a couple
# of candidate locations relative to the repo root and the process cwd.
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIST_CANDIDATES = [
    os.path.join(REPO_ROOT, "frontend", "dist"),
    os.path.join(os.getcwd(), "frontend", "dist"),
]
DIST = next((c for c in _DIST_CANDIDATES if os.path.isdir(c)), None)

if DIST:
    logger.info("SPA static dir resolved: %s", DIST)
else:
    logger.warning(
        "SPA static dir NOT FOUND. Searched candidates: %s", _DIST_CANDIDATES
    )

if DIST and os.path.isdir(os.path.join(DIST, "assets")):
    app.mount(
        "/assets", StaticFiles(directory=os.path.join(DIST, "assets")), name="assets"
    )


@app.get("/{full_path:path}")
async def spa(full_path: str):
    if not DIST:
        return JSONResponse(
            status_code=503,
            content={
                "error": "SPA build directory not found",
                "searched": _DIST_CANDIDATES,
            },
        )

    candidate = os.path.normpath(os.path.join(DIST, full_path))
    is_safe = os.path.commonpath([DIST, candidate]) == DIST

    if is_safe and full_path and os.path.isfile(candidate):
        return FileResponse(candidate)

    return FileResponse(os.path.join(DIST, "index.html"))
