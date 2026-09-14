from django.urls import path

from .views import DrugCatalogView, DrugCreateView, DrugUpdateView

app_name = "prescription"

urlpatterns = [
    path("medicamentos/", DrugCatalogView.as_view(), name="drug_catalog"),
    path("medicamentos/novo/", DrugCreateView.as_view(), name="drug_create"),
    path(
        "medicamentos/<uuid:pk>/editar/",
        DrugUpdateView.as_view(),
        name="drug_update",
    ),
]
