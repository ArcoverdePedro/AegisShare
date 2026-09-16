from django.urls import path

from . import views

app_name = "pep"

urlpatterns = [
    path("pacientes/", views.patient_list, name="patient_list"),
    path("pacientes/novo/", views.patient_create, name="patient_create"),
    path("pacientes/<uuid:pk>/", views.patient_detail, name="patient_detail"),
    path(
        "pacientes/<uuid:patient_id>/encontros/",
        views.encounter_list,
        name="encounter_list",
    ),
    path(
        "pacientes/<uuid:patient_id>/encontros/novo/",
        views.encounter_create,
        name="encounter_create",
    ),
    path(
        "encontros/<uuid:pk>/",
        views.encounter_detail,
        name="encounter_detail",
    ),
    path(
        "encontros/<uuid:encounter_id>/evolucoes/nova/",
        views.evolution_create,
        name="evolution_create",
    ),
    path(
        "evolucoes/<uuid:pk>/",
        views.evolution_detail,
        name="evolution_detail",
    ),
    path(
        "evolucoes/<uuid:pk>/adendo/",
        views.evolution_amendment_create,
        name="evolution_amendment_create",
    ),
]
