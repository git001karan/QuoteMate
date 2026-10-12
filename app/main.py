"""QuoteMate - WhatsApp Sales and Quotation Assistant.

FastAPI main entry point for API routing, health checks, and application lifespan.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI

from app.api.routes import router as api_router
from app.database import init_db
from app.services.catalogue_service import catalogue_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager: initializes database and seeds products on startup."""
    init_db()
    catalogue_service.seed_catalogue_if_empty()
    yield


app = FastAPI(
    title="QuoteMate API",
    description="AI-powered WhatsApp Sales and Quotation Assistant for Cerevyn Solutions PS05",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/", summary="Root status and service info")
def read_root():
    """Return basic metadata about the QuoteMate service."""
    return {
        "service": "QuoteMate",
        "description": "WhatsApp Sales and Quotation Assistant",
        "status": "online",
        "version": "0.1.0",
        "docs_url": "/docs",
    }


@app.get("/health", summary="Service health check")
def health_check():
    """Return health status and current UTC timestamp."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "QuoteMate",
        "version": "0.1.0",
    }
