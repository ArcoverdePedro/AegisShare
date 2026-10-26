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
    path("laboratorio/pedidos/<uuid:pk>/etiqueta/", views.specimen_label, name="specimen_label"),
    path("laboratorio/pedidos/<uuid:pk>/cancelar/", views.order_cancel, name="order_cancel"),
    path(
        "laboratorio/pedidos/<uuid:pk>/amostras/<uuid:specimen_id>/rejeitar/",
        views.specimen_reject,
        name="specimen_reject",
    ),
    path("laboratorio/recebimento/", views.specimen_receive, name="specimen_receive"),
]
