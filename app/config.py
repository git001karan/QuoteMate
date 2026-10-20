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

# --- Robustness limits -------------------------------------------------------

# Maximum quantity of a single line item accepted from a customer message.
# Requests above this cap are politely clamped (never silently).
MAX_QTY = int(os.getenv("MAX_QTY", "100"))

# Maximum accepted length (characters) for an incoming message text field.
MAX_TEXT_LENGTH = int(os.getenv("MAX_TEXT_LENGTH", "1000"))

# How many days a confirmed quotation stays valid from the confirmation time.
QUOTE_VALIDITY_DAYS = int(os.getenv("QUOTE_VALIDITY_DAYS", "7"))

# How many recent messages (incoming + outgoing) are attached to a handoff
# event as conversation context for the human agent.
HANDOFF_CONTEXT_MESSAGES = int(os.getenv("HANDOFF_CONTEXT_MESSAGES", "5"))

# --- Optional WhatsApp Cloud API integration (off by default) ----------------
# Live WhatsApp integration is OUT OF SCOPE for this assessment. These values
# define the integration point: when WHATSAPP_APP_SECRET is set, POST /webhook
# verifies the X-Hub-Signature-256 HMAC header (constant-time comparison);
# when WHATSAPP_VERIFY_TOKEN is set, GET /webhook answers Meta's verification
# handshake (hub.mode / hub.verify_token / hub.challenge).
WHATSAPP_APP_SECRET = os.getenv("WHATSAPP_APP_SECRET", "")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_VERIFY_TOKEN", "")
