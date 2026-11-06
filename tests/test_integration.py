from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from inventory.services import (
    allocate_purchase_item,
    cancel_stock_movement,
    create_transfer,
    location_balance,
)
from inventory.tests.base import create_initial_entry, create_item, project_location, warehouse
from projects.tests.base import create_project, create_user
from purchases.models import Purchase
from purchases.tests.base import create_purchase, create_purchase_item, create_supplier


class PurchaseAllocationIntegrationTests(TestCase):
    def setUp(self):
        self.user = create_user(
            "integration-manager",
            permissions=(
                "projects.view_project",
                "purchases.view_purchase",
                "purchases.add_purchase",
                "purchases.change_purchase",
                "inventory.view_item",
                "inventory.view_location",
                "inventory.view_stockmovement",
                "inventory.add_stockmovement",
                "inventory.change_stockmovement",
            ),
        )
        self.client.force_login(self.user)
        self.project = create_project(name="Obra Integração")
        self.location = project_location(self.project)
        self.item = create_item()
        self.purchase = create_purchase(supplier=create_supplier())
        self.purchase_item = create_purchase_item(
            purchase=self.purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("5"),
        )

    def test_allocation_updates_project_balances_and_history(self):
        allocate_purchase_item(
            purchase_item=self.purchase_item,
            location=self.location,
            quantity=Decimal("2"),
            movement_date=date(2026, 1, 10),
            user=self.user,
        )

        response = self.client.get(self.project.get_absolute_url())
        self.assertContains(response, self.item.name)
        self.assertContains(response, "2,000")

        response = self.client.get(
            reverse("purchases:purchase_detail", args=[self.purchase.pk])
        )
        self.assertContains(response, self.item.name)

    def test_cancellation_frees_allocation_and_removes_balance(self):
        movement = allocate_purchase_item(
            purchase_item=self.purchase_item,
            location=self.location,
            quantity=Decimal("2"),
            movement_date=date(2026, 1, 10),
            user=self.user,
        )
        cancel_stock_movement(
            movement=movement,
            user=self.user,
            reason="Receção errada",
        )

        self.assertEqual(
            self.purchase_item.get_active_allocated_quantity(),
            Decimal("0"),
        )
        self.assertEqual(
            location_balance(self.item, self.location),
            Decimal("0"),
        )

        response = self.client.get(self.project.get_absolute_url())
        self.assertContains(response, "Cancelado")

    def test_purchase_registration_flows_into_allocation(self):
        response = self.client.post(
            reverse("purchases:purchase_create"),
            {
                "supplier": self.purchase.supplier.pk,
                "purchase_date": "2026-01-10",
                "notes": "",
                "items-TOTAL_FORMS": "1",
                "items-INITIAL_FORMS": "0",
                "items-MIN_NUM_FORMS": "0",
                "items-MAX_NUM_FORMS": "50",
                "items-0-item": self.item.pk,
                "items-0-description": "",
                "items-0-unit": "",
                "items-0-quantity": "2.000",
                "items-0-unit_price": "10.00",
            },
        )
        self.assertEqual(response.status_code, 302)
        purchase = Purchase.objects.latest("pk")
        self.assertEqual(
            response["Location"],
            reverse("purchases:purchase_allocations", args=[purchase.pk]),
        )

        purchase_item = purchase.items.get()
        response = self.client.post(
            reverse("purchases:purchase_allocations", args=[purchase.pk]),
            {
                "item_pk": purchase_item.pk,
                f"allocation-{purchase_item.pk}-location": self.location.pk,
                f"allocation-{purchase_item.pk}-quantity": "2.000",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            location_balance(self.item, self.location),
            Decimal("2"),
        )

        response = self.client.get(self.project.get_absolute_url())
        self.assertContains(response, self.item.name)
        self.assertContains(response, "2,000")

    def test_project_without_location_does_not_show_unrelated_movements(self):
        project = create_project(name="Obra sem localização")
        unrelated_item = create_item(name="Item não relacionado")
        create_initial_entry(
            item=unrelated_item,
            location=warehouse(),
            quantity=Decimal("1"),
        )

        response = self.client.get(project.get_absolute_url())
        self.assertNotContains(response, "Item não relacionado")

    def test_archived_project_rejects_allocation_but_allows_return(self):
        create_initial_entry(
            item=self.item,
            location=self.location,
            quantity=Decimal("3"),
        )
        self.project.archive()

        response = self.client.post(
            reverse(
                "purchases:item_allocations",
                args=[self.purchase.pk, self.purchase_item.pk],
            ),
            {"location": self.location.pk, "quantity": "1.000"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "obra arquivada")

        create_transfer(
            item=self.item,
            from_location=self.location,
            to_location=warehouse(),
            quantity=Decimal("1"),
            movement_date=date(2026, 1, 11),
            user=self.user,
        )
        self.assertEqual(
            location_balance(self.item, self.location),
            Decimal("2"),
        )
