from django.urls import path

from . import views

app_name = "inventory"
urlpatterns = [
    path("estoque/", views.item_list, name="item_list"),
    path("estoque/requisicoes/", views.requisition_list, name="requisition_list"),
    path("estoque/requisicoes/nova/", views.requisition_create, name="requisition_create"),
    path("estoque/requisicoes/<uuid:pk>/", views.requisition_detail, name="requisition_detail"),
]
