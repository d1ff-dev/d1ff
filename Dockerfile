# Stage 1: Builder — install dependencies
FROM python:3.12-slim AS builder

# Install uv from official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Copy dependency files first (cache layer)
COPY pyproject.toml uv.lock README.md ./

# Install only runtime deps without the project itself (cache layer)
RUN uv sync --frozen --no-dev --no-install-project

# Copy source code and prompt templates
COPY src/ ./src/
COPY prompts/ ./prompts/

# Now install the project package into the venv
RUN uv sync --frozen --no-dev

# Stage 2: Runtime — minimal image
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy venv and source from builder
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src
COPY --from=builder /app/prompts /app/prompts

# Create volume mount point for SQLite
RUN mkdir -p /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

CMD ["uvicorn", "d1ff.main:app", "--host", "0.0.0.0", "--port", "8000"]
