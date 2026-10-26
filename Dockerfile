# ==============================================================================
# Multi-stage Dockerfile for CodeComprehension
# Runs under non-root user 'codeuser' with healthcheck probe
# ==============================================================================

FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt


# Final Runtime Stage
FROM python:3.12-slim AS runtime

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/home/codeuser/.local/bin:$PATH" \
    FLASK_ENV=production \
    FLASK_DEBUG=false \
    PORT=5000 \
    HOST=0.0.0.0 \
    DATABASE_PATH=/app/codecomprehension.db

# Install runtime curl for healthcheck probe
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged non-root user
RUN groupadd -g 1000 codeuser && \
    useradd -u 1000 -g codeuser -m codeuser

# Copy installed Python packages from builder stage
COPY --from=builder /root/.local /home/codeuser/.local

# Copy application source code
COPY --chown=codeuser:codeuser . .

# Grant codeuser full ownership and read/write permissions to the entire /app directory
RUN chown -R codeuser:codeuser /app && chmod -R 775 /app

# Switch to unprivileged non-root execution
USER codeuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:5000/healthz || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "4", "--preload", "--timeout", "60", "wsgi:app"]