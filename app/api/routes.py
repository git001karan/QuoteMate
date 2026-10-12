"""API route endpoints for QuoteMate."""

from typing import List
from fastapi import APIRouter, HTTPException, status

from app.schemas import Product
from app.services.catalogue_service import ProductNotFoundError, catalogue_service

router = APIRouter(tags=["Catalogue"])


@router.get("/products", response_model=List[Product], summary="List all catalogue products")
def list_products() -> List[Product]:
    """Retrieve all available products from the catalogue."""
    return catalogue_service.get_all_products()


@router.get(
    "/products/{product_id}",
    response_model=Product,
    summary="Get product by ID",
    responses={404: {"description": "Product not found"}},
)
def get_product(product_id: str) -> Product:
    """Retrieve details for a single product by its unique product ID."""
    try:
        return catalogue_service.get_product_by_id(product_id)
    except ProductNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err
