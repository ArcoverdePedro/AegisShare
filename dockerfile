FROM python:3.13-slim-trixie

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

ENV UV_NO_CACHE=1 \
    UV_CONCURRENT_INSTALLS=4 \
    UV_CACHE_DIR=/dev/null \
    PYTHONPYCACHEPREFIX=/dev/null \
    PYTHONHASHSEED=random \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_NO_COMPILE=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN uv sync --frozen --no-dev --no-cache \
    && uv cache clean \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean \
    && rm -rf /root/.cache \
    && rm -rf /tmp/* \
    && find /usr/local -type f -name '*.pyc' -delete \
    && find /usr/local -type d -name '__pycache__' -delete \
    && find /app -type d -name '__pycache__' -delete \
    && find /app -type f -name '*.pyc' -delete \
    && find . -type f -name '*.py[co]' -delete  \
    && find . -type d -name '*.egg-info' -exec rm -rf {} + 2>/dev/null || true  \
    && find . -name '*.md' -delete 2>/dev/null || true

COPY . .

RUN chmod +x /app/commands.sh