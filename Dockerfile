FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libmagic1 \
    libjpeg-dev \
    zlib1g-dev \
    libpng-dev \
    libfreetype-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy the backend-clean directory contents
COPY backend-clean/ /app/

# Copy and install Python dependencies
COPY backend-clean/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create uploads directory
RUN mkdir -p uploads && chmod 755 uploads

EXPOSE 8000

# Reduced workers, increased timeout.
# IMPORTANT: Render assigns the container's listen port dynamically via the
# $PORT env var (it does NOT default to 8000 or EXPOSE'd ports) and routes
# traffic to whatever port that variable names. Binding to a hardcoded port
# instead of $PORT means Render's proxy can never reach the container, so
# every single request fails identically -- which surfaces in the browser
# as a CORS error on every endpoint, since there's no response to attach
# CORS headers to. Shell form (not exec/JSON-array form) is required here
# so that $PORT actually gets expanded; falls back to 8000 for local
# `docker run` where $PORT isn't set.
CMD gunicorn -w 2 -k uvicorn.workers.UvicornWorker --timeout 120 --graceful-timeout 30 server:app --bind 0.0.0.0:${PORT:-8000}
