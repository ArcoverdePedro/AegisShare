# urls.py - HTMX para lista, WebSocket para mensagens
from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

urlpatterns = [
    path("setup/", views.FirstSuperuserCreateView.as_view(), name="primeiro_cadastro"),
    path("", views.home, name="home"),
    path("login/", views.custom_login, name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("cadastro/", views.cadastro, name="cadastro"),
    path("sobre/", views.sobre, name="sobre"),
    path("arquivos/", views.arquivos, name="arquivos"),
    path("upload/", views.upload, name="upload"),
    path("user/", views.user, name="user"),
    path("buscar-cliente/", views.buscar_cliente, name="buscar_cliente"),
    path("buscar-funcionario/", views.buscar_funcionario, name="buscar_funcionario"),
    path("buscar_arquivo/", views.buscar_arquivo, name="buscar_arquivo"),
    
    # Chat URLs
    path("chat/", views.chat_index, name="chat_index"),
    path("chat/users/", views.user_list, name="user_list"),  # HTMX
    path(
        "chat/conversation/<uuid:user_id>/",
        views.get_or_create_conversation,
        name="get_conversation",
    ),
    path(
        "chat/<uuid:conversation_id>/",
        views.load_conversation,
        name="load_conversation",
    ),
    
    # Não precisa mais:
    # - send_message (WebSocket)
    # - check_new_messages (WebSocket)
]