#!/bin/sh
set -e

echo "[entrypoint] Initialising database and seeding domains..."
python -c "from app import init_db; init_db()"

echo "[entrypoint] Starting Gunicorn on port ${PORT:-8000}..."
exec gunicorn \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${WEB_CONCURRENCY:-2}" \
    --threads 2 \
    --timeout 120 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app
