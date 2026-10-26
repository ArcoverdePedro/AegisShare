from auditlog.context import set_actor
from auditlog.signals import accessed
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.views.decorators.debug import sensitive_variables

from apps.admin.inventory.models import MaterialMovement
from apps.clinical.pep.models import Encounter
from apps.clinical.pep.permissions import accessible_patients, require_module_permission
from apps.clinical.prescription.models import MedicationDispenseItem

from .forms import AccountOpenForm, BillingItemForm
from .models import AccountClosure, BillingItem, HospitalAccount
from .totals import account_total


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
        if account.closed:
            raise BillingConflict("Conta fechada: reabra com justificativa antes de lançar.")
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


def _locked_account(user, account_id, capability, *, allow_closed=False):
    require_permission(user, capability)
    account = get_object_or_404(
        HospitalAccount.objects.select_for_update().select_related("encounter"), pk=account_id
    )
    get_object_or_404(accessible_patients(user), pk=account.encounter.patient_id)
    if account.closed and not allow_closed:
        raise BillingConflict("Conta fechada: reabra com justificativa antes de lançar.")
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


def _material_consumption(account):
    return MaterialMovement.objects.filter(
        encounter=account.encounter, kind=MaterialMovement.Kind.ISSUE
    ).select_related("balance__item")


def pending_material_movements(account):
    """Consumo de material do encontro, nao estornado no estoque e sem item vigente na conta."""
    billed = _billed_sources(account, BillingItem.Source.MATERIAL)
    pending = [
        movement
        for movement in _material_consumption(account).filter(reversed_by__isnull=True)
        if movement.pk not in billed
    ]
    for movement in pending:
        movement.consumed = -movement.quantity_delta
    return pending


def billing_divergences(account):
    """Itens vigentes cuja origem foi estornada no estoque: exigem estorno na conta."""
    reversed_ids = set(
        _material_consumption(account)
        .filter(reversed_by__isnull=False)
        .values_list("pk", flat=True)
    )
    return [
        item
        for item in account.items.filter(
            source=BillingItem.Source.MATERIAL, reverses__isnull=True, reversed_by__isnull=True
        )
        if item.source_id in reversed_ids
    ]


def capture_material(*, user, account_id, movement_id, unit_price, operation_key):
    with transaction.atomic(), set_actor(user):
        account = _locked_account(user, account_id, "add_item")
        existing = _replay(operation_key, user, account)
        if existing:
            return existing
        movement = get_object_or_404(_material_consumption(account), pk=movement_id)
        if hasattr(movement, "reversed_by"):
            raise BillingConflict("Consumo estornado no estoque não é lançado.")
        if movement.pk in _billed_sources(account, BillingItem.Source.MATERIAL):
            raise BillingConflict("Este consumo já está lançado na conta.")
        item = movement.balance.item
        return BillingItem.objects.create(
            account=account,
            description=f"{item.code} · {item.name} ({item.unit})"[:200],
            quantity=-movement.quantity_delta,
            unit_price=unit_price,
            recorded_by=user,
            operation_key=operation_key,
            source=BillingItem.Source.MATERIAL,
            source_id=movement.pk,
        )


def close_account(*, user, account_id):
    """Fecha somente conta consistente: sem producao pendente nem divergencia de estorno."""
    with transaction.atomic(), set_actor(user):
        account = _locked_account(user, account_id, "close_account")
        if account.encounter.status == Encounter.Status.OPEN:
            raise BillingConflict("Encerre o encontro antes de fechar a conta.")
        if pending_dispense_items(account) or pending_material_movements(account):
            raise BillingConflict("Há produção confirmada sem lançamento.")
        if billing_divergences(account):
            raise BillingConflict("Há consumo estornado com item vigente na conta.")
        return AccountClosure.objects.create(
            account=account,
            action=AccountClosure.Action.CLOSE,
            total=account_total(account),
            recorded_by=user,
        )


def reopen_account(*, user, account_id, reason):
    if not reason.strip():
        raise BillingConflict("Informe o motivo da reabertura.")
    with transaction.atomic(), set_actor(user):
        account = _locked_account(user, account_id, "close_account", allow_closed=True)
        if not account.closed:
            raise BillingConflict("A conta não está fechada.")
        return AccountClosure.objects.create(
            account=account,
            action=AccountClosure.Action.REOPEN,
            total=account_total(account),
            reason=reason.strip(),
            recorded_by=user,
        )
