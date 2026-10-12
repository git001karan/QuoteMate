"""Automated test suite for product catalogue, schemas, and API endpoints."""

import json
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas import Product
from app.services.catalogue_service import (
    CatalogueService,
    CatalogueValidationError,
    ProductNotFoundError,
)

client = TestClient(app)


def test_catalogue_contains_at_least_10_products():
    """Verify that the catalogue loads at least 10 products (assessment requirement)."""
    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) >= 10
    # Our default catalogue defines 12 items
    assert len(products) == 12


def test_each_product_has_required_fields():
    """Verify that every product in the catalogue has all required non-empty fields."""
    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()

    for p in products:
        assert "id" in p and isinstance(p["id"], str) and len(p["id"].strip()) > 0
        assert "name" in p and isinstance(p["name"], str) and len(p["name"].strip()) > 0
        assert "description" in p and isinstance(p["description"], str) and len(p["description"].strip()) > 0
        assert "price" in p and (isinstance(p["price"], (int, float)) or isinstance(p["price"], Decimal))
        assert p["price"] > 0
        assert "stock" in p and isinstance(p["stock"], int) and not isinstance(p["stock"], bool)
        assert p["stock"] >= 0


def test_product_ids_are_unique():
    """Verify that every product ID across the catalogue is unique."""
    response = client.get("/products")
    assert response.status_code == 200
    products = response.json()
    ids = [p["id"] for p in products]
    assert len(ids) == len(set(ids)), "Product IDs must not contain duplicates"


def test_list_products_returns_200():
    """Verify that GET /products returns HTTP 200 and a non-empty list."""
    response = client.get("/products")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) > 0


def test_get_existing_product_returns_correct_details():
    """Verify that GET /products/{product_id} returns the matching product."""
    response = client.get("/products/KB-101")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "KB-101"
    assert data["name"] == "Ergonomic Mechanical Keyboard"
    assert data["price"] == 3499.0
    assert data["stock"] == 25


def test_get_unknown_product_returns_404():
    """Verify that retrieving a non-existent product ID returns HTTP 404."""
    response = client.get("/products/DOES-NOT-EXIST-999")
    assert response.status_code == 404
    error_data = response.json()
    assert "detail" in error_data
    assert "not found" in error_data["detail"].lower()


@pytest.mark.parametrize(
    "invalid_data,expected_error",
    [
        (
            {"id": "TEST-1", "name": "Item", "description": "Desc", "price": -10.0, "stock": 5},
            "greater than 0",
        ),
        (
            {"id": "TEST-2", "name": "Item", "description": "Desc", "price": 0.0, "stock": 5},
            "greater than 0",
        ),
        (
            {"id": "TEST-3", "name": "Item", "description": "Desc", "price": 100.0, "stock": -1},
            "greater than or equal to 0",
        ),
        (
            {"id": "TEST-4", "name": "Item", "description": "Desc", "price": True, "stock": 5},
            "Boolean values are not accepted",
        ),
        (
            {"id": "TEST-5", "name": "Item", "description": "Desc", "price": 100.0, "stock": False},
            "Boolean values are not accepted",
        ),
        (
            {"id": "", "name": "Item", "description": "Desc", "price": 100.0, "stock": 5},
            "non-empty string",
        ),
        (
            {"id": "TEST-6", "name": "   ", "description": "Desc", "price": 100.0, "stock": 5},
            "non-empty string",
        ),
    ],
)
def test_schema_rejects_invalid_values(invalid_data, expected_error):
    """Verify that Pydantic rejects negative prices, negative stock, booleans, and empty strings."""
    with pytest.raises(ValidationError) as exc_info:
        Product.model_validate(invalid_data)
    assert expected_error in str(exc_info.value)


def test_malformed_catalogue_produces_controlled_error(tmp_path):
    """Verify that malformed JSON, duplicate IDs, or missing fields produce CatalogueValidationError."""
    # 1. Invalid JSON
    corrupted_json_file = tmp_path / "corrupted.json"
    corrupted_json_file.write_text("{ not valid json }", encoding="utf-8")
    with pytest.raises(CatalogueValidationError) as exc_info:
        CatalogueService(data_path=corrupted_json_file)
    assert "Malformed JSON" in str(exc_info.value)

    # 2. Duplicate product IDs
    duplicate_json_file = tmp_path / "duplicate.json"
    duplicate_data = [
        {"id": "DUP-1", "name": "Item 1", "description": "Desc", "price": 100.0, "stock": 10},
        {"id": "DUP-1", "name": "Item 2", "description": "Desc", "price": 200.0, "stock": 5},
    ]
    duplicate_json_file.write_text(json.dumps(duplicate_data), encoding="utf-8")
    with pytest.raises(CatalogueValidationError) as exc_info:
        CatalogueService(data_path=duplicate_json_file)
    assert "Duplicate product ID" in str(exc_info.value)

    # 3. Non-list JSON root
    dict_json_file = tmp_path / "not_a_list.json"
    dict_json_file.write_text(json.dumps({"id": "P-1"}), encoding="utf-8")
    with pytest.raises(CatalogueValidationError) as exc_info:
        CatalogueService(data_path=dict_json_file)
    assert "must be a list" in str(exc_info.value)
