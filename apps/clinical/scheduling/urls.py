from django.urls import path

from . import views

app_name = "scheduling"
urlpatterns = [
    path("agenda/", views.agenda, name="agenda"),
    path("agenda/fila/", views.queue, name="queue"),
    path("agenda/horarios/novo/", views.slot_create, name="slot_create"),
    path("agenda/horarios/<uuid:pk>/bloquear/", views.slot_block, name="slot_block"),
    path(
        "agenda/pacientes/<uuid:patient_id>/agendar/",
        views.appointment_create,
        name="appointment_create",
    ),
    path("agenda/agendamentos/<uuid:pk>/", views.appointment_detail, name="appointment_detail"),
]
