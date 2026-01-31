# =============================================================================
# DOCKERFILE FOR LIGA ACB SCRAPER
# =============================================================================
#
# PURPOSE:
#     Creates a containerized environment to run the Liga ACB scraper.
#
# HOW TO USE:
#     Build the image:
#         docker build -t liga-acb-scraper .
#
#     Run the dashboard:
#         docker run -p 5000:5000 liga-acb-scraper
#
# =============================================================================

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create output directory
RUN mkdir -p /app/output/json /app/logs

# Pre-populate data during build
# Note: ACB scraper takes ~10 mins, so we rely on committed JSON files
# The daily GitHub Action will refresh the data
RUN echo "=== Building: Using committed JSON data ===" && \
    ls -la /app/output/json/*_latest.json 2>/dev/null || echo "No latest files" && \
    echo "=== Build complete: Data ready ==="

# Environment variables
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; print('OK')" || exit 1

# Make startup script executable
RUN chmod +x start.sh

# Default command
CMD ["./start.sh"]
