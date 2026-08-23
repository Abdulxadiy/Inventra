set -e

echo "==> Running migrations..."
python manage.py migrate --noinput

echo "==> Static files collecting..."

python manage.py collectstatic --noinput --clear || true

echo "==> Preparations completed. Main process starting..."

exec "$@"