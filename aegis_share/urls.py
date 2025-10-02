from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("login/", views.custom_login, name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("cadastro/", views.cadastro, name="cadastro"),
    path("notifications/", views.notifications, name="notifications"),
]
