from datetime import date
from decimal import Decimal
from uuid import uuid4

from purchases.models import Purchase, PurchaseItem, Supplier


def create_supplier(*, name="Fornecedor de teste", is_active=True):
    return Supplier.objects.create(name=name, is_active=is_active)


def create_purchase(
    *,
    supplier=None,
    purchase_date=None,
    total=Decimal("100.00"),
    notes="",
):
    return Purchase.objects.create(
        supplier=supplier or create_supplier(name=f"Fornecedor {uuid4().hex[:8]}"),
        purchase_date=purchase_date or date(2026, 1, 10),
        total=total,
        notes=notes,
    )


def create_purchase_item(
    *,
    purchase=None,
    item=None,
    description="Artigo de teste",
    unit="un",
    quantity=Decimal("5.000"),
    unit_price=None,
):
    return PurchaseItem.objects.create(
        purchase=purchase or create_purchase(),
        item=item,
        description=description,
        unit=unit,
        quantity=quantity,
        unit_price=unit_price,
    )
