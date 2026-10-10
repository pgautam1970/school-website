"""FastAPI application: API, secure dashboard shell, scheduler lifecycle."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import routes_admin, routes_auth, routes_reports, routes_sources
from .config import get_settings
from .db import SessionLocal, init_db
from .scheduler import start_scheduler, stop_scheduler
from .services import ensure_bootstrap

logging.basicConfig(level=logging.INFO, format='{"ts":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s","msg":"%(message)s"}')
STATIC = Path(__file__).parent / "static"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.env == "production" and not s.secret_key_is_strong:
        raise RuntimeError("KVI_SECRET_KEY must be a random value of at least 32 characters in production.")
    init_db()
    with SessionLocal() as db:
        ensure_bootstrap(db)
    start_scheduler()
    yield
    stop_scheduler()


def create_app() -> FastAPI:
    app = FastAPI(title="KVI AI School Intelligence & Daily Reporting Agent",
                  version="1.0.0", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):
        # CSRF hardening: state-changing API calls must carry a custom header that
        # browsers will not send cross-site without a CORS preflight.
        if request.url.path.startswith("/api/") and request.method not in SAFE_METHODS:
            if request.headers.get("x-requested-with") != "kvi-dashboard":
                return JSONResponse({"detail": "Missing X-Requested-With header"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app.include_router(routes_auth.router)
    app.include_router(routes_sources.router)
    app.include_router(routes_reports.router)
    app.include_router(routes_admin.router)

    app.mount("/static", StaticFiles(directory=STATIC), name="static")

    @app.get("/", include_in_schema=False)
    def dashboard_index():
        return FileResponse(STATIC / "index.html", media_type="text/html")

    return app


app = create_app()
