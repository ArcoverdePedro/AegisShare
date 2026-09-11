from django.urls import path

from apps.clinical.pep.consumers import PatientClinicalConsumer

from . import consumers

websocket_urlpatterns = [
    path("ws/chat/<uuid:conversation_id>/", consumers.ChatConsumer.as_asgi()),
    path(
        "ws/clinical/patients/<uuid:patient_id>/",
        PatientClinicalConsumer.as_asgi(),
    ),
]
