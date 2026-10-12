"""Pytest configuration and session fixtures for QuoteMate."""

import pytest
from app.database import init_db
from app.services.catalogue_service import catalogue_service


@pytest.fixture(autouse=True, scope="session")
def setup_test_database():
    """Ensure database tables and initial catalogue seed exist during automated test runs."""
    init_db()
    catalogue_service.seed_catalogue_if_empty()
