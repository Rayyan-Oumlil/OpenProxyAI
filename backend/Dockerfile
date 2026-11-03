# ── Stage 1: Builder ──────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

COPY requirements.txt .
# torch + transformers (multi-GB with CUDA wheels) only serve the optional ML prompt-injection model, which
# is imported lazily and falls back to regex when absent. The demo image builds with INSTALL_ML=false.
ARG INSTALL_ML=true
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && if [ "$INSTALL_ML" = "false" ]; then grep -v -E '^(torch|transformers)([<>=!~ ]|$)' requirements.txt > requirements.lite.txt; else cp requirements.txt requirements.lite.txt; fi \
    && /opt/venv/bin/pip install --no-cache-dir -r requirements.lite.txt

# ── Stage 2: Runtime ─────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Security: run as non-root
RUN groupadd --gid 1001 appuser \
    && useradd --uid 1001 --gid 1001 --create-home appuser

WORKDIR /app

# Copy virtual env from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application code
COPY . .

# Own everything under /app to appuser
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import httpx; r = httpx.get('http://localhost:8080/health'); r.raise_for_status()"]

# Use $PORT so Cloud Run (which injects PORT=8080) works out of the box.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
