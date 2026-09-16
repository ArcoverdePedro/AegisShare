from django.urls import path

from . import views

app_name = "compliance"
urlpatterns = [
    path("lgpd/solicitacoes/", views.request_list, name="request_list"),
    path("lgpd/solicitacoes/nova/", views.request_create, name="request_create"),
    path("lgpd/solicitacoes/<uuid:pk>/", views.request_detail, name="request_detail"),
    path(
        "lgpd/solicitacoes/<uuid:pk>/transicao/",
        views.request_transition,
        name="request_transition",
    ),
]
