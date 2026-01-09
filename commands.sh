#!/bin/sh
set -e

uv run manage.py shell -c 'from django.core.cache import cache; cache.clear()' --verbosity 0

uv run manage.py migrate

uv run manage.py collectstatic --noinput --clear

exec uv run granian mysite.asgi:application \
  --host 0.0.0.0 \
  --port $PORT \
  --interface asgi \
  --workers 1 \
  --runtime-threads 1
