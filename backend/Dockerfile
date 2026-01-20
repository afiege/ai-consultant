# Backend Dockerfile for Railway deployment
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p /app/database /app/uploads /app/exports

# Expose port (Railway uses dynamic PORT)
EXPOSE ${PORT:-8000}

# Run the application - use Railway's PORT or default to 8000
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
