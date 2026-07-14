#!/bin/sh
set -e

echo "[SGE] Aplicando migrate..."
python manage.py migrate --noinput

echo "[SGE] Coletando estaticos..."
python manage.py collectstatic --noinput || true

if [ -n "$1" ]; then
  echo "[SGE] Executando: $@"
  exec "$@"
elif [ "$DJANGO_ENV" = "prd" ]; then
  echo "[SGE] Iniciando gunicorn..."
  exec gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 120
else
  echo "[SGE] Iniciando runserver..."
  exec python manage.py runserver 0.0.0.0:8000
fi