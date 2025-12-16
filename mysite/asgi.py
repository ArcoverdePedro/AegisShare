# ruff: noqa: E402
import os

from django.core.asgi import get_asgi_application

# CRÍTICO: Configurar Django ANTES de qualquer outro import
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

# Initialize Django ASGI application early
django_asgi_app = get_asgi_application()

from channels.auth import AuthMiddlewareStack

# IMPORTANTE: Imports de channels e routing DEPOIS de inicializar Django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator

from aegis_share.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
