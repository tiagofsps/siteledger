from decimal import Decimal

from django.test import TestCase

from inventory.tests.base import create_initial_entry, create_item, warehouse
from purchases.formsets import PurchaseItemFormSet

from .base import create_purchase, create_purchase_item


def management_data(*, total, initial):
    return {
        "items-TOTAL_FORMS": str(total),
        "items-INITIAL_FORMS": str(initial),
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "50",
    }


class PurchaseItemFormSetTests(TestCase):
    def test_purchase_requires_at_least_one_item(self):
        purchase = create_purchase()
        data = management_data(total=1, initial=0)
        data.update(
            {
                "items-0-item": "",
                "items-0-description": "",
                "items-0-unit": "",
                "items-0-quantity": "",
                "items-0-unit_price": "",
            }
        )
        formset = PurchaseItemFormSet(data, instance=purchase, prefix="items")
        self.assertFalse(formset.is_valid())
        self.assertIn("pelo menos uma linha", " ".join(formset.non_form_errors()))

    def test_item_with_movements_cannot_be_deleted(self):
        item = create_item()
        purchase = create_purchase()
        purchase_item = create_purchase_item(
            purchase=purchase,
            item=item,
            description=item.name,
            unit=item.unit,
            quantity=Decimal("5"),
        )
        create_initial_entry(
            item=item,
            location=warehouse(),
            quantity=Decimal("1"),
            purchase_item=purchase_item,
        )

        data = management_data(total=1, initial=1)
        data.update(
            {
                "items-0-id": str(purchase_item.pk),
                "items-0-purchase": str(purchase.pk),
                "items-0-item": str(item.pk),
                "items-0-description": item.name,
                "items-0-unit": item.unit,
                "items-0-quantity": "5.000",
                "items-0-unit_price": "10.00",
                "items-0-DELETE": "on",
            }
        )
        formset = PurchaseItemFormSet(data, instance=purchase, prefix="items")
        self.assertFalse(formset.is_valid())
        self.assertIn("DELETE", formset.forms[0].errors)

    def test_quantity_cannot_drop_below_active_receipt(self):
        item = create_item()
        purchase = create_purchase()
        purchase_item = create_purchase_item(
            purchase=purchase,
            item=item,
            description=item.name,
            unit=item.unit,
            quantity=Decimal("5"),
        )
        create_initial_entry(
            item=item,
            location=warehouse(),
            quantity=Decimal("3"),
            purchase_item=purchase_item,
        )

        data = management_data(total=1, initial=1)
        data.update(
            {
                "items-0-id": str(purchase_item.pk),
                "items-0-purchase": str(purchase.pk),
                "items-0-item": str(item.pk),
                "items-0-description": item.name,
                "items-0-unit": item.unit,
                "items-0-quantity": "2.000",
                "items-0-unit_price": "10.00",
            }
        )
        formset = PurchaseItemFormSet(data, instance=purchase, prefix="items")
        self.assertFalse(formset.is_valid())
        self.assertIn("quantity", formset.forms[0].errors)

    def test_line_without_movements_can_be_deleted(self):
        item = create_item()
        purchase = create_purchase()
        deleted = create_purchase_item(
            purchase=purchase,
            item=item,
            description=item.name,
            unit=item.unit,
            quantity=Decimal("5"),
            unit_price=Decimal("10.00"),
        )
        kept = create_purchase_item(
            purchase=purchase,
            item=item,
            description=item.name,
            unit=item.unit,
            quantity=Decimal("2"),
            unit_price=Decimal("10.00"),
        )

        data = management_data(total=2, initial=2)
        data.update(
            {
                "items-0-id": str(deleted.pk),
                "items-0-purchase": str(purchase.pk),
                "items-0-item": str(item.pk),
                "items-0-description": item.name,
                "items-0-unit": item.unit,
                "items-0-quantity": "5.000",
                "items-0-unit_price": "10.00",
                "items-0-DELETE": "on",
                "items-1-id": str(kept.pk),
                "items-1-purchase": str(purchase.pk),
                "items-1-item": str(item.pk),
                "items-1-description": item.name,
                "items-1-unit": item.unit,
                "items-1-quantity": "2.000",
                "items-1-unit_price": "10.00",
            }
        )
        formset = PurchaseItemFormSet(data, instance=purchase, prefix="items")
        self.assertTrue(formset.is_valid(), formset.errors)
