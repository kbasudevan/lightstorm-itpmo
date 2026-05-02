# ============================================================
# Lightstorm IT Projects — Dockerfile
# Production image: Python 3.11-slim + Gunicorn
# ============================================================

FROM python:3.11-slim

# ── System dependencies ──────────────────────────────────────
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ────────────────────────────────────────
WORKDIR /app

# ── Python dependencies (own layer for cache efficiency) ─────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ─────────────────────────────────────────
COPY app.py config.py models.py etom_data.py ./
COPY static/  static/
COPY templates/ templates/

# ── Persistent-data directories ──────────────────────────────
# /app/instance  → SQLite database  (mount a named volume here)
# /app/static/uploads → file attachments (mount a named volume here)
RUN mkdir -p /app/instance /app/static/uploads

# ── Entrypoint script ────────────────────────────────────────
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ── Non-root user for security ───────────────────────────────
RUN adduser --disabled-password --gecos '' --uid 1000 appuser \
    && chown -R appuser:appuser /app
USER appuser

# ── Runtime ──────────────────────────────────────────────────
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
