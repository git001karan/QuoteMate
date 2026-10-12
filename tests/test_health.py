"""Test cases for root and health check endpoints."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_read_root():
    """Verify that GET / returns 200 and expected metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "QuoteMate"
    assert data["status"] == "online"
    assert "version" in data
    assert data["docs_url"] == "/docs"


def test_health_check():
    """Verify that GET /health returns 200 and healthy status."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "QuoteMate"
    assert "timestamp" in data


def test_openapi_docs_endpoint():
    """Verify that OpenAPI schema and documentation endpoints are reachable."""
    docs_response = client.get("/docs")
    assert docs_response.status_code == 200

    openapi_response = client.get("/openapi.json")
    assert openapi_response.status_code == 200
    openapi_data = openapi_response.json()
    assert openapi_data["info"]["title"] == "QuoteMate API"
