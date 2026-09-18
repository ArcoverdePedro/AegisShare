from django.urls import path

from . import views

app_name = "lis"
urlpatterns = [
    path("laboratorio/pedidos/", views.order_list, name="order_list"),
    path(
        "laboratorio/encontros/<uuid:encounter_id>/pedidos/novo/",
        views.order_create,
        name="order_create",
    ),
    path("laboratorio/pedidos/<uuid:pk>/", views.order_detail, name="order_detail"),
    path("laboratorio/pedidos/<uuid:pk>/coleta/", views.specimen_create, name="specimen_create"),
]
