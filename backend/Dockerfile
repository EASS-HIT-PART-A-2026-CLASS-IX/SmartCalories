# Multi-stage build using uv. Final image runs uvicorn (or arq, switched via compose `command`).
FROM ghcr.io/astral-sh/uv:0.5-python3.12-bookworm-slim AS builder

WORKDIR /app
ENV UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 UV_PROJECT_ENVIRONMENT=/opt/venv

COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --no-dev

COPY backend/calorie_tracker ./calorie_tracker
COPY backend/alembic.ini ./alembic.ini

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev


FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/calorie_tracker ./calorie_tracker
COPY --from=builder /app/alembic.ini ./alembic.ini

RUN mkdir -p /app/uploads /app/data && \
    addgroup --system app && adduser --system --ingroup app --home /app app && \
    chown -R app:app /app
USER app

EXPOSE 9000
CMD ["uvicorn", "calorie_tracker.main:app", "--host", "0.0.0.0", "--port", "9000"]
