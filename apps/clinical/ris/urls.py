from django.urls import path

from . import views

app_name = "ris"
urlpatterns = [
    path("imagem/pedidos/", views.order_list, name="order_list"),
    path(
        "imagem/encontros/<uuid:encounter_id>/pedidos/novo/",
        views.order_create,
        name="order_create",
    ),
    path("imagem/pedidos/<uuid:pk>/", views.order_detail, name="order_detail"),
]
