import json
import uuid

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.cache import patch_vary_headers
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients
from apps.pwa.session import session_fingerprint

from .forms import VitalSignsRecordForm
from .models import VitalSignsRecord
from .permissions import (
    PERM_RECORD_VITALS,
    PERM_VIEW,
    can_record_vitals,
    has_nursing_permission,
)
from .services import (
    MEASURE_FIELDS,
    VitalSignsIdempotencyConflictError,
    record_vital_signs,
)

OFFLINE_OPERATION_TYPE = "nursing.vitals.record"


def _no_store(response):
    response["Cache-Control"] = "private, no-store, max-age=0"
    patch_vary_headers(response, ("Cookie", "HX-Request"))
    return response


def _scoped_encounter_or_404(user, pk):
    return get_object_or_404(
        Encounter.objects.select_related("patient", "responsible_professional").filter(
            patient__in=accessible_patients(user)
        ),
        pk=pk,
    )


def _read_json_object(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _safe_uuid(value):
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _sync_conflict(reason, *, status=409):
    return _no_store(
        JsonResponse(
            {"status": "conflict", "reason": reason},
            status=status,
        )
    )


def _offline_context(request):
    return {"offline_session_fingerprint": session_fingerprint(request) or ""}


@login_required
@require_GET
def nursing_worklist(request):
    if not has_nursing_permission(request.user, PERM_VIEW):
        raise PermissionDenied

    encounters = (
        Encounter.objects.select_related("patient", "responsible_professional")
        .filter(patient__in=accessible_patients(request.user))
        .order_by("-started_at")
        .distinct()
    )
    paginator = Paginator(encounters, 25)
    page_obj = paginator.get_page(request.GET.get("page"))
    return _no_store(
        render(
            request,
            "clinical/nursing/worklist.html",
            {"encounters": page_obj.object_list, "page_obj": page_obj},
        )
    )


@login_required
@require_GET
def nursing_encounter(request, pk):
    if not has_nursing_permission(request.user, PERM_VIEW):
        raise PermissionDenied

    encounter = _scoped_encounter_or_404(request.user, pk)
    vital_signs = encounter.nursing_vital_signs.select_related(
        "recorded_by", "replaces"
    ).all()[:50]
    return _no_store(
        render(
            request,
            "clinical/nursing/encounter.html",
            {
                "encounter": encounter,
                "vital_signs": vital_signs,
                "can_record_vitals": can_record_vitals(request.user, encounter),
            },
        )
    )


@login_required
@require_http_methods(["GET", "POST"])
def vitals_create(request, encounter_id):
    if not has_nursing_permission(request.user, PERM_RECORD_VITALS):
        raise PermissionDenied

    encounter = _scoped_encounter_or_404(request.user, encounter_id)
    if not can_record_vitals(request.user, encounter):
        raise PermissionDenied

    form = VitalSignsRecordForm(
        request.POST or None,
        encounter=encounter,
    )
    if request.method == "POST" and form.is_valid():
        record_vital_signs(
            encounter=encounter,
            actor=request.user,
            data=form.cleaned_data,
        )
        messages.success(request, "Sinais vitais registrados com sucesso.")
        return _no_store(redirect("nursing:encounter", pk=encounter.pk))

    return _no_store(
        render(
            request,
            "clinical/nursing/vitals_form.html",
            {
                "form": form,
                "encounter": encounter,
                **_offline_context(request),
            },
        )
    )


@login_required
@require_http_methods(["GET", "POST"])
def vitals_correct(request, record_id):
    if not has_nursing_permission(request.user, PERM_RECORD_VITALS):
        raise PermissionDenied

    original = get_object_or_404(
        VitalSignsRecord.objects.select_related(
            "encounter__patient",
            "encounter__responsible_professional",
            "recorded_by",
        ).filter(encounter__patient__in=accessible_patients(request.user)),
        pk=record_id,
    )
    encounter = original.encounter
    if not can_record_vitals(request.user, encounter):
        raise PermissionDenied

    initial = None
    if request.method == "GET":
        initial = {
            field_name: getattr(original, field_name)
            for field_name in VitalSignsRecordForm.Meta.fields
        }

    form = VitalSignsRecordForm(
        request.POST or None,
        encounter=encounter,
        initial=initial,
    )
    if request.method == "POST" and form.is_valid():
        record_vital_signs(
            encounter=encounter,
            actor=request.user,
            data=form.cleaned_data,
            replaces=original,
        )
        messages.success(request, "Correção de sinais vitais registrada com sucesso.")
        return _no_store(redirect("nursing:encounter", pk=encounter.pk))

    return _no_store(
        render(
            request,
            "clinical/nursing/vitals_form.html",
            {
                "form": form,
                "encounter": encounter,
                "is_correction": True,
                "original_record": original,
                **_offline_context(request),
            },
        )
    )


@login_required
@require_POST
def vitals_sync(request):
    if not has_nursing_permission(request.user, PERM_RECORD_VITALS):
        return _sync_conflict("permission_denied", status=403)

    body = _read_json_object(request)
    expected_keys = {
        "idempotency_key",
        "operation_type",
        "user_session_fingerprint",
        "payload",
    }
    if body is None or set(body) != expected_keys:
        return _sync_conflict("invalid_envelope", status=400)
    if body["operation_type"] != OFFLINE_OPERATION_TYPE:
        return _sync_conflict("invalid_operation", status=400)

    current_fingerprint = session_fingerprint(request)
    if (
        not current_fingerprint
        or body["user_session_fingerprint"] != current_fingerprint
    ):
        return _sync_conflict("session_changed")

    idempotency_key = _safe_uuid(body["idempotency_key"])
    payload = body["payload"]
    if idempotency_key is None or not isinstance(payload, dict):
        return _sync_conflict("invalid_envelope", status=400)

    allowed_payload_keys = {"encounter_id", "recorded_at", "replaces_id", "measurements"}
    required_payload_keys = {"encounter_id", "recorded_at", "measurements"}
    if not required_payload_keys.issubset(payload) or not set(payload).issubset(
        allowed_payload_keys
    ):
        return _sync_conflict("invalid_payload", status=400)

    measurements = payload["measurements"]
    if not isinstance(measurements, dict) or not set(measurements).issubset(
        MEASURE_FIELDS
    ):
        return _sync_conflict("invalid_payload", status=400)

    encounter_id = _safe_uuid(payload["encounter_id"])
    if encounter_id is None:
        return _sync_conflict("invalid_payload", status=400)

    encounter = (
        Encounter.objects.select_related("patient", "responsible_professional")
        .filter(pk=encounter_id)
        .first()
    )
    if encounter is None or not can_record_vitals(request.user, encounter):
        return _sync_conflict("encounter_unavailable")

    replaces = None
    replaces_id = payload.get("replaces_id")
    if replaces_id:
        replaces_uuid = _safe_uuid(replaces_id)
        if replaces_uuid is None:
            return _sync_conflict("replacement_unavailable")
        replaces = VitalSignsRecord.objects.filter(
            pk=replaces_uuid,
            encounter=encounter,
        ).first()
        if replaces is None:
            return _sync_conflict("replacement_unavailable")

    form = VitalSignsRecordForm(
        {
            "recorded_at": payload["recorded_at"],
            **measurements,
        },
        encounter=encounter,
    )
    if not form.is_valid():
        return _sync_conflict("validation_conflict")

    try:
        record = record_vital_signs(
            encounter=encounter,
            actor=request.user,
            data=form.cleaned_data,
            idempotency_key=idempotency_key,
            replaces=replaces,
            origin=VitalSignsRecord.Origin.OFFLINE_SYNC,
        )
    except VitalSignsIdempotencyConflictError:
        return _sync_conflict("idempotency_conflict")
    except (PermissionDenied, Encounter.DoesNotExist):
        return _sync_conflict("encounter_unavailable")
    except ValidationError:
        return _sync_conflict("validation_conflict")

    return _no_store(
        JsonResponse(
            {
                "status": "synced",
                "record_id": str(record.pk),
            }
        )
    )
