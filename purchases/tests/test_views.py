from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse

from inventory.models import StockMovement
from inventory.tests.base import create_initial_entry, create_item, project_location, warehouse
from projects.tests.base import create_project, create_user

from purchases.forms import PurchaseForm, SupplierForm
from purchases.formsets import PurchaseItemFormSet
from purchases.models import Purchase, PurchaseItem, Supplier
from purchases.views import _purchase_wizard_step

from .base import create_purchase, create_purchase_item, create_supplier


PURCHASE_PERMISSIONS = (
    "purchases.view_supplier",
    "purchases.add_supplier",
    "purchases.change_supplier",
    "purchases.view_purchase",
    "purchases.add_purchase",
    "purchases.change_purchase",
    "inventory.view_item",
    "inventory.add_item",
    "inventory.view_location",
    "inventory.view_stockmovement",
    "inventory.change_stockmovement",
    "projects.view_project",
)


def purchase_form_data(*, supplier, purchase_date="2026-01-10", item=None, quantity="2.000"):
    data = {
        "supplier": supplier.pk,
        "purchase_date": purchase_date,
        "notes": "",
        "items-TOTAL_FORMS": "1",
        "items-INITIAL_FORMS": "0",
        "items-MIN_NUM_FORMS": "0",
        "items-MAX_NUM_FORMS": "50",
        "items-0-item": item.pk if item else "",
        "items-0-quantity": quantity,
        "items-0-unit_price": "10.00",
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

    def test_supplier_list_filters_and_htmx(self):
        create_supplier(name="Fornecedor A")
        create_supplier(name="Fornecedor B")

        response = self.client.get(reverse("purchases:supplier_list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fornecedor A")
        self.assertContains(response, "Fornecedor B")

        response = self.client.get(
            reverse("purchases:supplier_list"),
            {"q": "Fornecedor A"},
        )
        self.assertContains(response, "Fornecedor A")
        self.assertNotContains(response, "Fornecedor B")

        response = self.client.get(
            reverse("purchases:supplier_list"),
            {"q": "Fornecedor A"},
            HTTP_HX_REQUEST="true",
        )
        self.assertTemplateUsed(
            response,
            "purchases/partials/supplier_results.html",
        )

        response = self.client.get(
            reverse("purchases:supplier_list"),
            {"q": "   "},
        )
        self.assertContains(response, "Fornecedor A")
        self.assertContains(response, "Fornecedor B")

    def test_supplier_update_get_renders_form(self):
        supplier = create_supplier(name="Fornecedor")

        response = self.client.get(
            reverse("purchases:supplier_update", args=[supplier.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Editar fornecedor")

    def test_supplier_create_integrity_error_fallback(self):
        with patch.object(
            SupplierForm,
            "save",
            side_effect=IntegrityError,
        ):
            response = self.client.post(
                reverse("purchases:supplier_create"),
                {"name": "Fornecedor Único", "is_active": "on"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Já existe um fornecedor")

    def test_supplier_update_integrity_error_fallback(self):
        supplier = create_supplier(name="Fornecedor")

        with patch.object(
            SupplierForm,
            "save",
            side_effect=IntegrityError,
        ):
            response = self.client.post(
                reverse("purchases:supplier_update", args=[supplier.pk]),
                {"name": "Fornecedor Único", "is_active": "on"},
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
        self.assertEqual(response["Location"], purchase.get_absolute_url())
        purchase_item = purchase.items.get()
        self.assertEqual(purchase_item.description, self.item.name)
        self.assertEqual(purchase_item.unit, self.item.unit)
        self.assertEqual(purchase.total, Decimal("20.00"))

    def test_total_is_computed_from_lines(self):
        data = purchase_form_data(
            supplier=self.supplier,
            item=self.item,
            quantity="3.000",
        )
        data["items-TOTAL_FORMS"] = "2"
        data["items-1-item"] = self.item.pk
        data["items-1-description"] = ""
        data["items-1-unit"] = ""
        data["items-1-quantity"] = "2.000"
        data["items-1-unit_price"] = "4.20"

        response = self.client.post(reverse("purchases:purchase_create"), data)

        self.assertEqual(response.status_code, 302)
        purchase = Purchase.objects.get()
        self.assertEqual(purchase.total, Decimal("38.40"))

    def test_unit_price_is_required(self):
        data = purchase_form_data(supplier=self.supplier, item=self.item)
        data["items-0-unit_price"] = ""

        response = self.client.post(reverse("purchases:purchase_create"), data)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo é obrigatório.")
        self.assertFalse(Purchase.objects.exists())

    def test_update_recalculates_total(self):
        purchase = create_purchase(supplier=self.supplier)
        purchase_item = create_purchase_item(
            purchase=purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("2"),
            unit_price=Decimal("10.00"),
        )

        data = {
            "supplier": self.supplier.pk,
            "purchase_date": "2026-01-10",
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
            "items-0-unit_price": "12.50",
        }
        response = self.client.post(
            reverse("purchases:purchase_update", args=[purchase.pk]),
            data,
        )

        self.assertEqual(response.status_code, 302)
        purchase.refresh_from_db()
        self.assertEqual(purchase.total, Decimal("25.00"))

    def test_create_form_contains_wizard_progress(self):
        response = self.client.get(reverse("purchases:purchase_create"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-wizard")
        self.assertContains(response, "form-progress")
        self.assertContains(response, ">Dados<")
        self.assertContains(response, ">Linhas<")
        self.assertNotContains(response, ">Receção<")

    def test_create_form_uses_catalogue_items_only(self):
        response = self.client.get(reverse("purchases:purchase_create"))

        self.assertContains(response, reverse("inventory:item_quick_create"))
        self.assertNotContains(response, 'name="items-0-description"')
        self.assertNotContains(response, 'name="items-0-unit"')

    def test_create_invalid_header_opens_first_step(self):
        data = purchase_form_data(supplier=self.supplier, item=self.item)
        data["supplier"] = ""

        response = self.client.post(reverse("purchases:purchase_create"), data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["wizard_initial_step"], 1)

    def test_create_requires_catalogue_item(self):
        data = purchase_form_data(supplier=self.supplier, item=None)
        response = self.client.post(reverse("purchases:purchase_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Este campo é obrigatório.")
        self.assertFalse(Purchase.objects.exists())

    def test_create_without_location_permission_redirects_to_detail(self):
        self.client.force_login(
            create_user(
                "purchase-creator",
                permissions=("purchases.add_purchase",),
            )
        )
        response = self.client.post(
            reverse("purchases:purchase_create"),
            purchase_form_data(supplier=self.supplier, item=self.item),
        )
        self.assertEqual(response.status_code, 302)
        purchase = Purchase.objects.get()
        self.assertEqual(response["Location"], purchase.get_absolute_url())

    def test_purchase_requires_at_least_one_item(self):
        data = purchase_form_data(supplier=self.supplier, item=None)
        data["items-0-quantity"] = ""
        data["items-0-unit_price"] = ""
        response = self.client.post(reverse("purchases:purchase_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "pelo menos uma linha")

    def test_create_can_be_retried_after_line_validation_error(self):
        data = purchase_form_data(
            supplier=self.supplier,
            item=self.item,
            quantity="1.500",
        )
        response = self.client.post(reverse("purchases:purchase_create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["formset"].instance.pk)
        self.assertEqual(response.context["wizard_initial_step"], 2)

        response = self.client.post(
            reverse("purchases:purchase_create"),
            purchase_form_data(supplier=self.supplier, item=self.item),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Purchase.objects.count(), 1)

    def test_update_cannot_reduce_below_received_quantity(self):
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
            "items-0-unit_price": "10.00",
        }
        response = self.client.post(
            reverse("purchases:purchase_update", args=[purchase.pk]),
            data,
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "não pode ser inferior")
        self.assertEqual(response.context["wizard_initial_step"], 2)

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

    def test_receipt_creates_movement_and_updates_balance(self):
        purchase = create_purchase(supplier=self.supplier)
        purchase_item = create_purchase_item(
            purchase=purchase,
            item=self.item,
            quantity=Decimal("5"),
        )

        response = self.client.post(
            reverse("purchases:purchase_receive", args=[purchase.pk]),
            {
                "item_pk": purchase_item.pk,
                "location": warehouse().pk,
                "quantity": "2.000",
                "movement_date": "2026-01-15",
            },
        )
        self.assertEqual(response.status_code, 302)
        movement = StockMovement.objects.get(purchase_item=purchase_item)
        self.assertEqual(movement.quantity, Decimal("2.000"))
        self.assertEqual(
            purchase_item.get_active_received_quantity(),
            Decimal("2.000"),
        )

    def test_receipt_cannot_exceed_purchase_quantity(self):
        purchase = create_purchase(supplier=self.supplier)
        purchase_item = create_purchase_item(
            purchase=purchase,
            item=self.item,
            quantity=Decimal("2"),
        )

        response = self.client.post(
            reverse("purchases:purchase_receive", args=[purchase.pk]),
            {
                "item_pk": purchase_item.pk,
                "location": warehouse().pk,
                "quantity": "3.000",
                "movement_date": "2026-01-15",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "excede o que falta receber")

    def test_purchase_list_links_to_suppliers(self):
        response = self.client.get(reverse("purchases:purchase_list"))

        self.assertContains(response, reverse("purchases:supplier_list"))

    def test_purchase_list_filters_by_query(self):
        purchase = create_purchase(supplier=self.supplier)
        create_purchase_item(
            purchase=purchase,
            item=self.item,
            description="Material especial",
            unit=self.item.unit,
            quantity=Decimal("2"),
        )
        other = create_purchase(supplier=create_supplier(name="Outro fornecedor"))
        create_purchase_item(
            purchase=other,
            item=create_item(name="Outro artigo"),
            description="Outro artigo",
            quantity=Decimal("1"),
        )

        response = self.client.get(
            reverse("purchases:purchase_list"),
            {"q": "especial"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, purchase.get_absolute_url())
        self.assertNotContains(response, other.get_absolute_url())

    def test_purchase_list_filters_by_supplier(self):
        purchase = create_purchase(supplier=self.supplier)
        create_purchase_item(purchase=purchase, item=self.item, quantity=Decimal("2"))
        other_supplier = create_supplier(name="Outro fornecedor")
        other = create_purchase(supplier=other_supplier)
        create_purchase_item(purchase=other, item=self.item, quantity=Decimal("1"))

        response = self.client.get(
            reverse("purchases:purchase_list"),
            {"supplier": self.supplier.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, purchase.get_absolute_url())
        self.assertNotContains(response, other.get_absolute_url())

    def test_purchase_list_htmx_partial(self):
        response = self.client.get(
            reverse("purchases:purchase_list"),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "purchases/partials/purchase_results.html",
        )

    def test_purchase_list_hides_project_filter_without_permission(self):
        self.client.force_login(
            create_user(
                "purchase-viewer",
                permissions=("purchases.view_purchase",),
            )
        )

        response = self.client.get(reverse("purchases:purchase_list"))

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("project", response.context["filter_form"].fields)

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
        received_item = create_purchase_item(
            purchase=purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("5"),
        )
        create_purchase_item(
            purchase=purchase,
            item=create_item(name="Outro artigo"),
            quantity=Decimal("2"),
        )
        create_initial_entry(
            item=self.item,
            location=location,
            quantity=Decimal("1"),
            purchase_item=received_item,
        )

        response = self.client.get(
            reverse("purchases:purchase_list"),
            {"project": project.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["purchases"][0].item_count, 2)

    def test_purchase_detail_shows_receipt_form_until_received(self):
        purchase = create_purchase(supplier=self.supplier)
        purchase_item = create_purchase_item(
            purchase=purchase,
            item=self.item,
            quantity=Decimal("5"),
        )

        response = self.client.get(purchase.get_absolute_url())
        receive_url = reverse("purchases:purchase_receive", args=[purchase.pk])
        self.assertContains(response, receive_url)
        self.assertContains(response, f'name="item_pk" value="{purchase_item.pk}"')

        create_initial_entry(
            item=self.item,
            location=warehouse(),
            quantity=Decimal("5"),
            purchase_item=purchase_item,
        )
        response = self.client.get(purchase.get_absolute_url())
        self.assertNotContains(response, receive_url)
        self.assertContains(response, "totalmente recebida")

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


class PurchaseReceiptViewTests(TestCase):
    def setUp(self):
        self.user = create_user("receipt-manager", permissions=PURCHASE_PERMISSIONS)
        self.client.force_login(self.user)
        self.supplier = create_supplier()
        self.item = create_item()
        self.purchase = create_purchase(supplier=self.supplier)
        self.purchase_item = create_purchase_item(
            purchase=self.purchase,
            item=self.item,
            quantity=Decimal("5"),
        )

    def receipt_data(
        self,
        line,
        *,
        location=None,
        quantity="2.000",
        movement_date="2026-01-15",
    ):
        return {
            "item_pk": line.pk,
            "location": (location or warehouse()).pk,
            "quantity": quantity,
            "movement_date": movement_date,
        }

    def test_detail_shows_pending_line_form(self):
        response = self.client.get(self.purchase.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item.name)
        self.assertContains(response, 'name="quantity"')
        self.assertContains(response, 'name="movement_date"')
        self.assertContains(response, "Por receber")

    def test_post_receives_and_redirects(self):
        response = self.client.post(
            reverse("purchases:purchase_receive", args=[self.purchase.pk]),
            self.receipt_data(self.purchase_item),
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], self.purchase.get_absolute_url())
        movement = StockMovement.objects.get(purchase_item=self.purchase_item)
        self.assertEqual(movement.quantity, Decimal("2.000"))
        self.assertEqual(movement.movement_date, date(2026, 1, 15))
        self.assertEqual(
            self.purchase_item.get_active_received_quantity(),
            Decimal("2.000"),
        )

    def test_post_rejects_quantity_above_remaining(self):
        response = self.client.post(
            reverse("purchases:purchase_receive", args=[self.purchase.pk]),
            self.receipt_data(self.purchase_item, quantity="6.000"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "excede o que falta receber")
        self.assertFalse(
            StockMovement.objects.filter(purchase_item=self.purchase_item).exists()
        )

    def test_post_rejects_fractional_discrete_quantity(self):
        response = self.client.post(
            reverse("purchases:purchase_receive", args=[self.purchase.pk]),
            self.receipt_data(self.purchase_item, quantity="1.500"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "só admite quantidades inteiras")
        self.assertFalse(
            StockMovement.objects.filter(purchase_item=self.purchase_item).exists()
        )

    def test_fully_received_line_has_no_form(self):
        create_initial_entry(
            item=self.item,
            location=warehouse(),
            quantity=Decimal("5"),
            purchase_item=self.purchase_item,
        )
        response = self.client.get(self.purchase.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "totalmente recebida")
        self.assertNotContains(response, 'name="quantity"')

    def test_inactive_catalogue_item_has_no_form(self):
        self.item.is_active = False
        self.item.save(update_fields=["is_active"])
        response = self.client.get(self.purchase.get_absolute_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "está inativo")
        self.assertNotContains(response, 'name="quantity"')

    def test_item_from_another_purchase_is_rejected(self):
        other_purchase = create_purchase(
            supplier=create_supplier(name="Outro fornecedor")
        )
        other_item = create_purchase_item(
            purchase=other_purchase,
            item=self.item,
            quantity=Decimal("1"),
        )
        response = self.client.post(
            reverse("purchases:purchase_receive", args=[self.purchase.pk]),
            self.receipt_data(other_item, quantity="1.000"),
        )

        self.assertEqual(response.status_code, 404)

    def test_missing_item_pk_is_rejected(self):
        response = self.client.post(
            reverse("purchases:purchase_receive", args=[self.purchase.pk]),
            {},
        )

        self.assertEqual(response.status_code, 400)

    def test_receive_validation_error_renders_form(self):
        with patch(
            "purchases.views.receive_purchase_item",
            side_effect=ValidationError("Falha simulada"),
        ):
            response = self.client.post(
                reverse("purchases:purchase_receive", args=[self.purchase.pk]),
                self.receipt_data(self.purchase_item),
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Falha simulada")

    def test_get_is_not_allowed(self):
        response = self.client.get(
            reverse("purchases:purchase_receive", args=[self.purchase.pk])
        )

        self.assertEqual(response.status_code, 405)

    def test_permissions_are_required(self):
        self.client.force_login(create_user("receipt-viewer"))
        response = self.client.post(
            reverse("purchases:purchase_receive", args=[self.purchase.pk]),
            self.receipt_data(self.purchase_item),
        )

        self.assertEqual(response.status_code, 403)

    def test_csrf_is_required(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            reverse("purchases:purchase_receive", args=[self.purchase.pk]),
            self.receipt_data(self.purchase_item),
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
        self.assertContains(response, 'id="id_items-1-item"')
        self.assertContains(response, 'name="items-1-purchase"')
        self.assertContains(response, 'name="items-TOTAL_FORMS" value="2"')
        self.assertContains(response, "hx-swap-oob")

    def test_row_endpoint_limits_to_50_rows(self):
        response = self.client.get(
            reverse("purchases:purchase_item_row"),
            {"items-TOTAL_FORMS": "50"},
        )
        self.assertEqual(response.status_code, 400)

    def test_row_endpoint_rejects_invalid_total(self):
        response = self.client.get(
            reverse("purchases:purchase_item_row"),
            {"items-TOTAL_FORMS": "abc"},
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


class ReceiptMarkupTests(TestCase):
    def setUp(self):
        self.user = create_user("receipt-manager", permissions=PURCHASE_PERMISSIONS)
        self.client.force_login(self.user)
        self.supplier = create_supplier()
        self.item = create_item()
        self.purchase = create_purchase(supplier=self.supplier)
        create_purchase_item(purchase=self.purchase, item=self.item, quantity=Decimal("2"))

    def test_purchase_detail_uses_shared_card_and_meta_markup(self):
        response = self.client.get(self.purchase.get_absolute_url())

        self.assertContains(response, 'class="card"')
        self.assertContains(response, 'class="card-header"')
        self.assertContains(response, "meta-grid")

    def test_supplier_form_renders_switch_control(self):
        response = self.client.get(reverse("purchases:supplier_create"))

        self.assertContains(response, 'class="switch"')
        self.assertContains(response, "switch-track")
        self.assertContains(response, 'type="checkbox"')


class PurchaseWizardStepTests(TestCase):
    def test_unbound_and_valid_forms_return_first_step(self):
        supplier = create_supplier()
        item = create_item()

        unbound_form = PurchaseForm()
        formset = PurchaseItemFormSet(instance=Purchase(), prefix="items")
        self.assertEqual(_purchase_wizard_step(unbound_form, formset), 1)

        data = purchase_form_data(supplier=supplier, item=item)
        form = PurchaseForm(data=data)
        formset = PurchaseItemFormSet(
            data=data,
            instance=Purchase(),
            prefix="items",
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertTrue(formset.is_valid(), formset.errors)
        self.assertEqual(_purchase_wizard_step(form, formset), 1)
