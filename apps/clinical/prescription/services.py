from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.clinical.pep.models import Encounter

from .events import emit_prescription_event
from .models import Drug, MedicationRequest, MedicationRequestItem
from .permissions import can_prescribe_for_encounter


class PrescriptionStateError(RuntimeError):
    """Conflito de estado seguro, sem detalhes internos ou PHI."""


class PrescriptionItemError(PrescriptionStateError):
    pass


def _require_author(request, actor):
    if request.authored_by_id != actor.pk:
        raise PermissionDenied


def _require_prescribe_access(request, actor):
    if not can_prescribe_for_encounter(actor, request.encounter):
        raise PermissionDenied
    _require_author(request, actor)


def create_medication_request(*, encounter_id, actor, replaces_id=None):
    """Cria uma prescrição em DRAFT para um encontro aberto e autorizado."""
    with transaction.atomic():
        encounter = (
            Encounter.objects.select_for_update()
            .select_related("patient")
            .get(pk=encounter_id)
        )
        if not can_prescribe_for_encounter(actor, encounter):
            raise PermissionDenied
        if encounter.status != Encounter.Status.OPEN:
            raise PrescriptionStateError("A prescrição exige encontro aberto.")

        replaces = None
        if replaces_id:
            replaces = (
                MedicationRequest.objects.select_for_update()
                .select_related("encounter__patient")
                .get(pk=replaces_id)
            )
            if not can_prescribe_for_encounter(actor, replaces.encounter):
                raise PermissionDenied
            if replaces.encounter_id != encounter.pk:
                raise PrescriptionStateError(
                    "A prescrição substituída deve pertencer ao mesmo encontro."
                )
            if replaces.status == MedicationRequest.Status.DRAFT:
                raise PrescriptionStateError(
                    "Um rascunho deve ser editado diretamente, não substituído."
                )
            if replaces.replacements.exists():
                raise PrescriptionStateError(
                    "A prescrição informada já possui uma substituição."
                )

        return MedicationRequest.objects.create(
            encounter=encounter,
            authored_by=actor,
            replaces=replaces,
        )


def add_medication_request_item(
    *,
    request_id,
    actor,
    drug_id,
    dose,
    dose_unit,
    route,
    frequency,
    sequence,
    duration_value=None,
    duration_unit="",
    instructions="",
):
    """Adiciona item somente enquanto a prescrição permanece em DRAFT."""
    with transaction.atomic():
        request = (
            MedicationRequest.objects.select_for_update()
            .select_related("encounter__patient")
            .get(pk=request_id)
        )
        _require_prescribe_access(request, actor)
        if request.status != MedicationRequest.Status.DRAFT:
            raise PrescriptionStateError(
                "Itens só podem ser alterados enquanto a prescrição está em rascunho."
            )
        if request.encounter.status != Encounter.Status.OPEN:
            raise PrescriptionStateError("O encontro não está mais aberto.")

        max_items = int(getattr(settings, "RX_MAX_ITEMS_PER_REQUEST", 50))
        if request.items.count() >= max_items:
            raise PrescriptionItemError(
                "A prescrição atingiu o limite máximo de itens permitido."
            )

        drug = Drug.objects.get(pk=drug_id)
        if not drug.active:
            raise PrescriptionItemError("Medicamento inativo não pode ser prescrito.")
        if request.items.filter(drug=drug).exists():
            raise PrescriptionItemError(
                "O mesmo medicamento não pode ser incluído duas vezes no mesmo rascunho."
            )

        return MedicationRequestItem.objects.create(
            medication_request=request,
            drug=drug,
            dose=dose,
            dose_unit=dose_unit,
            route=route,
            frequency=frequency,
            duration_value=duration_value,
            duration_unit=duration_unit,
            instructions=instructions,
            sequence=sequence,
        )


def remove_medication_request_item(*, request_id, item_id, actor):
    """Remove item apenas do rascunho do próprio prescritor."""
    with transaction.atomic():
        request = (
            MedicationRequest.objects.select_for_update()
            .select_related("encounter__patient")
            .get(pk=request_id)
        )
        _require_prescribe_access(request, actor)
        if request.status != MedicationRequest.Status.DRAFT:
            raise PrescriptionStateError(
                "Itens submetidos não podem ser removidos."
            )
        item = request.items.select_for_update().get(pk=item_id)
        item.delete()


def submit_medication_request(*, request_id, actor):
    """Faz a transição DRAFT -> SUBMITTED e congela a edição comum."""
    with transaction.atomic():
        request = (
            MedicationRequest.objects.select_for_update()
            .select_related("encounter__patient")
            .get(pk=request_id)
        )
        _require_prescribe_access(request, actor)
        if request.status != MedicationRequest.Status.DRAFT:
            raise PrescriptionStateError("A prescrição não está em rascunho.")
        if request.encounter.status != Encounter.Status.OPEN:
            raise PrescriptionStateError("O encontro não está mais aberto.")
        if not request.items.exists():
            raise PrescriptionItemError(
                "Inclua pelo menos um medicamento antes de submeter a prescrição."
            )

        request.status = MedicationRequest.Status.SUBMITTED
        request.submitted_at = timezone.now()
        request.save(update_fields=["status", "submitted_at", "updated_at"])
        emit_prescription_event(
            event_type="prescription.created",
            prescription_id=request.pk,
            encounter_id=request.encounter_id,
            status=request.status,
        )
        return request
