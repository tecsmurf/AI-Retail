FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Create data directory for CV events
RUN mkdir -p /app/data /app/uploads

# Railway injects PORT env var — default to 8000
ENV PORT=8000
EXPOSE ${PORT}

# Run with PORT from environment
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT
