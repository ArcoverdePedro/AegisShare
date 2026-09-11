from django.db.models import Q
from django.utils import timezone

from .models import Patient


def is_internal_professional(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    return bool(user.is_admin() or user.is_employee())


def can_create_patient(user) -> bool:
    return is_internal_professional(user)


def accessible_patients(user):
    queryset = Patient.objects.filter(active=True)
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_admin():
        return queryset
    if not user.is_employee():
        return queryset.none()

    now = timezone.now()
    return queryset.filter(
        Q(created_by=user)
        | Q(access_grants__user=user, access_grants__expires_at__isnull=True)
        | Q(access_grants__user=user, access_grants__expires_at__gt=now)
    ).distinct()


def can_access_patient(user, patient: Patient) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_admin():
        return True
    if not user.is_employee():
        return False
    if patient.created_by_id == user.id:
        return True

    now = timezone.now()
    return patient.access_grants.filter(user=user).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=now)
    ).exists()


def can_create_encounter(user, patient: Patient) -> bool:
    return is_internal_professional(user) and can_access_patient(user, patient)
