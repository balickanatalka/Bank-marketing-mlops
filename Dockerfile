# Python runtime matches .python-version; digest verified against Docker Hub.
FROM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS builder
ENV UV_PYTHON_DOWNLOADS=never UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1
WORKDIR /app
RUN pip install --no-cache-dir uv==0.13.9
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --locked --no-dev --no-install-project

FROM python:3.12.16-slim-trixie@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS runtime
# Trivy identified a fixable zlib vulnerability in the pinned base.
RUN apt-get update \
    && apt-get install -y --no-install-recommends zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
    && apt-get purge -y --no-auto-remove mount \
    && rm -rf /var/lib/apt/lists/*
ENV PATH="/app/.venv/bin:$PATH" PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MLFLOW_ENABLE_TELEMETRY=false MLFLOW_DISABLE_AGENT_HINT=1 \
    MPLCONFIGDIR=/tmp/matplotlib HOME=/tmp
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY src ./src
COPY configs/serving-logging.json ./configs/serving-logging.json
COPY docs/api/openapi-v1.json ./docs/api/openapi-v1.json
COPY DATA_LICENSE.md docs/THIRD_PARTY_NOTICES.md ./notices/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/ready', timeout=2)"]
CMD ["python", "-m", "uvicorn", "src.serving:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log", "--log-config", "configs/serving-logging.json"]
