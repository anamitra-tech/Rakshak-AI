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
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.api import auth, analyze, entities, network, geospatial, report, trends
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


@app.get("/api/health")
def health_check():
    """Quick way to confirm the backend is up."""
    return {"status": "ok"}
