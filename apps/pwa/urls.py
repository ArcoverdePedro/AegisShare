from django.urls import path

from .views import (
    ManifestView,
    OfflineView,
    PushConfigView,
    PushSubscribeView,
    PushUnsubscribeView,
    PwaIconView,
    ServiceWorkerView,
)

app_name = "pwa"

urlpatterns = [
    path("manifest.webmanifest", ManifestView.as_view(), name="manifest"),
    path("service-worker.js", ServiceWorkerView.as_view(), name="service_worker"),
    path("pwa/icons/<int:size>.png", PwaIconView.as_view(), name="icon"),
    path("offline/", OfflineView.as_view(), name="offline"),
    path("pwa/push/config/", PushConfigView.as_view(), name="push_config"),
    path("pwa/push/subscribe/", PushSubscribeView.as_view(), name="push_subscribe"),
    path(
        "pwa/push/unsubscribe/",
        PushUnsubscribeView.as_view(),
        name="push_unsubscribe",
    ),
]
