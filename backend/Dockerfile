# Multi-stage build for backend
FROM python:3.11-slim as builder

WORKDIR /build

# Install uv for faster dependency installation
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

FROM python:3.11-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY app/ ./app/

# Copy FAISS index (built during image build)
COPY ../dataset/processed/ ./dataset/processed/

# Expose port
EXPOSE 8000

# Run FastAPI with uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
