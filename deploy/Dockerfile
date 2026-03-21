# Multi-stage build for minimal size
FROM python:3.11-slim as builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Runtime stage
FROM python:3.11-slim

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Don't buffer Python output (important for logging)
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Create app directory
WORKDIR /app

# Copy application code
COPY bot/ ./bot/

# Create data directory (will be mounted as volume)
RUN mkdir -p /data

# Health check
COPY deploy/healthcheck.py .
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python healthcheck.py || exit 1

# Run as non-root user (security best practice)
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app /data
USER appuser

# Start command
CMD ["python", "-m", "bot.main"]
