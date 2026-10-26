from auditlog.context import set_actor
from auditlog.signals import accessed
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.debug import sensitive_variables

from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients, require_module_permission
from apps.clinical.prescription.models import MedicationDispenseItem

from .forms import AccountOpenForm, BillingItemForm
from .models import BillingItem, HospitalAccount


class BillingConflict(ValueError):
    pass


def require_permission(user, capability=None):
    require_module_permission(user, "billing", "view_accounts", capability)


def _validate(form):
    if not form.is_valid():
        raise BillingConflict("Revise os dados e a confirmação.")
    return form.cleaned_data


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
        except IntegrityError:
            # Outra requisicao gravou a mesma chave ao mesmo tempo: devolve o registro dela.
            existing = HospitalAccount.objects.filter(operation_key=data["operation_key"]).first()
            if existing is None:
                raise
            return _retry_account(existing, user, encounter.pk)


@sensitive_variables()
def add_item(
    *, user, account_id, description, quantity, unit_price, justification, operation_key, confirmed
):
    require_permission(user, "add_item")
    data = _validate(
        BillingItemForm(
            {
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "justification": justification,
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
        except IntegrityError:
            # Outra requisicao gravou a mesma chave ao mesmo tempo: devolve o registro dela.
            existing = BillingItem.objects.filter(operation_key=data["operation_key"]).first()
            if existing is None:
                raise
            return _retry_item(existing, user, account.pk, data)


def _locked_account(user, account_id, capability):
    require_permission(user, capability)
    account = get_object_or_404(
        HospitalAccount.objects.select_for_update().select_related("encounter"), pk=account_id
    )
    get_object_or_404(accessible_patients(user), pk=account.encounter.patient_id)
    return account


def _replay(operation_key, user, account):
    existing = BillingItem.objects.filter(operation_key=operation_key).first()
    if existing and (existing.recorded_by_id, existing.account_id) != (user.pk, account.pk):
        raise BillingConflict("Operação incompatível.")
    return existing


def _billed_sources(account, source):
    """Origens com item vigente (lancado e nao estornado)."""
    return set(
        account.items.filter(source=source, reverses__isnull=True, reversed_by__isnull=True)
        .exclude(source_id=None)
        .values_list("source_id", flat=True)
    )


def pending_dispense_items(account):
    """Producao confirmada (dispensacao) do encontro ainda sem item vigente na conta."""
    billed = _billed_sources(account, BillingItem.Source.DISPENSE)
    return [
        item
        for item in MedicationDispenseItem.objects.filter(
            dispense__medication_request__encounter=account.encounter
        ).select_related("request_item__drug", "dispense")
        if item.pk not in billed
    ]


def capture_dispense(*, user, account_id, dispense_item_id, unit_price, operation_key):
    with transaction.atomic(), set_actor(user):
        account = _locked_account(user, account_id, "add_item")
        existing = _replay(operation_key, user, account)
        if existing:
            return existing
        item = get_object_or_404(
            MedicationDispenseItem.objects.select_related("request_item__drug"),
            pk=dispense_item_id,
            dispense__medication_request__encounter=account.encounter,
        )
        if item.pk in _billed_sources(account, BillingItem.Source.DISPENSE):
            raise BillingConflict("Esta dispensação já está lançada na conta.")
        if item.quantity != item.quantity.to_integral_value():
            raise BillingConflict(
                "Quantidade fracionada exige regra de conversão aprovada; lance manualmente."
            )
        drug = item.request_item.drug
        return BillingItem.objects.create(
            account=account,
            description=f"{drug.code} · {drug.name} ({drug.dispense_unit})"[:200],
            quantity=int(item.quantity),
            unit_price=unit_price,
            recorded_by=user,
            operation_key=operation_key,
            source=BillingItem.Source.DISPENSE,
            source_id=item.pk,
        )


def reverse_item(*, user, item_id, justification, operation_key):
    with transaction.atomic(), set_actor(user):
        original = get_object_or_404(BillingItem, pk=item_id)
        account = _locked_account(user, original.account_id, "reverse_item")
        existing = _replay(operation_key, user, account)
        if existing:
            return existing
        original = BillingItem.objects.select_for_update().get(pk=original.pk)
        if original.reverses_id or hasattr(original, "reversed_by"):
            raise BillingConflict("Item já estornado ou é um estorno.")
        return BillingItem.objects.create(
            account=account,
            description=f"Estorno: {original.description}"[:200],
            quantity=original.quantity,
            unit_price=original.unit_price,
            recorded_by=user,
            operation_key=operation_key,
            source=original.source,
            source_id=original.source_id,
            justification=justification.strip(),
            reverses=original,
        )
