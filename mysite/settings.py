import base64
import binascii
import os
from pathlib import Path

import environ
from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    SECURE_SSL_REDIRECT=(bool, True),
    SESSION_COOKIE_SECURE=(bool, True),
    CSRF_COOKIE_SECURE=(bool, True),
    FILE_MAX_UPLOAD_MB=(int, 50),
    FILE_RETENTION_DAYS=(int, 30),
    PINATA_TIMEOUT_SECONDS=(int, 90),
    CLAMAV_ENABLED=(bool, False),
    CLAMAV_REQUIRED=(bool, False),
    CLAMAV_PORT=(int, 3310),
    SENTRY_TRACES_SAMPLE_RATE=(float, 0.05),
)

ENV_FILE = env.str("ENV_FILE", default=str(BASE_DIR / ".env"))
if os.path.exists(ENV_FILE):
    environ.Env.read_env(ENV_FILE)

SECRET_KEY = env.str("SECRET_KEY", default="")
DEBUG = env.bool("DEBUG")
ENVIRONMENT = env.str("ENVIRONMENT", default="development" if DEBUG else "production")

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "development-only-insecure-key"
    else:
        raise ImproperlyConfigured("SECRET_KEY e obrigatoria quando DEBUG=False.")

if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith("CHANGE_ME")):
    raise ImproperlyConfigured(
        "SECRET_KEY de producao deve possuir pelo menos 50 caracteres e nao pode ser placeholder."
    )

ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT") if not DEBUG else False
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE") if not DEBUG else False
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE") if not DEBUG else False
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool(
        "SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True
    )
    SECURE_HSTS_PRELOAD = env.bool("SECURE_HSTS_PRELOAD", default=True)

INSTALLED_APPS = [
    "channels",
    "django_htmx",
    "auditlog",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "crispy_forms",
    "django_simple_bulma",
    "crispy_bulma",
    "django_feather",
    "aegis_share",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "auditlog.middleware.AuditlogMiddleware",
    "aegis_share.middleware.TrackedSessionMiddleware",
    "aegis_share.middleware.FirstAccessRedirectMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "mysite.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "aegis_share.context_processors.notifications_context",
            ],
        },
    },
]

WSGI_APPLICATION = "mysite.wsgi.application"
ASGI_APPLICATION = "mysite.asgi.application"

DATABASE_URL = env.str("DATABASE_URL", default="")
if DATABASE_URL:
    DATABASES = {
        "default": env.db_url_config(DATABASE_URL, conn_max_age=60)
    }
elif not DEBUG:
    raise ImproperlyConfigured(
        "DATABASE_URL e obrigatoria em producao. Use PostgreSQL interno ou um host externo."
    )
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

REDIS_URL = env.str("REDIS_URL", default="")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "TIMEOUT": 300,
        }
    }
else:
    CHANNEL_LAYERS = {
        "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "aegisshare-local",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.Argon2PasswordHasher"]

AUTH_USER_MODEL = "aegis_share.CustomUser"
LOGIN_URL = "login"
LOGOUT_REDIRECT_URL = "home"

MESSAGE_TAGS = {
    messages.INFO: "info",
    messages.SUCCESS: "success",
    messages.WARNING: "warning",
    messages.ERROR: "danger",
}

CRISPY_ALLOWED_TEMPLATE_PACKS = "bulma"
CRISPY_TEMPLATE_PACK = "bulma"

LANGUAGE_CODE = "pt-br"
TIME_ZONE = env.str("TIME_ZONE", default="America/Fortaleza")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "django_simple_bulma.finders.SimpleBulmaFinder",
]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

FILE_MAX_UPLOAD_MB = env.int("FILE_MAX_UPLOAD_MB")
FILE_RETENTION_DAYS = env.int("FILE_RETENTION_DAYS")
FILE_UPLOAD_MAX_MEMORY_SIZE = min(FILE_MAX_UPLOAD_MB * 1024 * 1024, 5 * 1024 * 1024)
DATA_UPLOAD_MAX_MEMORY_SIZE = FILE_MAX_UPLOAD_MB * 1024 * 1024 + 1024 * 1024

FILE_ENCRYPTION_KEY = env.str("FILE_ENCRYPTION_KEY", default="")
if not FILE_ENCRYPTION_KEY and DEBUG:
    FILE_ENCRYPTION_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

if not FILE_ENCRYPTION_KEY:
    raise ImproperlyConfigured("FILE_ENCRYPTION_KEY e obrigatoria em producao.")

try:
    _decoded_file_key = base64.urlsafe_b64decode(FILE_ENCRYPTION_KEY.encode("ascii"))
except (ValueError, UnicodeEncodeError, binascii.Error) as exc:
    raise ImproperlyConfigured(
        "FILE_ENCRYPTION_KEY deve ser base64 URL-safe representando exatamente 32 bytes."
    ) from exc
if len(_decoded_file_key) != 32:
    raise ImproperlyConfigured(
        "FILE_ENCRYPTION_KEY deve representar exatamente 32 bytes."
    )
del _decoded_file_key

PINATA_JWT_TOKEN = env.str("PINATA_JWT_TOKEN", default="")
if not PINATA_JWT_TOKEN and not DEBUG:
    raise ImproperlyConfigured("PINATA_JWT_TOKEN e obrigatorio em producao.")
PINATA_GATEWAY_URL = env.str(
    "PINATA_GATEWAY_URL",
    default="https://gateway.pinata.cloud/ipfs/{cid}",
)
PINATA_TIMEOUT_SECONDS = env.int("PINATA_TIMEOUT_SECONDS")

CLAMAV_ENABLED = env.bool("CLAMAV_ENABLED")
CLAMAV_REQUIRED = env.bool("CLAMAV_REQUIRED")
CLAMAV_HOST = env.str("CLAMAV_HOST", default="clamav")
CLAMAV_PORT = env.int("CLAMAV_PORT")

AUDITLOG_STORE_JSON_CHANGES = True
AUDITLOG_DISABLE_ON_RAW_SAVE = True
AUDITLOG_CHANGE_DISPLAY_TRUNCATE_LENGTH = 140

SENTRY_DSN = env.str("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        environment=ENVIRONMENT,
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE"),
        send_default_pii=False,
    )

LOG_LEVEL = env.str("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "mysite.logging.JsonFormatter"}},
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"}
    },
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "aegis_share": {
            "handlers": ["console"],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}
