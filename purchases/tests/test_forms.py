from datetime import date
from decimal import Decimal

from django.test import TestCase

from inventory.tests.base import create_item, project_location, warehouse
from projects.tests.base import create_project

from purchases.forms import AllocationForm, PurchaseItemForm, SupplierForm
from purchases.models import PurchaseItem

from .base import create_purchase, create_purchase_item, create_supplier


class SupplierFormTests(TestCase):
    def test_duplicate_name_is_rejected_case_insensitively(self):
        create_supplier(name="Fornecedor")
        form = SupplierForm(data={"name": "fornecedor", "is_active": "on"})
        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)


class PurchaseItemFormTests(TestCase):
    def setUp(self):
        self.item = create_item()

    def test_catalogue_item_fills_description_and_unit(self):
        form = PurchaseItemForm(
            data={
                "item": self.item.pk,
                "description": "",
                "unit": "",
                "quantity": "2.000",
                "unit_price": "",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["description"], self.item.name)
        self.assertEqual(form.cleaned_data["unit"], self.item.unit)

    def test_free_text_item_requires_description_and_unit(self):
        form = PurchaseItemForm(
            data={
                "item": "",
                "description": "",
                "unit": "",
                "quantity": "2.000",
                "unit_price": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("description", form.errors)
        self.assertIn("unit", form.errors)

    def test_unit_must_match_catalogue_item(self):
        form = PurchaseItemForm(
            data={
                "item": self.item.pk,
                "description": self.item.name,
                "unit": "kg",
                "quantity": "2.000",
                "unit_price": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("unit", form.errors)


class AllocationFormTests(TestCase):
    def setUp(self):
        self.item = create_item()
        self.purchase_item = create_purchase_item(
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("5"),
        )

    def test_quantity_cannot_exceed_remaining(self):
        form = AllocationForm(
            data={"location": warehouse().pk, "quantity": "6.000"},
            item=self.purchase_item,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("quantity", form.errors)

    def test_archived_project_location_is_rejected(self):
        project = create_project()
        location = project_location(project)
        project.archive()

        form = AllocationForm(
            data={"location": location.pk, "quantity": "1.000"},
            item=self.purchase_item,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("location", form.errors)

    def test_purchase_item_without_catalogue_item_is_rejected(self):
        purchase_item = PurchaseItem.objects.create(
            purchase=create_purchase(),
            description="Sem catálogo",
            unit="un",
            quantity=Decimal("1"),
        )
        form = AllocationForm(
            data={"location": warehouse().pk, "quantity": "1.000"},
            item=purchase_item,
        )
        self.assertFalse(form.is_valid())
        self.assertIn("__all__", form.errors)
