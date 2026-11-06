from decimal import Decimal

from django.test import TestCase

from inventory.tests.base import create_initial_entry, create_item, project_location, warehouse
from projects.tests.base import create_project

from purchases.forms import ReceiptForm, PurchaseItemForm, SupplierForm

from .base import create_purchase_item, create_supplier


class SupplierFormTests(TestCase):
    def test_duplicate_name_is_rejected_case_insensitively(self):
        create_supplier(name="Fornecedor")
        form = SupplierForm(data={"name": "fornecedor", "is_active": "on"})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)


class PurchaseItemFormTests(TestCase):
    def setUp(self):
        self.item = create_item(unit="un")

    def test_item_is_required(self):
        form = PurchaseItemForm(
            data={"item": "", "quantity": "2.000", "unit_price": "10.00"}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("item", form.errors)

    def test_saved_line_snapshots_item_name_and_unit(self):
        form = PurchaseItemForm(
            data={
                "item": self.item.pk,
                "quantity": "2.000",
                "unit_price": "10.00",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        line = form.save(commit=False)
        self.assertEqual(line.description, self.item.name)
        self.assertEqual(line.unit, self.item.unit)

    def test_discrete_unit_rejects_fractional_quantity(self):
        form = PurchaseItemForm(
            data={
                "item": self.item.pk,
                "quantity": "1.500",
                "unit_price": "10.00",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_continuous_unit_accepts_fractional_quantity(self):
        item = create_item(name="Areia", unit="m3")
        form = PurchaseItemForm(
            data={
                "item": item.pk,
                "quantity": "1.500",
                "unit_price": "10.00",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_item_cannot_change_after_receipts(self):
        other_item = create_item(name="Outro artigo", unit="un")
        line = create_purchase_item(item=self.item, unit_price=Decimal("10.00"))
        create_initial_entry(
            item=self.item,
            location=warehouse(),
            quantity=Decimal("1"),
            purchase_item=line,
        )

        form = PurchaseItemForm(
            instance=line,
            data={
                "item": other_item.pk,
                "quantity": "5.000",
                "unit_price": "10.00",
            },
        )
        self.assertFalse(form.is_valid())
        self.assertIn("item", form.errors)


class ReceiptFormTests(TestCase):
    def setUp(self):
        self.item = create_item()
        self.purchase_item = create_purchase_item(
            item=self.item,
            quantity=Decimal("5"),
        )

    def test_quantity_cannot_exceed_remaining(self):
        form = ReceiptForm(
            data={"location": warehouse().pk, "quantity": "6.000"},
            item=self.purchase_item,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_archived_project_location_is_rejected(self):
        project = create_project()
        location = project_location(project)
        project.archive()

        form = ReceiptForm(
            data={"location": location.pk, "quantity": "1.000"},
            item=self.purchase_item,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("location", form.errors)


class UnitPriceRequirementTests(TestCase):
    def test_unit_price_is_required(self):
        item = create_item()
        form = PurchaseItemForm(
            data={"item": item.pk, "quantity": "2.000", "unit_price": ""}
        )
        self.assertFalse(form.is_valid())
        self.assertIn("unit_price", form.errors)


class PurchaseItemSnapshotTests(TestCase):
    def test_editing_a_line_keeps_the_original_snapshot(self):
        item = create_item(name="Cimento", unit="sc")
        line = create_purchase_item(item=item, unit_price=Decimal("10.00"))
        original_description = line.description

        item.name = "Cimento Portland"
        item.save(update_fields=["name"])

        form = PurchaseItemForm(
            instance=line,
            data={
                "item": item.pk,
                "quantity": "5.000",
                "unit_price": "12.00",
            },
        )
        self.assertTrue(form.is_valid(), form.errors)
        line = form.save()

        self.assertEqual(line.description, original_description)
        self.assertEqual(line.unit_price, Decimal("12.00"))


class UnitSelectTests(TestCase):
    def test_item_options_expose_their_unit(self):
        item = create_item(unit="sc")
        form = PurchaseItemForm()

        markup = str(form["item"])

        self.assertIn('class="item-select"', markup)
        self.assertIn(f'value="{item.pk}"', markup)
        self.assertIn('data-unit="sc"', markup)
