from django.urls import path

from . import views

app_name = "billing"
urlpatterns = [
    path("faturamento/contas/", views.account_list, name="account_list"),
    path(
        "faturamento/encontros/<uuid:encounter_id>/conta/abrir/",
        views.account_open,
        name="account_open",
    ),
    path("faturamento/contas/<uuid:pk>/", views.account_detail, name="account_detail"),
    path("faturamento/contas/<uuid:pk>/itens/novo/", views.item_create, name="item_create"),
]
