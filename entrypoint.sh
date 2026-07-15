#!/bin/sh
set -e

PORT="${PORT:-8000}"

echo "[SGE] Aplicando migrate..."
python manage.py migrate --noinput

echo "[SGE] Coletando estaticos..."
python manage.py collectstatic --noinput || true

if [ -n "$1" ]; then
  echo "[SGE] Executando: $@"
  exec sh -c "PORT=$PORT $*"
elif [ "$DJANGO_ENV" = "prd" ]; then
  echo "[SGE] Iniciando gunicorn na porta $PORT..."
  exec gunicorn app.wsgi:application --bind 0.0.0.0:"$PORT" --workers 2 --timeout 120
else
  echo "[SGE] Iniciando runserver na porta $PORT..."
  exec python manage.py runserver 0.0.0.0:"$PORT"
fi