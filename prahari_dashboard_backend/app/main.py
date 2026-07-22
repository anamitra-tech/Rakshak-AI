import os
import sys

# Real AI/ML logic (ml/, graph/, dashboard/, llm/, data/) lives at the repo
# root, two levels above this file (repo_root/prahari_dashboard_backend/app/
# main.py) -- not inside this FastAPI project. Add it to sys.path so
# app.services.classifier / app.services.graph can import those packages
# regardless of the process's cwd when uvicorn is launched.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.api import auth, analyze, entities, network, geospatial, report, trends
# chat deliberately NOT imported here: app/services/chat.py -> bot.agent pulls
# in the RAG stack (FlagEmbedding/BAAI-bge-m3 + faiss-cpu + torch), which
# won't fit Render free tier's 512MB RAM (same constraint documented in
# render.yaml for webhook.app's /chat). Importing the module at all -- even
# without ever calling the route -- would trigger that load at startup, so
# the import itself is commented out, not just the route registration.
from app.db.users_db import init_db

app = FastAPI(title="Prahari API", version="0.1.0")


@app.on_event("startup")
def on_startup():
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Consistent error shape across all endpoints, matching the API contract doc:
# { "error": true, "code": "...", "message": "..." }
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": True, "code": "internal_error", "message": str(exc)},
    )


app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(entities.router, prefix="/api", tags=["entities"])
app.include_router(report.router, prefix="/api/citizen", tags=["citizen"])
app.include_router(network.router, prefix="/api/network", tags=["network"])
app.include_router(geospatial.router, prefix="/api/geo", tags=["geospatial"])
app.include_router(trends.router, prefix="/api", tags=["trends"])
# /api/chat intentionally not registered -- see the commented-out import above.


@app.get("/api/health")
def health_check():
    """Quick way to confirm the backend is up."""
    return {"status": "ok"}


# --- Serve the built React dashboard from this same service/origin -------
# Deployed as one Render web service: the Vite build output (prahari_dashboard_
# frontend/dist, built in the Docker build stage) is served alongside the API
# so the frontend's hardcoded relative fetch('/api/...') calls just work with
# no CORS/cross-origin cookie handling needed (same origin as the API).
_FRONTEND_DIST = os.path.join(_REPO_ROOT, "prahari_dashboard_frontend", "dist")
if os.path.isdir(_FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(_FRONTEND_DIST, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        candidate = os.path.join(_FRONTEND_DIST, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_FRONTEND_DIST, "index.html"))
