#!/bin/sh
set -eu

PORT="${PORT:-8000}"
RUN_MIGRATIONS="${RUN_MIGRATIONS:-true}"
COLLECT_STATIC="${COLLECT_STATIC:-true}"
WEB_WORKERS="${WEB_WORKERS:-1}"

if [ -z "${REDIS_URL:-}" ] && [ "$WEB_WORKERS" != "1" ]; then
  echo "REDIS_URL nao configurada; WEB_WORKERS foi reduzido para 1 para manter WebSockets consistentes."
  WEB_WORKERS=1
fi

if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Aguardando banco de dados..."
  attempt=1
  max_attempts="${DB_STARTUP_ATTEMPTS:-30}"

  until uv run python - <<'PY'
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")
import django
django.setup()
from django.db import connection
connection.ensure_connection()
connection.close()
PY
  do
    if [ "$attempt" -ge "$max_attempts" ]; then
      echo "Banco de dados indisponivel apos ${max_attempts} tentativas."
      exit 1
    fi
    attempt=$((attempt + 1))
    sleep 2
  done

  echo "Aplicando migrations..."
  uv run manage.py migrate --noinput
fi

if [ "$COLLECT_STATIC" = "true" ]; then
  echo "Coletando arquivos estaticos..."
  uv run manage.py collectstatic --noinput
fi

echo "Iniciando AegisShare na porta ${PORT} com ${WEB_WORKERS} worker(s)..."
exec uv run granian mysite.asgi:application \
  --host 0.0.0.0 \
  --port "$PORT" \
  --interface asgi \
  --workers "$WEB_WORKERS"
