#!/usr/bin/env python3
import os
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.contrib.auth.models import Permission  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.clinical.prescription.models import Drug, Lot, StockItem  # noqa: E402
from apps.clinical.prescription.stock_services import (  # noqa: E402
    create_lot,
    create_stock_item,
)

USERNAME = "ci-rx-accessibility"
PASSWORD = "ci-rx-accessibility-password"
DENIED_USERNAME = "ci-rx-denied-client"
DENIED_PASSWORD = "ci-rx-denied-client-password"
LOT_NUMBER = "E2E-RX-LOT-A11Y-001"


def configure_admin():
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=USERNAME)
    user.email = "ci-rx-accessibility@example.invalid"
    user.nivel_permissao = "ADM"
    user.is_active = True
    user.is_staff = True
    user.is_superuser = True
    user.set_password(PASSWORD)
    user.save()
    return user


def configure_denied_client():
    User = get_user_model()
    user, _ = User.objects.get_or_create(username=DENIED_USERNAME)
    user.email = "ci-rx-denied-client@example.invalid"
    user.nivel_permissao = "CLI"
    user.is_active = True
    user.is_staff = False
    user.is_superuser = False
    user.set_password(DENIED_PASSWORD)
    user.save()

    permissions = Permission.objects.filter(
        content_type__app_label="prescription",
        codename__in={
            "view_drug",
            "manage_drug_catalog",
            "view_pharmacy_stock",
            "manage_pharmacy_stock",
        },
    )
    user.user_permissions.set(permissions)
    return user


def ensure_drug(*, code, name, presentation):
    drug, _ = Drug.objects.update_or_create(
        code=code,
        defaults={
            "name": name,
            "presentation": presentation,
            "strength_text": "Referência sintética",
            "route_hint": "",
            "dispense_unit": "unidade",
            "active": True,
        },
    )
    return drug


def ensure_stock(*, actor, drug):
    stock = StockItem.objects.filter(
        drug=drug,
        storage_location="Farmácia E2E",
    ).first()
    if stock is None:
        stock = create_stock_item(
            actor=actor,
            drug_id=drug.pk,
            storage_location="Farmácia E2E",
            minimum_level=Decimal("5"),
        )

    lot = Lot.objects.filter(stock_item=stock, lot_number=LOT_NUMBER).first()
    if lot is None:
        lot = create_lot(
            actor=actor,
            stock_item_id=stock.pk,
            lot_number=LOT_NUMBER,
            expires_on=timezone.localdate() + timedelta(days=180),
            initial_quantity=Decimal("12"),
        )
    return stock, lot


def main():
    admin = configure_admin()
    denied_client = configure_denied_client()
    primary = ensure_drug(
        code="E2E-RX-A11Y-001",
        name="Medicamento Sintético Acessibilidade",
        presentation="Apresentação E2E",
    )
    ensure_drug(
        code="E2E-RX-A11Y-002",
        name="Medicamento Sintético Secundário",
        presentation="Apresentação E2E alternativa",
    )
    stock, lot = ensure_stock(actor=admin, drug=primary)

    print(
        "Dados E2E RX acessibilidade prontos:",
        admin.username,
        denied_client.username,
        primary.code,
        stock.storage_location,
        lot.lot_number,
    )


if __name__ == "__main__":
    main()
