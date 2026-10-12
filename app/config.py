"""Configuration management for QuoteMate using environment variables."""

import os
from pathlib import Path

# Project root directory: parent directory of 'app'
BASE_DIR = Path(__file__).resolve().parent.parent

# Database configuration
DEFAULT_DB_PATH = BASE_DIR / "quotemate.db"
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")

# Application configuration
APP_NAME = os.getenv("APP_NAME", "QuoteMate")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEFAULT_TAX_RATE = float(os.getenv("DEFAULT_TAX_RATE", "0.18"))
