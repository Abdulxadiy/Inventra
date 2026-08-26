#!/bin/sh

set -e

# Monkey-patch gevent BEFORE importing Django or any database modules
export GEVENT_RESOLVER=ares
python -c "from gevent import monkey; monkey.patch_all()"

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Preparations completed. Main process starting..."

exec "$@"
