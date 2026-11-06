from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings

from inventory.models import Item, Location, StockMovement
from inventory.services import location_balance
from projects.models import Project
from projects.tests.base import create_user
from purchases.models import Purchase, PurchaseItem, Supplier


@override_settings(DEBUG=True)
class SeedDemoCommandTests(TestCase):
    def seed(self, **options):
        return call_command("seed_demo", stdout=StringIO(), **options)

    def test_seed_demo_creates_expected_data(self):
        self.seed()

        self.assertEqual(
            Project.objects.filter(name__startswith="Demo · ").count(),
            4,
        )
        self.assertEqual(
            Supplier.objects.filter(name__startswith="Demo · ").count(),
            2,
        )
        self.assertEqual(
            Item.objects.filter(name__startswith="Demo · ").count(),
            7,
        )
        self.assertEqual(
            Purchase.objects.filter(notes__startswith="[demo]").count(),
            2,
        )
        self.assertEqual(
            PurchaseItem.objects.filter(
                purchase__notes__startswith="[demo]"
            ).count(),
            6,
        )
        self.assertEqual(
            StockMovement.objects.filter(notes__startswith="[demo]").count(),
            16,
        )

        self.assertTrue(
            Location.objects.filter(
                location_type=Location.Type.WAREHOUSE
            ).exists()
        )
        for project in Project.objects.filter(name__startswith="Demo · "):
            with self.subTest(project=project.name):
                self.assertTrue(
                    Location.objects.filter(project=project).exists()
                )

    def test_seed_demo_is_idempotent(self):
        self.seed()
        counts = {
            "projects": Project.objects.count(),
            "suppliers": Supplier.objects.count(),
            "items": Item.objects.count(),
            "purchases": Purchase.objects.count(),
            "purchase_items": PurchaseItem.objects.count(),
            "locations": Location.objects.count(),
            "movements": StockMovement.objects.count(),
        }

        self.seed()

        self.assertEqual(Project.objects.count(), counts["projects"])
        self.assertEqual(Supplier.objects.count(), counts["suppliers"])
        self.assertEqual(Item.objects.count(), counts["items"])
        self.assertEqual(Purchase.objects.count(), counts["purchases"])
        self.assertEqual(
            PurchaseItem.objects.count(),
            counts["purchase_items"],
        )
        self.assertEqual(Location.objects.count(), counts["locations"])
        self.assertEqual(StockMovement.objects.count(), counts["movements"])

        notes = list(
            StockMovement.objects.filter(
                notes__startswith="[demo]"
            ).values_list("notes", flat=True)
        )
        self.assertEqual(len(notes), len(set(notes)))

    def test_seed_demo_respects_receipt_limits_and_balances(self):
        self.seed()

        for purchase_item in PurchaseItem.objects.filter(
            purchase__notes__startswith="[demo]"
        ):
            with self.subTest(purchase_item=purchase_item.description):
                self.assertLessEqual(
                    purchase_item.get_active_received_quantity(),
                    purchase_item.quantity,
                )

        for item in Item.objects.filter(name__startswith="Demo · "):
            for location in Location.objects.all():
                with self.subTest(item=item.name, location=location.name):
                    self.assertGreaterEqual(
                        location_balance(item, location),
                        Decimal("0.000"),
                    )

    def test_cancelled_movement_is_excluded_from_balance(self):
        self.seed()

        escora = Item.objects.get(name="Demo · Escora")
        warehouse = Location.objects.get(
            location_type=Location.Type.WAREHOUSE
        )
        movement = StockMovement.objects.get(
            notes="[demo] entrada inicial de escora no armazém"
        )

        self.assertTrue(movement.is_cancelled)
        self.assertEqual(
            location_balance(escora, warehouse),
            Decimal("0.000"),
        )

    def test_seed_demo_leaves_partial_receipts(self):
        self.seed()

        cement = PurchaseItem.objects.get(
            purchase__notes="[demo] Compra de materiais",
            description="Demo · Cimento",
        )

        self.assertGreater(
            cement.get_active_received_quantity(),
            Decimal("0"),
        )
        self.assertLess(
            cement.get_active_received_quantity(),
            cement.quantity,
        )

    def test_seed_demo_assigns_user_to_movements(self):
        user = create_user("seed-user")

        self.seed(user="seed-user")

        movements = StockMovement.objects.filter(
            notes__startswith="[demo]"
        )
        self.assertFalse(movements.filter(created_by__isnull=True).exists())
        self.assertEqual(
            movements.filter(created_by=user).count(),
            16,
        )
        cancelled = StockMovement.objects.get(
            notes="[demo] entrada inicial de escora no armazém"
        )
        self.assertEqual(cancelled.cancelled_by, user)

    def test_seed_demo_rejects_unknown_user(self):
        with self.assertRaises(CommandError):
            self.seed(user="missing")

        self.assertFalse(Project.objects.exists())

    def test_seed_demo_does_not_create_users(self):
        before = get_user_model().objects.count()

        self.seed()

        self.assertEqual(get_user_model().objects.count(), before)
        self.assertTrue(
            StockMovement.objects.filter(created_by__isnull=True).exists()
        )

    @override_settings(DEBUG=False)
    def test_seed_demo_requires_force_when_debug_is_disabled(self):
        with self.assertRaises(CommandError):
            self.seed()

        self.assertFalse(Project.objects.exists())

    @override_settings(DEBUG=False)
    def test_seed_demo_accepts_force_when_debug_is_disabled(self):
        self.seed(force=True)

        self.assertTrue(
            Project.objects.filter(name__startswith="Demo · ").exists()
        )
