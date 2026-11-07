from decimal import Decimal

from django.test import TestCase

from inventory.tests.base import create_initial_entry, create_item, warehouse
from purchases.services import (
    active_received_quantity,
    purchase_item_subtotal,
    recalculate_purchase_total,
)

from .base import create_purchase_item


class PurchaseServiceTests(TestCase):
    def setUp(self):
        self.item = create_item()
        self.purchase_item = create_purchase_item(item=self.item)

    def test_active_received_quantity_excludes_movement(self):
        first = create_initial_entry(
            item=self.item,
            location=warehouse(),
            quantity=Decimal("2"),
            purchase_item=self.purchase_item,
        )
        create_initial_entry(
            item=self.item,
            location=warehouse(),
            quantity=Decimal("3"),
            purchase_item=self.purchase_item,
        )

        self.assertEqual(
            active_received_quantity(self.purchase_item),
            Decimal("5.000"),
        )
        self.assertEqual(
            active_received_quantity(self.purchase_item, exclude_movement=first),
            Decimal("3.000"),
        )

    def test_purchase_item_subtotal_is_zero_without_price(self):
        line = create_purchase_item(item=self.item, unit_price=None)

        self.assertEqual(purchase_item_subtotal(line), Decimal("0.00"))

    def test_recalculate_skips_persist_when_total_unchanged(self):
        line = create_purchase_item(
            item=self.item,
            quantity=Decimal("2"),
            unit_price=Decimal("10.00"),
        )
        purchase = line.purchase
        purchase.total = Decimal("20.00")
        purchase.save(update_fields=["total"])

        result = recalculate_purchase_total(purchase)

        self.assertEqual(result, Decimal("20.00"))
        self.assertEqual(purchase.total, Decimal("20.00"))
