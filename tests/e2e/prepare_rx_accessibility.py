#!/usr/bin/env python3
import os
from datetime import timedelta
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "mysite.settings")

import django  # noqa: E402

django.setup()

from django.contrib.auth import get_user_model  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.clinical.prescription.models import Drug, Lot, StockItem  # noqa: E402
from apps.clinical.prescription.stock_services import (  # noqa: E402
    create_lot,
    create_stock_item,
)

USERNAME = "ci-rx-accessibility"
PASSWORD = "ci-rx-accessibility-password"


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

    lot = Lot.objects.filter(stock_item=stock, lot_number="E2E-RX-A11Y-001").first()
    if lot is None:
        lot = create_lot(
            actor=actor,
            stock_item_id=stock.pk,
            lot_number="E2E-RX-A11Y-001",
            expires_on=timezone.localdate() + timedelta(days=180),
            initial_quantity=Decimal("12"),
        )
    return stock, lot


def main():
    admin = configure_admin()
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
        primary.code,
        stock.storage_location,
        lot.lot_number,
    )


if __name__ == "__main__":
    main()
