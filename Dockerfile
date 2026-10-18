# syntax=docker/dockerfile:1
# QuoteMate - AI-Powered WhatsApp Sales and Quotation Assistant
# FastAPI application image for the Cerevyn Solutions PS05 assessment.

FROM python:3.11-slim

# Security/ops hygiene: no .pyc files in the image, unbuffered logs
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first (better layer caching: changes only on
# requirements.txt edits)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code plus the data files that are read at import/startup:
#   - app/data/products.json        (catalogue seeding)
#   - sample_data/messages_dataset.json (NLP classifier training)
COPY app/ ./app/
COPY sample_data/ ./sample_data/

# Non-root runtime user and a writable directory for the SQLite database
RUN useradd --create-home --uid 1000 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /data
USER appuser

# Container-specific defaults, overridable at runtime with `docker run -e`.
# NOTE: the application's own local default (app/config.py -> ./quotemate.db)
# is unchanged; this only points the database at the mounted /data volume so
# data survives container restarts.
ENV DATABASE_URL="sqlite:////data/quotemate.db" \
    ENVIRONMENT="production" \
    PORT=8000

# Persistent storage mount point for the SQLite database
VOLUME ["/data"]

EXPOSE 8000

# Health check against the application's real /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import os,sys,urllib.request; u=f\"http://127.0.0.1:{os.environ.get('PORT','8000')}/health\"; sys.exit(0 if urllib.request.urlopen(u, timeout=4).status==200 else 1)"

# Shell form so ${PORT} is expanded at container start; exec replaces the
# shell so uvicorn receives signals directly for clean shutdown.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
