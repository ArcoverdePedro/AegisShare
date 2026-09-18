import hashlib
import json
import logging

from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods

from aegis_share.services.crypto import CryptoConfigurationError
from apps.clinical.pep.permissions import accessible_patients, is_internal_professional

from .forms import LaboratoryInboxFilterForm, LaboratoryInboxForm, PatientExportForm
from .lab_inbox import metadata_receipts, receive_laboratory_file, require_inbox_permission
from .models import LaboratoryInboxReceipt, PatientExportReceipt

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


@login_required
@require_GET
def lab_inbox_list(request):
    require_inbox_permission(request.user)
    form = LaboratoryInboxFilterForm(request.GET, user=request.user)
    queryset = metadata_receipts(request.user)
    if not form.is_valid():
        queryset = queryset.none()
    elif form.cleaned_data["source"]:
        queryset = queryset.filter(source=form.cleaned_data["source"])
    page = Paginator(queryset, 25).get_page(request.GET.get("page"))
    page.object_list = list(page.object_list)
    with transaction.atomic(), set_actor(request.user):
        for item in page.object_list:
            accessed.send(LaboratoryInboxReceipt, instance=item)
    return render(request, "interop/inbox_list.html", {"form": form, "page_obj": page})


@login_required
@require_GET
def lab_inbox_detail(request, pk):
    require_inbox_permission(request.user)
    item = get_object_or_404(metadata_receipts(request.user), pk=pk)
    with set_actor(request.user):
        accessed.send(LaboratoryInboxReceipt, instance=item)
    return render(request, "interop/inbox_detail.html", {"item": item})


@sensitive_post_parameters()
@sensitive_variables()
@login_required
@require_http_methods(["GET", "POST"])
def lab_inbox_receive(request):
    require_inbox_permission(request.user, receive=True)
    form = LaboratoryInboxForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        try:
            item = receive_laboratory_file(
                user=request.user,
                source_id=form.cleaned_data["source"].pk,
                uploaded_file=form.cleaned_data["file"],
            )
        except ValidationError as exc:
            if exc.code == "too_large":
                return HttpResponse("O arquivo excede o limite de 1 MiB.", status=413)
            form.add_error("file", exc)
        except DatabaseError, CryptoConfigurationError:
            logger.error("Falha ao persistir recebimento laboratorial.")
            return HttpResponse(
                "Não foi possível receber o arquivo. Consulte os recibos e tente novamente.",
                status=503,
            )
        else:
            return redirect("interoperability:lab_inbox_detail", pk=item.pk)
    return render(request, "interop/inbox_form.html", {"form": form})
