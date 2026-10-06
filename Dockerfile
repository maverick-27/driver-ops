# API image. Stage 1 installs locked dependencies with uv; stage 2 is the slim runtime.
FROM ghcr.io/astral-sh/uv:python3.12-bookworm AS builder
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY src ./src

FROM python:3.12.8-slim
WORKDIR /app
RUN useradd --uid 10001 --create-home app
COPY --from=builder --chown=app:app /app /app
ENV PATH="/app/.venv/bin:$PATH" PYTHONUNBUFFERED=1 UVICORN_WORKERS=4
USER app
EXPOSE 8000
CMD sh -c 'uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers ${UVICORN_WORKERS:-4}'
