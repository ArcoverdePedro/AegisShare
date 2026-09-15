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
]
