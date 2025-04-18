FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsm6 \
    libxext6 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY . .

# Create static directory
RUN mkdir -p /app/static

# Set environment variables
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=wsgi.py
ENV FLASK_ENV=production

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health/live || exit 1

# Run the application with proper gunicorn configuration
CMD exec gunicorn \
    --bind :${PORT} \
    --workers 1 \
    --threads 8 \
    --timeout 60 \
    --keep-alive 60 \
    --log-level debug \
    --access-logfile - \
    --error-logfile - \
    --capture-output \
    wsgi:app
