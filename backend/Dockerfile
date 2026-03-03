# Stage 1: Build
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

WORKDIR /app
# Copy only dependency files first to use Docker's cache
COPY pyproject.toml uv.lock ./
# Install dependencies into a virtualenv
RUN uv sync --frozen --no-dev

# Stage 2: Final
FROM python:3.12-slim
WORKDIR /app
# Copy only the virtualenv and your code from the builder
COPY --from=builder /app/.venv /app/.venv
COPY . .

#Use the generated virtualenv for the runtime environment
ENV PATH="/app/.venv/bin:$PATH"

# Command to run the app when the container starts
# Uvicorn is the server that runs FastAPI.
# The --host 0.0.0.0 makes the app accessible from outside the container.

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
# CMD exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}