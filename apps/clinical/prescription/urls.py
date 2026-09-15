from django.urls import path

from .views import (
    DrugCatalogView,
    DrugCreateView,
    DrugUpdateView,
    PharmacyStockView,
    dispense_create,
    dispense_detail,
    dispense_list,
    prescription_cancel,
    prescription_create,
    prescription_detail,
    prescription_list,
    prescription_submit,
    prescription_validate,
)

app_name = "prescription"

urlpatterns = [
    path("prescricoes/", prescription_list, name="prescription_list"),
    path("prescricoes/nova/", prescription_create, name="prescription_create"),
    path("prescricoes/<uuid:pk>/", prescription_detail, name="prescription_detail"),
    path("prescricoes/<uuid:pk>/submeter/", prescription_submit, name="prescription_submit"),
    path("prescricoes/<uuid:pk>/validar/", prescription_validate, name="prescription_validate"),
    path("prescricoes/<uuid:pk>/cancelar/", prescription_cancel, name="prescription_cancel"),
    path("prescricoes/<uuid:pk>/dispensar/", dispense_create, name="dispense_create"),
    path("dispensacoes/", dispense_list, name="dispense_list"),
    path("dispensacoes/<uuid:pk>/", dispense_detail, name="dispense_detail"),
    path("medicamentos/", DrugCatalogView.as_view(), name="drug_catalog"),
    path("medicamentos/novo/", DrugCreateView.as_view(), name="drug_create"),
    path(
        "medicamentos/<uuid:pk>/editar/",
        DrugUpdateView.as_view(),
        name="drug_update",
    ),
    path("estoque-farmacia/", PharmacyStockView.as_view(), name="pharmacy_stock"),
]
