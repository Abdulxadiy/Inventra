#!/bin/sh

set -e

# Activate virtual environment
. /app/.venv/bin/activate

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Preparations completed. Main process starting..."

exec "$@"
