from django.db.models import Exists, OuterRef, Prefetch

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients

from .models import Admission, Bed, BedOccupancy
from .permissions import accessible_locations


def available_beds_for_user(user):
    active_occupancy = BedOccupancy.objects.filter(
        bed_id=OuterRef("pk"),
        ended_at__isnull=True,
    )
    return (
        Bed.objects.filter(
            active=True,
            operational_status=Bed.OperationalStatus.AVAILABLE,
            location__in=accessible_locations(user),
        )
        .annotate(has_active_occupancy=Exists(active_occupancy))
        .filter(has_active_occupancy=False)
        .select_related("location")
        .order_by("location__name", "code")
    )


def admissible_encounters_for_user(user):
    return (
        Encounter.objects.filter(
            patient__in=accessible_patients(user),
            encounter_type=Encounter.Type.INPATIENT,
            status=Encounter.Status.OPEN,
            adt_admission__isnull=True,
        )
        .select_related("patient")
        .order_by("-started_at")
    )


def admissions_for_user(user):
    patient_ids = accessible_patients(user).order_by().values("pk")
    queryset = Admission.objects.filter(encounter__patient_id__in=patient_ids)
    if not getattr(user, "is_admin", lambda: False)():
        queryset = queryset.filter(
            occupancies__bed__location__in=accessible_locations(user)
        )
    return queryset.select_related("encounter__patient", "admitted_by").distinct()


def active_admissions_for_user(user):
    active_occupancy = BedOccupancy.objects.filter(
        admission_id=OuterRef("pk"),
        ended_at__isnull=True,
        bed__location__in=accessible_locations(user),
    )
    return (
        Admission.objects.filter(
            encounter__patient__in=accessible_patients(user),
            encounter__status=Encounter.Status.OPEN,
            discharge__isnull=True,
        )
        .annotate(has_active_occupancy=Exists(active_occupancy))
        .filter(has_active_occupancy=True)
        .select_related("encounter__patient", "admitted_by")
        .order_by("-admitted_at")
    )


def bed_map_groups(user):
    active_occupancies = BedOccupancy.objects.filter(ended_at__isnull=True).select_related(
        "admission__encounter__patient"
    )
    beds = (
        Bed.objects.filter(active=True, location__in=accessible_locations(user))
        .select_related("location")
        .prefetch_related(
            Prefetch(
                "occupancies",
                queryset=active_occupancies,
                to_attr="active_occupancies",
            )
        )
        .order_by("location__name", "code")
    )

    visible_patient_ids = set(
        accessible_patients(user).order_by().values_list("pk", flat=True)
    )
    groups = {}
    for bed in beds:
        occupancy = bed.active_occupancies[0] if bed.active_occupancies else None
        status = "OCCUPIED" if occupancy else bed.operational_status
        patient = occupancy.admission.encounter.patient if occupancy else None
        show_phi = bool(patient and patient.pk in visible_patient_ids)
        row = {
            "bed": bed,
            "status": status,
            "occupancy": occupancy,
            "patient": patient if show_phi else None,
            "show_phi": show_phi,
        }
        groups.setdefault(bed.location, []).append(row)
    return list(groups.items())
