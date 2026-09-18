from auditlog.context import set_actor
from auditlog.signals import accessed
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.debug import sensitive_variables

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients, is_internal_professional

from .forms import AccountOpenForm, BillingItemForm
from .models import BillingItem, HospitalAccount


class BillingConflict(ValueError):
    pass


def require_permission(user, capability=None):
    permissions = ["billing.view_accounts"]
    if capability:
        permissions.append(f"billing.{capability}")
    if not is_internal_professional(user) or not user.has_perms(permissions):
        raise PermissionDenied


def _validate(form):
    if not form.is_valid():
        raise BillingConflict("Revise os dados e a confirmação.")
    return form.cleaned_data


def _operation_collision(exc, name, table):
    return (
        getattr(getattr(exc.__cause__, "diag", None), "constraint_name", None) == name
        or str(exc) == f"UNIQUE constraint failed: {table}.operation_key"
    )


def _retry_account(item, user, encounter_id):
    if (item.opened_by_id, item.encounter_id) != (user.pk, encounter_id):
        raise BillingConflict("Operação incompatível.")
    accessed.send(HospitalAccount, instance=item)
    return item


def _retry_item(item, user, account_id, data):
    if (item.recorded_by_id, item.account_id, item.description, item.quantity, item.unit_price) != (
        user.pk,
        account_id,
        data["description"],
        data["quantity"],
        data["unit_price"],
    ):
        raise BillingConflict("Operação incompatível.")
    accessed.send(BillingItem, instance=item)
    return item


@sensitive_variables()
def open_account(*, user, encounter_id, operation_key, confirmed):
    require_permission(user, "open_account")
    data = _validate(AccountOpenForm({"operation_key": operation_key, "confirmed": confirmed}))
    with transaction.atomic(), set_actor(user):
        encounter = get_object_or_404(Encounter.objects.select_for_update(), pk=encounter_id)
        require_permission(user, "open_account")
        get_object_or_404(accessible_patients(user), pk=encounter.patient_id)
        existing = HospitalAccount.objects.filter(operation_key=data["operation_key"]).first()
        if existing:
            return _retry_account(existing, user, encounter.pk)
        if HospitalAccount.objects.filter(encounter=encounter).exists():
            raise BillingConflict("Operação incompatível.")
        try:
            with transaction.atomic():
                return HospitalAccount.objects.create(
                    encounter=encounter, opened_by=user, operation_key=data["operation_key"]
                )
        except IntegrityError as exc:
            if not _operation_collision(
                exc, "uniq_billing_account_operation", "billing_hospitalaccount"
            ):
                raise
            existing = HospitalAccount.objects.filter(operation_key=data["operation_key"]).first()
            if existing is None:
                raise
            return _retry_account(existing, user, encounter.pk)


@sensitive_variables()
def add_item(*, user, account_id, description, quantity, unit_price, operation_key, confirmed):
    require_permission(user, "add_item")
    data = _validate(
        BillingItemForm(
            {
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "operation_key": operation_key,
                "confirmed": confirmed,
            }
        )
    )
    with transaction.atomic(), set_actor(user):
        account = get_object_or_404(
            HospitalAccount.objects.select_for_update().select_related("encounter"), pk=account_id
        )
        require_permission(user, "add_item")
        get_object_or_404(accessible_patients(user), pk=account.encounter.patient_id)
        existing = BillingItem.objects.filter(operation_key=data["operation_key"]).first()
        if existing:
            return _retry_item(existing, user, account.pk, data)
        data.pop("confirmed")
        try:
            with transaction.atomic():
                return BillingItem.objects.create(account=account, recorded_by=user, **data)
        except IntegrityError as exc:
            if not _operation_collision(exc, "uniq_billing_item_operation", "billing_billingitem"):
                raise
            existing = BillingItem.objects.filter(operation_key=data["operation_key"]).first()
            if existing is None:
                raise
            return _retry_item(existing, user, account.pk, data)
