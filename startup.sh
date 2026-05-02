#!/bin/bash
set -e
echo "[startup] Running database init..."
python -c "from app import init_db; init_db()"
echo "[startup] Starting gunicorn..."
exec gunicorn --bind=0.0.0.0:8000 --workers=2 --timeout=120 --preload app:app
