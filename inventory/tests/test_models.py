from datetime import date
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from inventory.models import Item, Location, StockMovement
from purchases.tests.base import create_purchase_item

from .base import create_initial_entry, create_item, project_location, warehouse


class ItemModelTests(TestCase):
    def test_item_defaults_and_display(self):
        item = create_item()
        self.assertTrue(item.is_active)
        self.assertEqual(str(item), "Cimento (saco)")
        self.assertEqual(item.get_absolute_url(), f"/inventory/items/{item.pk}/")

    def test_item_category_choices(self):
        self.assertIn(Item.Category.MATERIAL, Item.Category.values)
        self.assertIn(Item.Category.EQUIPMENT, Item.Category.values)
        self.assertIn(Item.Category.REUSABLE_MATERIAL, Item.Category.values)


class LocationModelTests(TestCase):
    def test_warehouse_is_seeded(self):
        location = warehouse()
        self.assertTrue(location.is_warehouse)
        self.assertFalse(location.is_project)
        self.assertIsNone(location.project)

    def test_only_one_warehouse_is_allowed(self):
        warehouse()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Location.objects.create(
                    name="Outro armazém",
                    location_type=Location.Type.WAREHOUSE,
                )

    def test_project_location_requires_project(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Location.objects.create(
                    name="Localização inválida",
                    location_type=Location.Type.PROJECT,
                )

    def test_warehouse_cannot_have_project(self):
        from projects.tests.base import create_project

        project = create_project()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Location.objects.create(
                    name="Armazém inválido",
                    location_type=Location.Type.WAREHOUSE,
                    project=project,
                )

    def test_project_location_is_created_for_project(self):
        location = project_location()
        self.assertTrue(location.is_project)
        self.assertEqual(location.project.name, "Obra de teste")


class StockMovementModelTests(TestCase):
    def setUp(self):
        self.item = create_item()
        self.location = warehouse()

    def test_quantity_must_be_positive(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    item=self.item,
                    to_location=self.location,
                    quantity=Decimal("0"),
                    movement_type=StockMovement.Type.INITIAL_ENTRY,
                    movement_date=date(2026, 1, 20),
                )

    def test_initial_entry_cannot_have_source(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    item=self.item,
                    from_location=self.location,
                    to_location=self.location,
                    quantity=Decimal("1"),
                    movement_type=StockMovement.Type.INITIAL_ENTRY,
                    movement_date=date(2026, 1, 20),
                )

    def test_purchase_item_is_only_allowed_on_initial_entries(self):
        purchase_item = create_purchase_item(
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
        )
        other = project_location()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    item=self.item,
                    from_location=self.location,
                    to_location=other,
                    purchase_item=purchase_item,
                    quantity=Decimal("1"),
                    movement_type=StockMovement.Type.TRANSFER,
                    movement_date=date(2026, 1, 20),
                )

    def test_transfer_requires_two_different_locations(self):
        other = project_location()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StockMovement.objects.create(
                    item=self.item,
                    from_location=self.location,
                    to_location=self.location,
                    quantity=Decimal("1"),
                    movement_type=StockMovement.Type.TRANSFER,
                    movement_date=date(2026, 1, 20),
                )

        movement = StockMovement.objects.create(
            item=self.item,
            from_location=self.location,
            to_location=other,
            quantity=Decimal("1"),
            movement_type=StockMovement.Type.TRANSFER,
            movement_date=date(2026, 1, 20),
        )
        self.assertFalse(movement.is_cancelled)

    def test_str_includes_type_item_quantity_and_unit(self):
        movement = create_initial_entry(
            item=self.item,
            location=self.location,
            quantity=Decimal("10"),
        )

        self.assertEqual(
            str(movement),
            "Entrada inicial - Cimento - 10 saco",
        )
