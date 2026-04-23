# Multi-stage build for backend
ARG TARGETPLATFORM=linux/amd64

FROM --platform=${TARGETPLATFORM} python:3.11-slim AS builder

WORKDIR /build

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app/ ./app/
RUN pip install --no-cache-dir .

FROM --platform=${TARGETPLATFORM} python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code, vector index, and mock data
COPY backend/app/ ./app/
COPY dataset/processed/ ./dataset/processed/
COPY dataset/mock/ ./dataset/mock/

# Expose port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
