#!/bin/sh

uv run python manage.py shell -c 'from django.core.cache import cache; cache.clear()'

uv run python manage.py migrate

uv run python manage.py collectstatic --noinput --clear

uv run granian mysite.wsgi:application --host 0.0.0.0 --port 8001 --interface wsgi --workers 5 --blocking-threads 2 --backpressure 100 --workers-lifetime 3900