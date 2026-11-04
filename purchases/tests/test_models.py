from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from purchases.models import Purchase, PurchaseItem, Supplier

from .base import create_purchase, create_purchase_item, create_supplier


class SupplierModelTests(TestCase):
    def test_name_is_unique_case_insensitively(self):
        create_supplier(name="Fornecedor")
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_supplier(name="fornecedor")

    def test_default_is_active(self):
        supplier = create_supplier()
        self.assertTrue(supplier.is_active)


class PurchaseModelTests(TestCase):
    def test_total_cannot_be_negative(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_purchase(total=Decimal("-0.01"))

    def test_absolute_url(self):
        purchase = create_purchase()
        self.assertEqual(
            purchase.get_absolute_url(),
            f"/purchases/{purchase.pk}/",
        )


class PurchaseItemModelTests(TestCase):
    def test_quantity_must_be_positive(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_purchase_item(quantity=Decimal("0"))

    def test_unit_price_cannot_be_negative(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                create_purchase_item(unit_price=Decimal("-1.00"))

    def test_subtotal_is_none_without_unit_price(self):
        item = create_purchase_item(unit_price=None)
        self.assertIsNone(item.subtotal)

    def test_subtotal_uses_round_half_up(self):
        item = create_purchase_item(
            quantity=Decimal("2.505"),
            unit_price=Decimal("1.00"),
        )
        self.assertEqual(item.subtotal, Decimal("2.51"))

    def test_active_allocated_and_remaining_quantity(self):
        from inventory.tests.base import create_item, warehouse
        from inventory.services import allocate_purchase_item

        item = create_item()
        purchase_item = create_purchase_item(
            item=item,
            description=item.name,
            unit=item.unit,
            quantity=Decimal("5"),
        )
        allocate_purchase_item(
            purchase_item=purchase_item,
            location=warehouse(),
            quantity=Decimal("2"),
            movement_date=date(2026, 1, 10),
            user=None,
        )
        self.assertEqual(
            purchase_item.get_active_allocated_quantity(),
            Decimal("2"),
        )
        self.assertEqual(purchase_item.remaining_quantity, Decimal("3"))
