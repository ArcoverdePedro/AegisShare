from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.clinical.pep.permissions import is_internal_professional

from .models import Employee


def _require_access(user):
    if not is_internal_professional(user) or not user.has_perm("hr.view_employee"):
        raise PermissionDenied


def _failed():
    return HttpResponse(
        "Não foi possível concluir a operação. Consulte o histórico e tente novamente.",
        status=503,
        content_type="text/plain; charset=utf-8",
    )


def _audit_read(user, employees):
    with transaction.atomic(), set_actor(user):
        for employee in employees:
            accessed.send(Employee, instance=employee)


@login_required
@require_GET
def employee_list(request):
    _require_access(request.user)
    try:
        page = Paginator(Employee.objects.select_related("user"), 25).get_page(
            request.GET.get("page")
        )
        page.object_list = list(page.object_list)
        _audit_read(request.user, page.object_list)
    except DatabaseError:
        return _failed()
    return render(request, "admin/hr/employee_list.html", {"page_obj": page})


@login_required
@require_GET
def employee_detail(request, pk):
    _require_access(request.user)
    try:
        employee = get_object_or_404(Employee.objects.select_related("user"), pk=pk)
        absences = list(employee.absences.all()[:20])
        _audit_read(request.user, [employee])
    except DatabaseError:
        return _failed()
    return render(
        request,
        "admin/hr/employee_detail.html",
        {"employee": employee, "absences": absences, "today": timezone.localdate()},
    )
