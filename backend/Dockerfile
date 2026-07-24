FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for health check and OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source code
COPY src/ ./src/
COPY eval/ ./eval/
COPY data/ ./data/
COPY tests/ ./tests/

# Create outputs directories
RUN mkdir -p outputs/reports outputs/traces outputs/metrics

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
