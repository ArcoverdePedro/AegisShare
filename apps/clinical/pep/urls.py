from django.urls import path

from .views import PatientCreateView, PatientDetailView, PatientListView

app_name = "pep"

urlpatterns = [
    path("pacientes/", PatientListView.as_view(), name="patient_list"),
    path("pacientes/novo/", PatientCreateView.as_view(), name="patient_create"),
    path("pacientes/<uuid:pk>/", PatientDetailView.as_view(), name="patient_detail"),
]
