from django.urls import path

from .views import AdmissionCreateView, AdmissionListView, BedMapPartialView, BedMapView

app_name = "adt"

urlpatterns = [
    path("admissoes/", AdmissionListView.as_view(), name="admission_list"),
    path("admissoes/nova/", AdmissionCreateView.as_view(), name="admission_create"),
    path("leitos/", BedMapView.as_view(), name="bed_map"),
    path("leitos/mapa/", BedMapPartialView.as_view(), name="bed_map_partial"),
]
