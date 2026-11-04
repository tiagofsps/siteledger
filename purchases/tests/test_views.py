from decimal import Decimal

from django.contrib import admin
from django.test import TestCase
from django.urls import reverse

from inventory.models import StockMovement
from inventory.tests.base import create_initial_entry, create_item, project_location, warehouse
from projects.tests.base import create_project, create_user

from purchases.models import Purchase, PurchaseItem, Supplier

from .base import create_purchase, create_purchase_item, create_supplier


PURCHASE_PERMISSIONS = (
    "purchases.view_supplier",
    "purchases.add_supplier",
    "purchases.change_supplier",
    "purchases.view_purchase",
    "purchases.add_purchase",
    "purchases.change_purchase",
    "inventory.view_item",
    "inventory.view_location",
    "inventory.view_stockmovement",
    "inventory.change_stockmovement",
    "projects.view_project",
)


def purchase_form_data(*, supplier, purchase_date="2026-01-10", total="100.00", item=None, quantity="2.000"):
    data = {
        "supplier": supplier.pk,
        "purchase_date": purchase_date,
        "total": total,
        "notes": "",
        "items-TOTAL_FORMS": "1",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "50",
        "items-0-item": item.pk if item else "",
        "items-0-description": "",
        "items-0-unit": "",
        "items-0-quantity": quantity,
        "items-0-unit_price": "",
    }
    return data


class SupplierViewTests(TestCase):
    def setUp(self):
        self.user = create_user("purchase-manager", permissions=PURCHASE_PERMISSIONS)
        self.client.force_login(self.user)

    def test_create_and_update_supplier(self):
        response = self.client.post(
            reverse("purchases:supplier_create"),
            {"name": "Fornecedor Novo", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        supplier = Supplier.objects.get(name="Fornecedor Novo")

        response = self.client.post(
            reverse("purchases:supplier_update", args=[supplier.pk]),
            {"name": "Fornecedor Editado", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 302)
        supplier.refresh_from_db()
        self.assertEqual(supplier.name, "Fornecedor Editado")

    def test_duplicate_supplier_is_rejected(self):
        create_supplier(name="Fornecedor")
        response = self.client.post(
            reverse("purchases:supplier_create"),
            {"name": "fornecedor", "is_active": "on"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Já existe um fornecedor")


class PurchaseViewTests(TestCase):
    def setUp(self):
        self.user = create_user("purchase-manager", permissions=PURCHASE_PERMISSIONS)
        self.client.force_login(self.user)
        self.supplier = create_supplier()
        self.item = create_item()

    def test_create_purchase_with_catalogue_item(self):
        response = self.client.post(
            reverse("purchases:purchase_create"),
            purchase_form_data(supplier=self.supplier, item=self.item),
        )
        self.assertEqual(response.status_code, 302)
        purchase = Purchase.objects.get()
        purchase_item = purchase.items.get()
        self.assertEqual(purchase_item.description, self.item.name)
        self.assertEqual(purchase_item.unit, self.item.unit)

    def test_purchase_requires_at_least_one_item(self):
        data = purchase_form_data(supplier=self.supplier, item=None)
        data["items-0-quantity"] = ""
        response = self.client.post(reverse("purchases:purchase_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pelo menos um artigo")

    def test_create_can_be_retried_after_item_validation_error(self):
        data = purchase_form_data(supplier=self.supplier, item=self.item)
        data["items-0-unit"] = "unidade-errada"
        response = self.client.post(reverse("purchases:purchase_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["formset"].instance.pk)

        response = self.client.post(
            reverse("purchases:purchase_create"),
            purchase_form_data(supplier=self.supplier, item=self.item),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Purchase.objects.count(), 1)

    def test_update_cannot_reduce_below_allocated_quantity(self):
        purchase = create_purchase(supplier=self.supplier)
        purchase_item = create_purchase_item(
            purchase=purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("5"),
        )
        create_initial_entry(
            item=self.item,
            location=warehouse(),
            quantity=Decimal("3"),
            purchase_item=purchase_item,
        )

        data = {
            "supplier": self.supplier.pk,
            "purchase_date": "2026-01-10",
            "total": "100.00",
            "notes": "",
            "items-TOTAL_FORMS": "1",
            "items-INITIAL_FORMS": "1",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "50",
            "items-0-id": str(purchase_item.pk),
            "items-0-purchase": str(purchase.pk),
            "items-0-item": str(self.item.pk),
            "items-0-description": self.item.name,
            "items-0-unit": self.item.unit,
            "items-0-quantity": "2.000",
            "items-0-unit_price": "",
        }
        response = self.client.post(
            reverse("purchases:purchase_update", args=[purchase.pk]),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "não pode ser inferior")

    def test_update_form_renders_parent_fk_hidden_field(self):
        purchase = create_purchase(supplier=self.supplier)
        create_purchase_item(
            purchase=purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("5"),
        )

        response = self.client.get(
            reverse("purchases:purchase_update", args=[purchase.pk])
        )
        self.assertContains(response, 'name="items-0-purchase"')

    def test_allocation_creates_movement_and_updates_balance(self):
        purchase = create_purchase(supplier=self.supplier)
        purchase_item = create_purchase_item(
            purchase=purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("5"),
        )

        response = self.client.post(
            reverse(
                "purchases:item_allocations",
                args=[purchase.pk, purchase_item.pk],
            ),
            {"location": warehouse().pk, "quantity": "2.000"},
        )
        self.assertEqual(response.status_code, 302)
        movement = StockMovement.objects.get(purchase_item=purchase_item)
        self.assertEqual(movement.quantity, Decimal("2.000"))
        self.assertEqual(
            purchase_item.get_active_allocated_quantity(),
            Decimal("2.000"),
        )

    def test_allocation_cannot_exceed_purchase_quantity(self):
        purchase = create_purchase(supplier=self.supplier)
        purchase_item = create_purchase_item(
            purchase=purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("2"),
        )

        response = self.client.post(
            reverse(
                "purchases:item_allocations",
                args=[purchase.pk, purchase_item.pk],
            ),
            {"location": warehouse().pk, "quantity": "3.000"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "excede o que falta alocar")

    def test_purchase_list_filters_by_project(self):
        project = create_project(name="Obra Filtrada")
        location = project_location(project)
        purchase = create_purchase(supplier=self.supplier)
        purchase_item = create_purchase_item(
            purchase=purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("5"),
        )
        create_initial_entry(
            item=self.item,
            location=location,
            quantity=Decimal("1"),
            purchase_item=purchase_item,
        )

        response = self.client.get(
            reverse("purchases:purchase_list"),
            {"project": project.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, purchase.get_absolute_url())

    def test_purchase_list_project_filter_keeps_all_item_counts(self):
        project = create_project(name="Obra Filtrada")
        location = project_location(project)
        purchase = create_purchase(supplier=self.supplier)
        allocated_item = create_purchase_item(
            purchase=purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("5"),
        )
        create_purchase_item(
            purchase=purchase,
            description="Artigo por alocar",
            unit="un",
            quantity=Decimal("2"),
        )
        create_initial_entry(
            item=self.item,
            location=location,
            quantity=Decimal("1"),
            purchase_item=allocated_item,
        )

        response = self.client.get(
            reverse("purchases:purchase_list"),
            {"project": project.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["purchases"][0].item_count, 2)

    def test_permissions_are_required(self):
        self.client.force_login(create_user("viewer"))
        response = self.client.get(reverse("purchases:purchase_list"))
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            reverse("purchases:purchase_create"),
            purchase_form_data(supplier=self.supplier, item=self.item),
        )
        self.assertEqual(response.status_code, 403)

    def test_csrf_is_required_for_state_changes(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            reverse("purchases:purchase_create"),
            purchase_form_data(supplier=self.supplier, item=self.item),
        )
        self.assertEqual(response.status_code, 403)


class PurchaseItemRowTests(TestCase):
    def setUp(self):
        self.user = create_user("purchase-manager", permissions=PURCHASE_PERMISSIONS)
        self.client.force_login(self.user)

    def test_row_endpoint_returns_one_row_and_total_update(self):
        response = self.client.get(
            reverse("purchases:purchase_item_row"),
            {"items-TOTAL_FORMS": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="items-1-item"')
        self.assertContains(response, 'name="items-1-purchase"')
        self.assertContains(response, 'name="items-TOTAL_FORMS" value="2"')
        self.assertContains(response, "hx-swap-oob")

    def test_row_endpoint_limits_to_50_rows(self):
        response = self.client.get(
            reverse("purchases:purchase_item_row"),
            {"items-TOTAL_FORMS": "50"},
        )
        self.assertEqual(response.status_code, 400)

    def test_row_endpoint_requires_purchase_permission(self):
        self.client.force_login(create_user("viewer"))
        response = self.client.get(reverse("purchases:purchase_item_row"))
        self.assertEqual(response.status_code, 403)


class PurchaseAdminTests(TestCase):
    def test_purchase_models_are_not_registered(self):
        for model in (Supplier, Purchase, PurchaseItem):
            with self.subTest(model=model.__name__):
                self.assertNotIn(model, admin.site._registry)
