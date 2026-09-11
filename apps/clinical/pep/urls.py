from django.urls import path

from .views import (
    EncounterCreateView,
    EncounterDetailView,
    EncounterListView,
    PatientCreateView,
    PatientDetailView,
    PatientListView,
)

app_name = "pep"

urlpatterns = [
    path("pacientes/", PatientListView.as_view(), name="patient_list"),
    path("pacientes/novo/", PatientCreateView.as_view(), name="patient_create"),
    path("pacientes/<uuid:pk>/", PatientDetailView.as_view(), name="patient_detail"),
    path(
        "pacientes/<uuid:patient_id>/encontros/",
        EncounterListView.as_view(),
        name="encounter_list",
    ),
    path(
        "pacientes/<uuid:patient_id>/encontros/novo/",
        EncounterCreateView.as_view(),
        name="encounter_create",
    ),
    path(
        "encontros/<uuid:pk>/",
        EncounterDetailView.as_view(),
        name="encounter_detail",
    ),
]
