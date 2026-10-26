from django.urls import path

from . import views

app_name = "indicators"
urlpatterns = [path("indicadores/", views.indicator_panel, name="panel")]
