# Stage 1: Build React SPA
FROM node:22-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Build Python package
FROM python:3.12-slim AS backend-builder

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

# Stage 3: Runtime — minimal image
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

# Copy venv and source from backend-builder
COPY --from=backend-builder /app/.venv /app/.venv
COPY --from=backend-builder /app/src /app/src
COPY --from=backend-builder /app/prompts /app/prompts

# Copy compiled React SPA from frontend-builder
COPY --from=frontend-builder /frontend/dist /app/static

# Create volume mount point for SQLite
RUN mkdir -p /data

ENV PORT=8000
EXPOSE ${PORT}

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\",8000)}/health')" || exit 1

CMD sh -c "uvicorn d1ff.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'"
