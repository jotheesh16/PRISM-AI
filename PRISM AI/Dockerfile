# ==============================================================================
# PRISM AI — Production Dockerfile
# Multimodal RAG with Explainability
# ==============================================================================
FROM python:3.12-slim-bookworm AS base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=8765 \
    PRISM_PORT=8765 \
    PRISM_HOST=0.0.0.0 \
    PRISM_DATA=/app/data \
    PRISM_EMBED_MODEL=all-minilm \
    TESSERACT_CMD=tesseract \
    PRISM_OCR_LANG=eng \
    HF_HOME=/home/prism/.cache/huggingface \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1

WORKDIR /app

# 1. Install system runtime dependencies: Tesseract 5 OCR, Leptonica, curl, GLib
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 2. Upgrade pip and install lightweight CPU PyTorch wheel first to minimize image size
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# 3. Install remaining Python application dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# 4. Pre-download and cache all-MiniLM-L6-v2 embeddings model during build
# This enables completely offline container operation at runtime
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"

# 5. Create non-root application user and persistent data directory
RUN useradd -u 1000 -m -s /bin/bash prism && \
    mkdir -p /app/data /home/prism/.cache && \
    cp -r /root/.cache/* /home/prism/.cache/ 2>/dev/null || true && \
    chown -R prism:prism /app /home/prism/.cache

# 6. Copy application source code
COPY --chown=prism:prism server.py ingest.py models.py research.py store.py file_import.py ./
COPY --chown=prism:prism web/ ./web/

# Switch to non-root user
USER prism

# Expose server port
EXPOSE 8765

# Persistent volume mount point for SQLite database, uploaded PDFs, and vector index
VOLUME ["/app/data"]

# Container healthcheck querying the system configuration API
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://127.0.0.1:${PORT}/api/config || exit 1

# Launch application
CMD ["python", "server.py"]
