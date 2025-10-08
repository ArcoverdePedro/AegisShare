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
    path("meus_arquivos/", views.meus_arquivos, name="meus_arquivos"),
    path("notifications/", views.notifications, name="notifications"),
]
