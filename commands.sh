#!/bin/sh

uv run manage.py shell -c 'from django.core.cache import cache; cache.clear()' --verbosity 0

uv run manage.py migrate

uv run manage.py collectstatic --noinput --clear

uv run uvicorn mysite.asgi:application --host 0.0.0.0 --port 8000 --workers 5