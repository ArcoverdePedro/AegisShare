from django.urls import path

from . import views

app_name = "interoperability"

urlpatterns = [path("interop/exportar/", views.patient_export, name="patient_export")]
