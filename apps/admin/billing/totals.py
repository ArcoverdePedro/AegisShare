from decimal import Decimal

from django.db import connection
from django.db.models import Aggregate, CharField, DecimalField, F, Sum


class _CentSum:
    """SQLite não tem soma Decimal nativa; acumula centavos sem float."""

    def __init__(self):
        self.cents = 0

    def step(self, quantity, price):
        self.cents += quantity * int(Decimal(str(price)) * 100)

    def finalize(self):
        return f"{self.cents // 100}.{self.cents % 100:02d}"


def account_total(account):
    items = account.items.all()
    if connection.vendor == "sqlite":
        connection.ensure_connection()
        connection.connection.create_aggregate("billing_cent_sum", 2, _CentSum)
        expression = Aggregate(
            F("quantity"), F("unit_price"), function="billing_cent_sum", output_field=CharField()
        )
    else:
        expression = Sum(
            F("quantity") * F("unit_price"),
            output_field=DecimalField(max_digits=30, decimal_places=2),
        )
    result = items.aggregate(total=expression)["total"]
    return Decimal(result) if result is not None else Decimal("0.00")
