from auditlog.context import set_actor
from auditlog.signals import accessed
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from django.views.decorators.http import require_GET, require_http_methods

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients

from .forms import AccountOpenForm, BillingItemForm
from .models import BillingItem, HospitalAccount
from .services import BillingConflict, add_item, open_account, require_permission
from .totals import account_total


def _accounts(user):
    return HospitalAccount.objects.filter(
        encounter__patient__in=accessible_patients(user)
    ).select_related("encounter__patient", "opened_by")


def _failed():
    return HttpResponse(
        "Não foi possível concluir a operação. Consulte os registros e tente novamente.", status=503
    )


@login_required
@require_GET
def account_list(request):
    require_permission(request.user)
    try:
        page = Paginator(_accounts(request.user), 25).get_page(request.GET.get("page"))
        page.object_list = list(page.object_list)
        with transaction.atomic(), set_actor(request.user):
            for account in page.object_list:
                accessed.send(HospitalAccount, instance=account)
    except DatabaseError:
        return _failed()
    return render(request, "admin/billing/account_list.html", {"page_obj": page})


@login_required
@require_GET
def account_detail(request, pk):
    require_permission(request.user)
    try:
        account = get_object_or_404(_accounts(request.user), pk=pk)
        page = Paginator(account.items.select_related("recorded_by"), 25).get_page(
            request.GET.get("page")
        )
        page.object_list = list(page.object_list)
        total = account_total(account)
        with transaction.atomic(), set_actor(request.user):
            accessed.send(HospitalAccount, instance=account)
            for item in page.object_list:
                accessed.send(BillingItem, instance=item)
    except DatabaseError:
        return _failed()
    return render(
        request,
        "admin/billing/account_detail.html",
        {"account": account, "page_obj": page, "total": total},
    )


@sensitive_post_parameters()
@sensitive_variables()
@login_required
@require_http_methods(["GET", "POST"])
def account_open(request, encounter_id):
    require_permission(request.user, "open_account")
    try:
        encounter = get_object_or_404(
            Encounter.objects.filter(patient__in=accessible_patients(request.user)).select_related(
                "patient"
            ),
            pk=encounter_id,
        )
        if request.method == "GET":
            existing = HospitalAccount.objects.filter(encounter=encounter).first()
            if existing:
                with transaction.atomic(), set_actor(request.user):
                    accessed.send(HospitalAccount, instance=existing)
                return redirect("billing:account_detail", pk=existing.pk)
        form = AccountOpenForm(request.POST if request.method == "POST" else None)
        status = 200
        if request.method == "POST" and form.is_valid():
            try:
                account = open_account(
                    user=request.user, encounter_id=encounter.pk, **form.cleaned_data
                )
            except BillingConflict:
                form.add_error(None, "Operação incompatível. Consulte as contas existentes.")
                status = 409
            else:
                return redirect("billing:account_detail", pk=account.pk)
        with transaction.atomic(), set_actor(request.user):
            accessed.send(Encounter, instance=encounter)
    except DatabaseError:
        return _failed()
    return render(
        request,
        "admin/billing/account_form.html",
        {"form": form, "encounter": encounter},
        status=status,
    )


@sensitive_post_parameters()
@sensitive_variables()
@login_required
@require_http_methods(["GET", "POST"])
def item_create(request, pk):
    require_permission(request.user, "add_item")
    try:
        account = get_object_or_404(_accounts(request.user), pk=pk)
        form = BillingItemForm(request.POST if request.method == "POST" else None)
        status = 200
        if request.method == "POST" and form.is_valid():
            try:
                add_item(user=request.user, account_id=account.pk, **form.cleaned_data)
            except BillingConflict:
                form.add_error(None, "Operação incompatível. Consulte os itens existentes.")
                status = 409
            else:
                return redirect("billing:account_detail", pk=account.pk)
        with transaction.atomic(), set_actor(request.user):
            accessed.send(HospitalAccount, instance=account)
    except DatabaseError:
        return _failed()
    return render(
        request, "admin/billing/item_form.html", {"form": form, "account": account}, status=status
    )
