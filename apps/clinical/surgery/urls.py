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
]
