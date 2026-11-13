FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_RETRIES=15 \
    PIP_TIMEOUT=120 \
    PIP_RESUME_RETRIES=10

# Docker Desktop's bridge to your host's proxy (required behind corporate/VPN/AV TLS inspection)
ENV HTTP_PROXY=http://http.docker.internal:3128 \
    HTTPS_PROXY=http://http.docker.internal:3128 \
    http_proxy=http://http.docker.internal:3128 \
    https_proxy=http://http.docker.internal:3128

# Also set the env-var form so it's inherited by any pip subprocess that slips through
ENV PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"

# Create a non-root runtime user
RUN useradd --create-home --uid 1000 appuser

# Pre-install build tools with --trusted-host on the CLI so no subprocess is needed later.
RUN pip install --no-cache-dir \
        --trusted-host pypi.org \
        --trusted-host files.pythonhosted.org \
        --trusted-host pypi.python.org \
        "setuptools>=75" \
        wheel

# Copy package manifest + source first (better layer caching + fixes install order)
COPY --chown=appuser:appuser pyproject.toml ./
COPY --chown=appuser:appuser app ./app

# --no-build-isolation skips the isolated build subprocess that drops the TLS stream on
# large index fetches (the /simple/sqlalchemy/ page is ~1.5 MB — the proxy kills it).
RUN pip install --no-cache-dir \
        --trusted-host pypi.org \
        --trusted-host files.pythonhosted.org \
        --trusted-host pypi.python.org \
        --no-build-isolation \
        .

# Copy the rest (alembic, tests, docs, etc.)
COPY --chown=appuser:appuser . .

# Ensure export directory exists and is writable by the runtime user
RUN mkdir -p /app/data/exports

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]