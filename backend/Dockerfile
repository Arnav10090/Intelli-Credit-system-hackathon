FROM python:3.11-slim

# System dependencies: Tesseract OCR + Poppler (for PDF) + build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    poppler-utils \
    ghostscript \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directories and ML models directory
RUN mkdir -p /app/data /app/uploads /app/outputs /app/ml/models

# Note: ML models are mounted via volume in docker-compose.yml
# If running standalone, ensure ml/models/ contains credit_validator.joblib

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]