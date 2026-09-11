from django.urls import path

from .views import ManifestView, OfflineView, ServiceWorkerView

app_name = "pwa"

urlpatterns = [
    path("manifest.webmanifest", ManifestView.as_view(), name="manifest"),
    path("service-worker.js", ServiceWorkerView.as_view(), name="service_worker"),
    path("offline/", OfflineView.as_view(), name="offline"),
]
