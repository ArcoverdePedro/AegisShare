from apps.clinical.pep.permissions import can_access_patient, is_internal_professional

PERM_VIEW = "prescription.view_medication_request"
PERM_PRESCRIBE = "prescription.prescribe_medication"
PERM_VALIDATE = "prescription.validate_medication_request"
PERM_CANCEL = "prescription.cancel_medication_request"
PERM_VIEW_DISPENSE = "prescription.view_medication_dispense"
PERM_DISPENSE = "prescription.dispense_medication"
PERM_VIEW_DRUG = "prescription.view_drug"
PERM_MANAGE_CATALOG = "prescription.manage_drug_catalog"
PERM_VIEW_STOCK = "prescription.view_pharmacy_stock"
PERM_MANAGE_STOCK = "prescription.manage_pharmacy_stock"


def has_rx_permission(user, permission):
    """A função técnica não substitui capacidade profissional explícita."""
    return is_internal_professional(user) and user.has_perm(permission)


def can_view_prescription(user, medication_request):
    return has_rx_permission(user, PERM_VIEW) and can_access_patient(
        user, medication_request.encounter.patient
    )


def can_prescribe_for_encounter(user, encounter):
    return has_rx_permission(user, PERM_PRESCRIBE) and can_access_patient(
        user, encounter.patient
    )


def can_validate_prescription(user, medication_request):
    return has_rx_permission(user, PERM_VALIDATE) and can_access_patient(
        user, medication_request.encounter.patient
    )


def can_cancel_prescription(user, medication_request):
    return has_rx_permission(user, PERM_CANCEL) and can_access_patient(
        user, medication_request.encounter.patient
    )


def can_dispense_prescription(user, medication_request):
    return has_rx_permission(user, PERM_DISPENSE) and can_access_patient(
        user, medication_request.encounter.patient
    )


def can_view_dispense(user, dispense):
    return has_rx_permission(user, PERM_VIEW_DISPENSE) and can_access_patient(
        user, dispense.medication_request.encounter.patient
    )


def can_view_drug_catalog(user):
    return has_rx_permission(user, PERM_VIEW_DRUG)


def can_manage_reference_data(user):
    return has_rx_permission(user, PERM_MANAGE_CATALOG)


def can_view_stock(user):
    return has_rx_permission(user, PERM_VIEW_STOCK)


def can_manage_stock(user):
    return has_rx_permission(user, PERM_MANAGE_STOCK)
