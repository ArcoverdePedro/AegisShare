from apps.clinical.pep.permissions import accessible_patients

from .models import MedicationRequest
from .permissions import PERM_VIEW, has_rx_permission


def visible_medication_requests(user):
    queryset = MedicationRequest.objects.select_related(
        "encounter__patient", "authored_by", "validated_by"
    )
    if not has_rx_permission(user, PERM_VIEW):
        return queryset.none()
    patients = accessible_patients(user)
    return queryset.filter(encounter__patient__in=patients).distinct()
