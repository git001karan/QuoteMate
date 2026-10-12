"""API route endpoints for QuoteMate."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import AnalyzeRequest, NLPAnalysisResult, Product
from app.services.catalogue_service import ProductNotFoundError, catalogue_service
from app.services.nlp_service import nlp_service

router = APIRouter()


@router.get(
    "/products",
    response_model=List[Product],
    tags=["Catalogue"],
    summary="List all catalogue products",
)
def list_products(db: Session = Depends(get_db)) -> List[Product]:
    """Retrieve all available products from the catalogue stored in SQLite."""
    return catalogue_service.get_all_products(db=db)


@router.get(
    "/products/{product_id}",
    response_model=Product,
    tags=["Catalogue"],
    summary="Get product by ID",
    responses={404: {"description": "Product not found"}},
)
def get_product(product_id: str, db: Session = Depends(get_db)) -> Product:
    """Retrieve details for a single product by its unique product ID from SQLite."""
    try:
        return catalogue_service.get_product_by_id(product_id, db=db)
    except ProductNotFoundError as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(err),
        ) from err


@router.post(
    "/nlp/analyze",
    response_model=NLPAnalysisResult,
    tags=["NLP Diagnostics"],
    summary="Diagnostic NLP analysis of an incoming message",
)
def analyze_message(
    payload: AnalyzeRequest, db: Session = Depends(get_db)
) -> NLPAnalysisResult:
    """Analyze customer message text for intent, matched products, and extracted quantities."""
    return nlp_service.analyze(payload.text, db=db)
