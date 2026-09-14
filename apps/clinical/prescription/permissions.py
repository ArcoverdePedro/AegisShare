from apps.clinical.pep.permissions import can_access_patient


PERM_VIEW = "prescription.view_prescription"
PERM_PRESCRIBE = "prescription.prescribe_medication"
PERM_VALIDATE = "prescription.validate_prescription"
PERM_DISPENSE = "prescription.dispense_medication"
PERM_MANAGE_STOCK = "prescription.manage_pharmacy_stock"
PERM_ADJUST_STOCK = "prescription.adjust_pharmacy_stock"
PERM_MANAGE_REFERENCE = "prescription.manage_medication_reference"


def _is_internal(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_client", lambda: False)():
        return False
    return bool(
        getattr(user, "is_admin", lambda: False)()
        or getattr(user, "is_employee", lambda: False)()
    )


def has_rx_permission(user, permission):
    if not _is_internal(user):
        return False
    if getattr(user, "is_admin", lambda: False)():
        return True
    return user.has_perm(permission)


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


def can_dispense_prescription(user, medication_request):
    return has_rx_permission(user, PERM_DISPENSE) and can_access_patient(
        user, medication_request.encounter.patient
    )


def can_manage_stock(user):
    return has_rx_permission(user, PERM_MANAGE_STOCK)


def can_adjust_stock(user):
    return has_rx_permission(user, PERM_ADJUST_STOCK)


def can_manage_reference_data(user):
    return has_rx_permission(user, PERM_MANAGE_REFERENCE)
