"""QuoteMate - WhatsApp Sales and Quotation Assistant.

FastAPI main entry point for API routing, health checks, and application lifespan.
"""

import logging
import os as _os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes import router as api_router
from app.database import SessionLocal, init_db
from app.services.catalogue_service import catalogue_service

# Structured logging: a single-line key=value format so log aggregators
# (and humans) can grep by message_id / sender_id.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("quotemate")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager: initializes database and seeds products on startup."""
    init_db()
    catalogue_service.seed_catalogue_if_empty()
    yield


app = FastAPI(
    title="QuoteMate API",
    description="AI-powered WhatsApp Sales and Quotation Assistant for Cerevyn Solutions PS05",
    version="0.2.0",
    lifespan=lifespan,
)


# --- Global JSON error handling ----------------------------------------------
# Clients always receive structured JSON; internal tracebacks are logged
# server-side only and never leak into HTTP responses.

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return Pydantic validation failures as a clean 422 JSON envelope."""
    errors = [
        {
            "field": ".".join(str(part) for part in err.get("loc", []) if part != "body"),
            "message": err.get("msg", "Invalid value."),
        }
        for err in exc.errors()
    ]
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "Request validation failed.", "errors": errors},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all: log the full traceback server-side, return generic JSON 500."""
    logger.exception(
        "unhandled_error path=%s method=%s error=%s",
        request.url.path,
        request.method,
        type(exc).__name__,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error. The incident has been logged.",
        },
    )


# Smallest justified CORS change: the frontend runs on a different origin than
# this API (Vite dev server on :5173 by default vs API on :8000), so browsers
# block cross-origin requests without this middleware. Allowed origins are
# controlled by the CORS_ORIGINS env var (comma-separated) and default to the
# local Vite dev server only. No credentials other than same-origin cookies are
# needed; allow_credentials=True keeps the preflight response explicit.
_cors_origins = _os.getenv("CORS_ORIGINS", "http://localhost:5173")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/", summary="Root status and service info")
def read_root():
    """Return basic metadata about the QuoteMate service."""
    return {
        "service": "QuoteMate",
        "description": "WhatsApp Sales and Quotation Assistant",
        "status": "online",
        "version": "0.2.0",
        "docs_url": "/docs",
    }


@app.get("/health", summary="Service health check")
def health_check():
    """Return health status and current UTC timestamp."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "QuoteMate",
        "version": "0.2.0",
    }


@app.get("/ready", summary="Readiness check (includes database probe)")
def readiness_check():
    """Readiness probe: verifies the application can execute a DB round-trip.

    Returns 200 with database='ok' when the connection works; 503 otherwise.
    Used by Azure App Service Health Check / container probes and CI smoke tests.
    """
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return {
            "status": "ready",
            "database": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as err:  # pragma: no cover - exercised via unit test with broken engine
        logger.error("readiness_failed error=%s", type(err).__name__)
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "unavailable",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
