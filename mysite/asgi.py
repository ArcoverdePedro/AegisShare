# ruff: noqa: E402
import os
from functools import partial

from django.core.asgi import get_asgi_application

# CRÍTICO: Configurar Django ANTES de qualquer outro import
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

# Initialize Django ASGI application early
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack

# IMPORTANTE: Imports de channels e routing DEPOIS de inicializar Django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.conf import settings
from granian.utils.proxies import wrap_asgi_with_proxy_headers

from aegis_share.routing import websocket_urlpatterns
from apps.interoperability.asgi import bounded_inbox

router = ProtocolTypeRouter(
    {
        "http": partial(bounded_inbox, django_asgi_app),
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)

# Atras do proxy reverso, REMOTE_ADDR vira o IP real do cliente (lido de
# X-Forwarded-For) somente quando a conexao vem de um proxy confiavel.
application = wrap_asgi_with_proxy_headers(router, trusted_hosts=settings.TRUSTED_PROXY_IPS)
