from auditlog.models import LogEntry
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.http import HttpResponseForbidden
from django.shortcuts import render

from aegis_share.models import CustomUser, DocumentRequest
from aegis_share.services.selectors import files_for_user


def home(request):
    if not request.user.is_authenticated:
        return render(request, "home/homesemlogin.html")
    return dashboard(request)


@login_required
def dashboard(request):
    files = files_for_user(request.user)
    totals = files.aggregate(total_bytes=Sum("tamanho_arquivo"))

    if request.user.is_admin():
        clients = CustomUser.objects.filter(nivel_permissao="CLI").count()
        requests_open = DocumentRequest.objects.exclude(
            status__in=["DONE", "CANCELLED"]
        ).count()
        activity = LogEntry.objects.select_related("actor", "content_type").order_by(
            "-timestamp"
        )[:10]
    else:
        clients = 0
        requests_open = DocumentRequest.objects.filter(
            recipient=request.user
        ).exclude(status__in=["DONE", "CANCELLED"]).count()
        activity = (
            LogEntry.objects.filter(actor=request.user)
            .select_related("actor", "content_type")
            .order_by("-timestamp")[:10]
        )

    context = {
        "file_count": files.count(),
        "total_bytes": totals["total_bytes"] or 0,
        "client_count": clients,
        "request_count": requests_open,
        "recent_files": files[:8],
        "activity": activity,
    }
    return render(request, "home/homecomlogin.html", context)


@login_required
def audit_log(request):
    if not request.user.is_admin():
        return HttpResponseForbidden("A auditoria e restrita a administradores.")

    entries = LogEntry.objects.select_related("actor", "content_type").order_by(
        "-timestamp"
    )

    actor = request.GET.get("actor", "").strip()
    model = request.GET.get("model", "").strip()
    action = request.GET.get("action", "").strip()

    if actor:
        entries = entries.filter(actor__username__icontains=actor)
    if model:
        entries = entries.filter(content_type__model__icontains=model)
    if action in {"0", "1", "2", "3"}:
        entries = entries.filter(action=int(action))

    paginator = Paginator(entries, 50)
    page = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "audit/list.html",
        {
            "page": page,
            "action_choices": LogEntry.Action.choices,
            "filters": {
                "actor": actor,
                "model": model,
                "action": action,
            },
        },
    )


def sobre(request):
    return render(request, "informacoes/sobre.html")
