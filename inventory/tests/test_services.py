from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from inventory.models import Item, StockMovement
from inventory.services import (
    receive_purchase_item,
    cancel_stock_movement,
    create_adjustment_in,
    create_adjustment_out,
    create_transfer,
    get_project_location_balances,
    location_balance,
    return_to_warehouse,
)
from purchases.models import Purchase, PurchaseItem, Supplier
from projects.tests.base import create_project

from .base import create_initial_entry, create_item, project_location, warehouse


class MovementServiceTests(TestCase):
    def setUp(self):
        self.item = create_item()
        self.warehouse = warehouse()
        self.project = create_project(name="Obra A")
        self.project_location = project_location(self.project)

    def test_initial_entry_increases_balance(self):
        movement = create_initial_entry(
            item=self.item,
            location=self.warehouse,
            quantity=Decimal("10"),
        )
        self.assertEqual(movement.movement_type, StockMovement.Type.INITIAL_ENTRY)
        self.assertEqual(
            location_balance(self.item, self.warehouse),
            Decimal("10"),
        )

    def test_transfer_moves_balance_between_locations(self):
        create_initial_entry(
            item=self.item,
            location=self.warehouse,
            quantity=Decimal("10"),
        )
        transfer = create_transfer(
            item=self.item,
            from_location=self.warehouse,
            to_location=self.project_location,
            quantity=Decimal("4"),
            movement_date=date(2026, 2, 1),
            user=None,
        )

        self.assertEqual(transfer.movement_type, StockMovement.Type.TRANSFER)
        self.assertEqual(location_balance(self.item, self.warehouse), Decimal("6"))
        self.assertEqual(
            location_balance(self.item, self.project_location),
            Decimal("4"),
        )

    def test_transfer_cannot_exceed_source_balance(self):
        create_initial_entry(
            item=self.item,
            location=self.warehouse,
            quantity=Decimal("3"),
        )
        with self.assertRaises(ValidationError):
            create_transfer(
                item=self.item,
                from_location=self.warehouse,
                to_location=self.project_location,
                quantity=Decimal("4"),
                movement_date=date(2026, 2, 1),
                user=None,
            )

    def test_return_to_warehouse(self):
        create_initial_entry(
            item=self.item,
            location=self.project_location,
            quantity=Decimal("5"),
        )
        return_to_warehouse(
            item=self.item,
            from_location=self.project_location,
            quantity=Decimal("2"),
            movement_date=date(2026, 2, 1),
            user=None,
        )
        self.assertEqual(
            location_balance(self.item, self.project_location),
            Decimal("3"),
        )
        self.assertEqual(location_balance(self.item, self.warehouse), Decimal("2"))

    def test_adjustments_require_reason_and_validate_balance(self):
        with self.assertRaises(ValidationError):
            create_adjustment_in(
                item=self.item,
                to_location=self.warehouse,
                quantity=Decimal("1"),
                movement_date=date(2026, 2, 1),
                user=None,
                notes="",
            )

        create_adjustment_in(
            item=self.item,
            to_location=self.warehouse,
            quantity=Decimal("2"),
            movement_date=date(2026, 2, 1),
            user=None,
            notes="Contagem corrigida",
        )
        create_adjustment_out(
            item=self.item,
            from_location=self.warehouse,
            quantity=Decimal("1"),
            movement_date=date(2026, 2, 2),
            user=None,
            notes="Material danificado",
        )
        self.assertEqual(location_balance(self.item, self.warehouse), Decimal("1"))

        with self.assertRaises(ValidationError):
            create_adjustment_out(
                item=self.item,
                from_location=self.warehouse,
                quantity=Decimal("2"),
                movement_date=date(2026, 2, 3),
                user=None,
                notes="Correção excessiva",
            )

    def test_archived_project_blocks_incoming_but_allows_outgoing(self):
        create_initial_entry(
            item=self.item,
            location=self.project_location,
            quantity=Decimal("5"),
        )
        self.project.archive()

        with self.assertRaises(ValidationError):
            create_transfer(
                item=self.item,
                from_location=self.warehouse,
                to_location=self.project_location,
                quantity=Decimal("1"),
                movement_date=date(2026, 2, 1),
                user=None,
            )

        create_transfer(
            item=self.item,
            from_location=self.project_location,
            to_location=self.warehouse,
            quantity=Decimal("2"),
            movement_date=date(2026, 2, 2),
            user=None,
        )
        self.assertEqual(
            location_balance(self.item, self.project_location),
            Decimal("3"),
        )

    def test_inactive_item_and_location_are_rejected(self):
        inactive_item = create_item(name="Inativo", is_active=False)
        with self.assertRaises(ValidationError):
            create_initial_entry(
                item=inactive_item,
                location=self.warehouse,
                quantity=Decimal("1"),
            )

        self.project_location.is_active = False
        self.project_location.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            create_initial_entry(
                item=self.item,
                location=self.project_location,
                quantity=Decimal("1"),
            )

    def test_cancellation_removes_movement_from_balance(self):
        movement = create_initial_entry(
            item=self.item,
            location=self.warehouse,
            quantity=Decimal("10"),
        )
        cancel_stock_movement(
            movement=movement,
            user=None,
            reason="Registo duplicado",
        )
        movement.refresh_from_db()
        self.assertTrue(movement.is_cancelled)
        self.assertEqual(movement.cancellation_reason, "Registo duplicado")
        self.assertEqual(location_balance(self.item, self.warehouse), Decimal("0"))

        with self.assertRaises(ValidationError):
            cancel_stock_movement(
                movement=movement,
                user=None,
                reason="Outra vez",
            )

    def test_cancellation_cannot_make_destination_negative(self):
        initial = create_initial_entry(
            item=self.item,
            location=self.project_location,
            quantity=Decimal("10"),
        )
        create_transfer(
            item=self.item,
            from_location=self.project_location,
            to_location=self.warehouse,
            quantity=Decimal("6"),
            movement_date=date(2026, 2, 1),
            user=None,
        )

        with self.assertRaises(ValidationError):
            cancel_stock_movement(
                movement=initial,
                user=None,
                reason="Cancelamento inválido",
            )

    def test_cancellation_of_transfer_restores_source_balance(self):
        create_initial_entry(
            item=self.item,
            location=self.warehouse,
            quantity=Decimal("10"),
        )
        transfer = create_transfer(
            item=self.item,
            from_location=self.warehouse,
            to_location=self.project_location,
            quantity=Decimal("5"),
            movement_date=date(2026, 2, 1),
            user=None,
        )
        cancel_stock_movement(
            movement=transfer,
            user=None,
            reason="Transferência errada",
        )
        self.assertEqual(location_balance(self.item, self.warehouse), Decimal("10"))
        self.assertEqual(
            location_balance(self.item, self.project_location),
            Decimal("0"),
        )

    def test_project_balances_include_only_active_movements(self):
        movement = create_initial_entry(
            item=self.item,
            location=self.project_location,
            quantity=Decimal("7"),
        )
        cancel_stock_movement(
            movement=movement,
            user=None,
            reason="Duplicado",
        )
        location, balances = get_project_location_balances(self.project)
        self.assertEqual(location, self.project_location)
        self.assertEqual(balances, [])


class PurchaseReceiptServiceTests(TestCase):
    def setUp(self):
        self.item = create_item()
        self.warehouse = warehouse()
        self.supplier = Supplier.objects.create(name="Fornecedor")
        self.purchase = Purchase.objects.create(
            supplier=self.supplier,
            purchase_date=date(2026, 1, 10),
            total=Decimal("100.00"),
        )
        self.purchase_item = PurchaseItem.objects.create(
            purchase=self.purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("5"),
        )

    def test_receive_purchase_item_creates_initial_entry(self):
        movement = receive_purchase_item(
            purchase_item=self.purchase_item,
            location=self.warehouse,
            quantity=Decimal("3"),
            movement_date=date(2026, 1, 10),
            user=None,
        )
        self.assertEqual(movement.movement_type, StockMovement.Type.INITIAL_ENTRY)
        self.assertEqual(movement.purchase_item, self.purchase_item)
        self.assertEqual(
            location_balance(self.item, self.warehouse),
            Decimal("3"),
        )
        self.assertEqual(
            self.purchase_item.get_active_received_quantity(),
            Decimal("3"),
        )

    def test_receipt_cannot_exceed_purchase_line_quantity(self):
        receive_purchase_item(
            purchase_item=self.purchase_item,
            location=self.warehouse,
            quantity=Decimal("3"),
            movement_date=date(2026, 1, 10),
            user=None,
        )
        with self.assertRaises(ValidationError):
            receive_purchase_item(
                purchase_item=self.purchase_item,
                location=self.warehouse,
                quantity=Decimal("3"),
                movement_date=date(2026, 1, 11),
                user=None,
            )

    def test_receipt_requires_matching_unit(self):
        self.purchase_item.unit = "kg"
        self.purchase_item.save(update_fields=["unit"])
        with self.assertRaises(ValidationError):
            receive_purchase_item(
                purchase_item=self.purchase_item,
                location=self.warehouse,
                quantity=Decimal("1"),
                movement_date=date(2026, 1, 10),
                user=None,
            )


class QuantityPrecisionServiceTests(TestCase):
    def test_initial_entry_rejects_fractional_discrete_quantity(self):
        item = create_item(name="Tijolo", unit="un")

        with self.assertRaises(ValidationError):
            create_initial_entry(
                item=item,
                location=warehouse(),
                quantity=Decimal("1.500"),
            )

        self.assertFalse(StockMovement.objects.filter(item=item).exists())

    def test_transfer_accepts_fractional_continuous_quantity(self):
        item = create_item(name="Areia", unit="m3")
        create_initial_entry(
            item=item,
            location=warehouse(),
            quantity=Decimal("2.000"),
        )

        movement = create_transfer(
            item=item,
            from_location=warehouse(),
            to_location=project_location(),
            quantity=Decimal("1.500"),
            movement_date=date(2026, 1, 21),
            user=None,
        )

        self.assertEqual(movement.quantity, Decimal("1.500"))
