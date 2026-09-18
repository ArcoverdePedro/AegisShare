from django.urls import path

from . import views

app_name = "interoperability"

urlpatterns = [
    path("interop/exportar/", views.patient_export, name="patient_export"),
    path("interop/laboratorio/", views.lab_inbox_list, name="lab_inbox_list"),
    path("interop/laboratorio/receber/", views.lab_inbox_receive, name="lab_inbox_receive"),
    path("interop/laboratorio/<uuid:pk>/", views.lab_inbox_detail, name="lab_inbox_detail"),
]
