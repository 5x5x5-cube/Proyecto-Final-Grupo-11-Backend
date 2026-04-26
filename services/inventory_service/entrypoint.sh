#!/bin/bash
set -e

echo "Running Alembic migrations..."
alembic upgrade head

echo "Running seed script..."
PYTHONPATH=/app python scripts/seed.py || echo "Seed script failed, continuing..."

echo "Starting Inventory Service..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
