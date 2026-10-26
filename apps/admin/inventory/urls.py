from django.urls import path

from . import views

app_name = "inventory"
urlpatterns = [
    path("estoque/", views.item_list, name="item_list"),
    path("estoque/requisicoes/", views.requisition_list, name="requisition_list"),
    path("estoque/requisicoes/nova/", views.requisition_create, name="requisition_create"),
    path("estoque/requisicoes/<uuid:pk>/", views.requisition_detail, name="requisition_detail"),
    path("estoque/saldos/", views.balance_list, name="balance_list"),
    path("estoque/movimentos/", views.movement_list, name="movement_list"),
    path("estoque/movimentos/novo/", views.movement_create, name="movement_create"),
    path("estoque/movimentos/<uuid:pk>/", views.movement_detail, name="movement_detail"),
    path("estoque/compras/", views.purchase_list, name="purchase_list"),
    path("estoque/compras/nova/", views.purchase_create, name="purchase_create"),
    path("estoque/compras/<uuid:pk>/", views.purchase_detail, name="purchase_detail"),
    path(
        "estoque/compras/itens/<uuid:pk>/receber/", views.purchase_receive, name="purchase_receive"
    ),
]
