from django.urls import path

from . import views

app_name = "nursing"

urlpatterns = [
    path("enfermagem/", views.nursing_worklist, name="worklist"),
    path(
        "enfermagem/encontros/<uuid:pk>/",
        views.nursing_encounter,
        name="encounter",
    ),
    path(
        "enfermagem/encontros/<uuid:encounter_id>/sinais-vitais/novo/",
        views.vitals_create,
        name="vitals_create",
    ),
    path(
        "enfermagem/sinais-vitais/<uuid:record_id>/corrigir/",
        views.vitals_correct,
        name="vitals_correct",
    ),
    path(
        "enfermagem/sinais-vitais/sincronizar/",
        views.vitals_sync,
        name="vitals_sync",
    ),
]
