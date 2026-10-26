from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, F
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.admin.billing.models import BillingItem
from apps.admin.billing.totals import items_total
from apps.admin.inventory.models import MaterialBalance
from apps.clinical.adt.models import Bed, BedOccupancy
from apps.clinical.lis.models import Specimen, SpecimenEvent
from apps.clinical.scheduling.models import Appointment


def _ratio(numerator, denominator):
    return round(100 * numerator / denominator, 1) if denominator else None


def indicators(*, days):
    """Agregados no banco; nenhum indicador expoe paciente individual."""
    now = timezone.now()
    since = now - timedelta(days=days)
    beds = Bed.objects.filter(active=True).exclude(
        operational_status=Bed.OperationalStatus.OUT_OF_SERVICE
    )
    occupied = BedOccupancy.objects.filter(ended_at__isnull=True, bed__in=beds).count()
    attended = Appointment.objects.filter(
        slot__starts_at__gte=since,
        slot__starts_at__lte=now,
        status__in=[
            Appointment.Status.NO_SHOW,
            Appointment.Status.CHECKED_IN,
            Appointment.Status.CALLED,
        ],
    )
    no_show = attended.filter(status=Appointment.Status.NO_SHOW).count()
    wait = Appointment.objects.filter(called_at__gte=since, checked_in_at__isnull=False).aggregate(
        wait=Avg(F("called_at") - F("checked_in_at"))
    )["wait"]
    specimens = Specimen.objects.filter(collected_at__gte=since)
    rejected = specimens.filter(events__kind=SpecimenEvent.Kind.REJECTED).count()
    billed = BillingItem.objects.filter(recorded_at__gte=since)
    return [
        {
            "name": "Ocupação de leitos (agora)",
            "value": _ratio(occupied, beds.count()),
            "unit": "%",
            "definition": f"{occupied} ocupados / {beds.count()} leitos ativos fora de 'fora de serviço' — ADT",
        },
        {
            "name": "Leitos aguardando higienização (agora)",
            "value": beds.filter(operational_status=Bed.OperationalStatus.CLEANING).count(),
            "unit": "leitos",
            "definition": "estado CLEANING — ADT",
        },
        {
            "name": "Faltas na agenda",
            "value": _ratio(no_show, attended.count()),
            "unit": "%",
            "definition": f"{no_show} faltas / {attended.count()} horários já iniciados com chegada ou falta — Agenda",
        },
        {
            "name": "Espera chegada → chamada",
            "value": round(wait.total_seconds() / 60, 1) if wait else None,
            "unit": "min (média)",
            "definition": "chamados na janela com chegada registrada — Agenda",
        },
        {
            "name": "Rejeição de amostras",
            "value": _ratio(rejected, specimens.count()),
            "unit": "%",
            "definition": f"{rejected} rejeitadas / {specimens.count()} coletadas na janela — LIS",
        },
        {
            "name": "Lotes vencidos com saldo",
            "value": MaterialBalance.objects.filter(
                quantity__gt=0, expires_on__lt=timezone.localdate()
            ).count(),
            "unit": "lotes",
            "definition": "saldo > 0 e validade anterior a hoje — Materiais",
        },
        {
            "name": "Produção lançada em contas",
            "value": items_total(billed.filter(reverses__isnull=True))
            - items_total(billed.filter(reverses__isnull=False)),
            "unit": "BRL (líquido de estornos)",
            "definition": "itens registrados na janela, em preparação (sem cobrança emitida) — Faturamento",
        },
    ]


@login_required
@require_GET
def indicator_panel(request):
    if not request.user.is_admin():
        raise PermissionDenied
    try:
        days = min(max(int(request.GET.get("dias", 30)), 1), 366)
    except ValueError:
        days = 30
    response = render(
        request,
        "admin/indicators/panel.html",
        {"indicators": indicators(days=days), "days": days, "now": timezone.localtime()},
    )
    response["Cache-Control"] = "private, no-store"
    return response
