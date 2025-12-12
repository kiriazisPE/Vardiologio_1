# Multi-stage production Dockerfile for Shift Planner
# Stage 1: Builder - Install dependencies
FROM python:3.13-slim AS builder

# Install build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime - Minimal production image
FROM python:3.13-slim

# Install runtime dependencies only
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    APP_ENV=production \
    DB_FILE=/data/shift_maker.sqlite3

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash appuser && \
    mkdir -p /data /app && \
    chown -R appuser:appuser /data /app

# Set working directory
WORKDIR /app

# Copy application code
COPY --chown=appuser:appuser . .

# Switch to non-root user
USER appuser

# Expose ports
EXPOSE 8501 8001

# Health check using custom endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Metadata labels
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
LABEL org.opencontainers.image.created="${BUILD_DATE}" \
      org.opencontainers.image.title="Shift Planner" \
      org.opencontainers.image.description="AI-powered shift scheduling application" \
      org.opencontainers.image.url="https://github.com/kiriazisPE/Vardiologio_1" \
      org.opencontainers.image.source="https://github.com/kiriazisPE/Vardiologio_1" \
      org.opencontainers.image.version="${VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.vendor="kiriazisPE" \
      org.opencontainers.image.licenses="MIT"

# Run application
CMD ["streamlit", "run", "main.py", "--server.port=8501", "--server.address=0.0.0.0", "--server.headless=true"]
