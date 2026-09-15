from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import can_access_patient

PERM_VIEW = "nursing.view_nursing"
PERM_RECORD_VITALS = "nursing.record_vitals"
PERM_ADMINISTER_MEDICATION = "nursing.administer_medication"


def _is_internal(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_client", lambda: False)():
        return False
    return bool(
        getattr(user, "is_admin", lambda: False)()
        or getattr(user, "is_employee", lambda: False)()
    )


def has_nursing_permission(user, permission):
    return _is_internal(user) and user.has_perm(permission)


def can_view_nursing(user, encounter):
    return has_nursing_permission(user, PERM_VIEW) and can_access_patient(
        user, encounter.patient
    )


def can_record_vitals(user, encounter):
    return (
        has_nursing_permission(user, PERM_RECORD_VITALS)
        and encounter.status == Encounter.Status.OPEN
        and can_access_patient(user, encounter.patient)
    )


def can_administer_dispense_item(user, dispense_item):
    encounter = dispense_item.dispense.medication_request.encounter
    return (
        has_nursing_permission(user, PERM_ADMINISTER_MEDICATION)
        and encounter.status == Encounter.Status.OPEN
        and can_access_patient(user, encounter.patient)
    )
