import hashlib
import json
import logging

from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.debug import sensitive_post_parameters
from django.views.decorators.http import require_http_methods

from apps.clinical.pep.permissions import accessible_patients, is_internal_professional

from .forms import PatientExportForm
from .models import PatientExportReceipt

logger = logging.getLogger(__name__)


@sensitive_post_parameters()
@login_required
@require_http_methods(["GET", "POST"])
def patient_export(request):
    if not is_internal_professional(request.user) or not request.user.has_perm(
        "interoperability.export_patient"
    ):
        raise PermissionDenied

    form = PatientExportForm(request.POST if request.method == "POST" else None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic(), set_actor(request.user):
                patient = (
                    accessible_patients(request.user)
                    .filter(pk=form.cleaned_data["patient"].pk)
                    .first()
                )
                if patient is None:
                    form.add_error("patient", "Selecione um paciente disponível.")
                else:
                    payload = {
                        "resourceType": "Patient",
                        "id": str(patient.pk),
                        "active": patient.active,
                        "name": [{"text": patient.full_name}],
                        "birthDate": patient.birth_date.isoformat(),
                    }
                    content = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode(
                        "utf-8"
                    )
                    receipt = PatientExportReceipt.objects.create(
                        patient=patient,
                        created_by=request.user,
                        content_sha256=hashlib.sha256(content).hexdigest(),
                    )
                    accessed.send(type(patient), instance=patient)
            if patient is not None:
                return HttpResponse(
                    content,
                    content_type="application/fhir+json",
                    headers={
                        "Content-Disposition": (
                            f'attachment; filename="patient-export-{receipt.pk}.json"'
                        ),
                    },
                )
        except DatabaseError:
            logger.error("Falha ao persistir auditoria de exportação de paciente.")
            return HttpResponse(
                "Não foi possível gerar o arquivo. Tente novamente mais tarde.",
                status=503,
                content_type="text/plain; charset=utf-8",
            )

    return render(request, "interop/export_form.html", {"form": form})
