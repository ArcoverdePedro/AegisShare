from django.urls import path
from django.contrib.auth import views as auth_views
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
    path("notifications/", views.notifications, name="notifications"),
    path('buscar-cliente/', views.buscar_cliente, name='buscar_cliente'),
    path("buscar_arquivo/", views.buscar_arquivo, name="buscar_arquivo"),
]
