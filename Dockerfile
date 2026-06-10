FROM python:3.12-slim-bookworm

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir resend "bcrypt==4.0.1" slowapi

# Copy application code
COPY . .

# Create persistent data directories
RUN mkdir -p /app/data /app/uploads /app/outputs

# Cloud Run requires port 8080
EXPOSE 8080

# Use gunicorn for production — more stable than uvicorn alone under load
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1", "--timeout-keep-alive", "75"]