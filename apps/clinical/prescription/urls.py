from django.urls import path

from .views import (
    DrugCatalogView,
    DrugCreateView,
    DrugUpdateView,
    MedicationRequestDetailView,
    MedicationRequestListView,
    PharmacyStockView,
)

app_name = "prescription"

urlpatterns = [
    path("prescricoes/", MedicationRequestListView.as_view(), name="prescription_list"),
    path(
        "prescricoes/<uuid:pk>/",
        MedicationRequestDetailView.as_view(),
        name="prescription_detail",
    ),
    path("medicamentos/", DrugCatalogView.as_view(), name="drug_catalog"),
    path("medicamentos/novo/", DrugCreateView.as_view(), name="drug_create"),
    path(
        "medicamentos/<uuid:pk>/editar/",
        DrugUpdateView.as_view(),
        name="drug_update",
    ),
    path("estoque-farmacia/", PharmacyStockView.as_view(), name="pharmacy_stock"),
]
