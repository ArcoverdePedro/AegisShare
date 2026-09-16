from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import can_access_patient, is_internal_professional
from apps.clinical.prescription.models import MedicationRequest

PERM_VIEW = "nursing.view_nursing"
PERM_RECORD_VITALS = "nursing.record_vitals"
PERM_ADMINISTER_MEDICATION = "nursing.administer_medication"


def has_nursing_permission(user, permission):
    return is_internal_professional(user) and user.has_perm(permission)


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
    medication_request = dispense_item.dispense.medication_request
    encounter = medication_request.encounter
    return (
        has_nursing_permission(user, PERM_ADMINISTER_MEDICATION)
        and encounter.status == Encounter.Status.OPEN
        and medication_request.status == MedicationRequest.Status.VALIDATED
        and can_access_patient(user, encounter.patient)
    )
