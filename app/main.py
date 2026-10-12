"""QuoteMate - WhatsApp Sales and Quotation Assistant.

FastAPI main entry point for API routing and health checks.
"""

from datetime import datetime, timezone
from fastapi import FastAPI

app = FastAPI(
    title="QuoteMate API",
    description="AI-powered WhatsApp Sales and Quotation Assistant for Cerevyn Solutions PS05",
    version="0.1.0",
)


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
