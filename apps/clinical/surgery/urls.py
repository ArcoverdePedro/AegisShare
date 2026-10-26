from django.urls import path

from . import views

app_name = "surgery"
urlpatterns = [
    path("cirurgias/solicitacoes/", views.case_list, name="case_list"),
    path(
        "cirurgias/encontros/<uuid:encounter_id>/solicitacoes/nova/",
        views.case_create,
        name="case_create",
    ),
    path("cirurgias/solicitacoes/<uuid:pk>/", views.case_detail, name="case_detail"),
    path("cirurgias/mapa/", views.room_map, name="room_map"),
    path("cirurgias/solicitacoes/<uuid:pk>/agendar/", views.schedule_create, name="schedule_create"),
    path(
        "cirurgias/solicitacoes/<uuid:pk>/agendamentos/<uuid:schedule_id>/cancelar/",
        views.schedule_cancel,
        name="schedule_cancel",
    ),
]
