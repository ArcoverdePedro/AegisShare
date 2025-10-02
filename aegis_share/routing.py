from django.urls import re_path
from aegis_share.consumer import Notificador

websocket_urlpatterns = [
    re_path(r"ws/notifications/$", Notificador.as_asgi()),
]
