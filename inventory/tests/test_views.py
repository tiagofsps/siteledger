from datetime import date
from decimal import Decimal

from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from inventory.models import Item, Location, StockMovement
from projects.tests.base import create_user

from .base import create_initial_entry, create_item, project_location, warehouse


INVENTORY_PERMISSIONS = (
    "inventory.view_item",
    "inventory.add_item",
    "inventory.change_item",
    "inventory.view_location",
    "inventory.view_stockmovement",
    "inventory.add_stockmovement",
    "inventory.change_stockmovement",
)


class InventoryViewTests(TestCase):
    def setUp(self):
        self.user = create_user("inventory-manager", permissions=INVENTORY_PERMISSIONS)
        self.client.force_login(self.user)
        self.item = create_item()
        self.warehouse = warehouse()

    def test_item_crud(self):
        response = self.client.get(reverse("inventory:item_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.name)

        response = self.client.post(
            reverse("inventory:item_create"),
            {
                "name": "Areia",
                "category": Item.Category.MATERIAL,
                "unit": "m³",
                "description": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Item.objects.get(name="Areia")
        self.assertEqual(created.unit, "m³")

        response = self.client.post(
            reverse("inventory:item_update", args=[created.pk]),
            {
                "name": "Areia fina",
                "category": Item.Category.MATERIAL,
                "unit": "m³",
                "description": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 302)
        created.refresh_from_db()
        self.assertEqual(created.name, "Areia fina")

    def test_item_search_and_htmx_partial(self):
        response = self.client.get(reverse("inventory:item_list"), {"q": "Cimento"})
        self.assertContains(response, self.item.name)

        response = self.client.get(
            reverse("inventory:item_list"),
            {"q": "Cimento"},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "inventory/partials/item_results.html")

    def test_item_detail_hides_movements_without_movement_permission(self):
        create_initial_entry(
            item=self.item,
            location=self.warehouse,
            quantity=Decimal("2"),
        )
        self.client.force_login(
            create_user("item-viewer", permissions=("inventory.view_item",))
        )

        response = self.client.get(self.item.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.name)
        self.assertNotContains(response, "Saldos registados")
        self.assertNotContains(response, "Movimentos recentes")

        self.client.force_login(self.user)
        response = self.client.get(self.item.get_absolute_url())
        self.assertContains(response, "Saldos registados")
        self.assertContains(response, "Movimentos recentes")

    def test_location_list_requires_permission(self):
        response = self.client.get(reverse("inventory:location_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Armazém")

        self.client.force_login(create_user("no-permissions"))
        response = self.client.get(reverse("inventory:location_list"))
        self.assertEqual(response.status_code, 403)

    def test_initial_entry_creation_and_cancellation(self):
        response = self.client.post(
            reverse("inventory:initial_entry_create"),
            {
                "item": self.item.pk,
                "to_location": self.warehouse.pk,
                "quantity": "10.000",
                "movement_date": "2026-01-20",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        movement = StockMovement.objects.get(item=self.item)
        self.assertEqual(movement.quantity, Decimal("10.000"))

        response = self.client.post(
            reverse("inventory:movement_cancel", args=[movement.pk]),
            {"reason": "Registo errado"},
        )
        self.assertEqual(response.status_code, 302)
        movement.refresh_from_db()
        self.assertTrue(movement.is_cancelled)

    def test_movement_creation_rejects_insufficient_transfer(self):
        create_initial_entry(
            item=self.item,
            location=self.warehouse,
            quantity=Decimal("2"),
        )
        response = self.client.post(
            reverse("inventory:transfer_create"),
            {
                "item": self.item.pk,
                "from_location": self.warehouse.pk,
                "to_location": project_location().pk,
                "quantity": "3.000",
                "movement_date": "2026-01-20",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "excede o saldo registado")

    def test_movement_list_filters_and_htmx(self):
        create_initial_entry(
            item=self.item,
            location=self.warehouse,
            quantity=Decimal("4"),
        )
        response = self.client.get(
            reverse("inventory:movement_list"),
            {"item": self.item.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.name)

        response = self.client.get(
            reverse("inventory:movement_list"),
            {"item": self.item.pk},
            HTTP_HX_REQUEST="true",
        )
        self.assertTemplateUsed(response, "inventory/partials/movement_results.html")

    def test_permissions_are_required(self):
        self.client.force_login(create_user("viewer"))
        response = self.client.get(reverse("inventory:item_list"))
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            reverse("inventory:initial_entry_create"),
            {
                "item": self.item.pk,
                "to_location": self.warehouse.pk,
                "quantity": "1.000",
                "movement_date": "2026-01-20",
                "notes": "",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_csrf_is_required_for_state_changes(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            reverse("inventory:item_create"),
            {
                "name": "CSRF",
                "category": Item.Category.MATERIAL,
                "unit": "un",
                "description": "",
                "is_active": "on",
            },
        )
        self.assertEqual(response.status_code, 403)


class InventoryAdminTests(TestCase):
    def test_inventory_models_are_not_registered(self):
        for model in (Item, Location, StockMovement):
            with self.subTest(model=model.__name__):
                self.assertNotIn(model, admin.site._registry)
