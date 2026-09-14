from apps.clinical.pep.permissions import accessible_patients, can_access_patient

from .models import Location, UserLocationAccess


PERM_VIEW_BED_MAP = "adt.view_bed_map"
PERM_ADMIT = "adt.admit_patient"
PERM_TRANSFER = "adt.transfer_patient"
PERM_DISCHARGE = "adt.discharge_patient"
PERM_MANAGE_BED = "adt.manage_bed_status"
PERM_VIEW_HISTORY = "adt.view_movement_history"


def _is_authenticated_internal(user):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_client", lambda: False)():
        return False
    return True


def has_adt_permission(user, codename):
    if not _is_authenticated_internal(user):
        return False
    if getattr(user, "is_admin", lambda: False)():
        return True
    return user.has_perm(codename)


def accessible_locations(user):
    queryset = Location.objects.filter(active=True)
    if not _is_authenticated_internal(user):
        return queryset.none()
    if getattr(user, "is_admin", lambda: False)():
        return queryset
    return queryset.filter(user_accesses__user=user).distinct()


def can_access_location(user, location):
    if not _is_authenticated_internal(user):
        return False
    if getattr(user, "is_admin", lambda: False)():
        return True
    return UserLocationAccess.objects.filter(user=user, location=location).exists()


def can_access_bed(user, bed):
    return can_access_location(user, bed.location)


def can_view_bed_map(user):
    return has_adt_permission(user, PERM_VIEW_BED_MAP)


def can_admit(user):
    return has_adt_permission(user, PERM_ADMIT)


def can_admit_to_bed(user, encounter, bed):
    return (
        can_admit(user)
        and can_access_bed(user, bed)
        and can_access_patient(user, encounter.patient)
    )


def can_manage_bed_status(user):
    return has_adt_permission(user, PERM_MANAGE_BED)


def can_view_movement_history(user):
    return has_adt_permission(user, PERM_VIEW_HISTORY)


def can_view_occupant_phi(user, patient):
    if not can_view_bed_map(user):
        return False
    return accessible_patients(user).filter(pk=patient.pk).exists()
