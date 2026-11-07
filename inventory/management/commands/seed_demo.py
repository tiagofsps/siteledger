from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from inventory.models import Item, StockMovement
from inventory.services import (
    cancel_stock_movement,
    create_adjustment_in,
    create_adjustment_out,
    create_initial_entry,
    create_transfer,
    ensure_project_location,
    get_warehouse_location,
    receive_purchase_item,
    return_to_warehouse,
)
from projects.models import Project
from purchases.models import Purchase, PurchaseItem, Supplier
from purchases.services import recalculate_purchase_total

DEMO_NAME_PREFIX = "Demo · "
DEMO_NOTE_PREFIX = "[demo]"


class Command(BaseCommand):
    help = "Popula a base de dados local com dados de demonstração."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            help="Utilizador a associar aos movimentos criados.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Permite executar com DEBUG=False.",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError(
                "O comando seed_demo destina-se a desenvolvimento. "
                "Use --force para continuar."
            )

        user = self._get_user(options["user"])
        today = timezone.localdate()

        with transaction.atomic():
            warehouse = self._seed_warehouse()
            project_locations = self._seed_projects(today)
            suppliers = self._seed_suppliers()
            items = self._seed_items()
            purchases, purchase_items = self._seed_purchases(
                today,
                suppliers,
                items,
            )
            self._seed_movements(
                today=today,
                warehouse=warehouse,
                project_locations=project_locations,
                items=items,
                purchases=purchases,
                purchase_items=purchase_items,
                user=user,
            )

        self.stdout.write(
            self.style.SUCCESS("Dados de demonstração criados ou atualizados.")
        )

    def _get_user(self, username):
        if not username:
            return None
        try:
            return get_user_model().objects.get(username=username)
        except get_user_model().DoesNotExist as error:
            raise CommandError(
                f'Utilizador "{username}" não encontrado.'
            ) from error

    def _seed_warehouse(self):
        warehouse = get_warehouse_location()
        if not warehouse.is_active:
            warehouse.is_active = True
            warehouse.save(update_fields=["is_active", "updated_at"])
        return warehouse

    def _seed_projects(self, today):
        definitions = (
            (
                "remodelacao",
                "Remodelação Centro",
                Project.Status.IN_PROGRESS,
                False,
                45,
            ),
            (
                "moradia",
                "Moradia Norte",
                Project.Status.PLANNED,
                False,
                20,
            ),
            (
                "concluida",
                "Obra Concluída",
                Project.Status.COMPLETED,
                False,
                120,
            ),
            (
                "arquivada",
                "Obra Arquivada",
                Project.Status.COMPLETED,
                True,
                180,
            ),
        )

        locations = {}
        for key, name, status, archived, days_ago in definitions:
            project, _ = Project.objects.update_or_create(
                name=f"{DEMO_NAME_PREFIX}{name}",
                defaults={
                    "address": "Morada de demonstração",
                    "description": "Obra criada pelo comando seed_demo.",
                    "start_date": today - timedelta(days=days_ago),
                    "status": status,
                },
            )

            if archived and not project.is_archived:
                project.archive()
            elif not archived and project.is_archived:
                project.unarchive()

            location = ensure_project_location(project)
            if not location.is_active:
                location.is_active = True
                location.save(update_fields=["is_active", "updated_at"])

            locations[key] = location

        return locations

    def _seed_suppliers(self):
        materials, _ = Supplier.objects.update_or_create(
            name=f"{DEMO_NAME_PREFIX}Materiais de Construção",
            defaults={"is_active": True},
        )
        tools, _ = Supplier.objects.update_or_create(
            name=f"{DEMO_NAME_PREFIX}Ferramentas e Equipamentos",
            defaults={"is_active": True},
        )
        return {
            "materials": materials,
            "tools": tools,
        }

    def _seed_items(self):
        definitions = (
            ("cimento", "Cimento", Item.Category.MATERIAL, "sc"),
            ("tijolo", "Tijolo", Item.Category.MATERIAL, "un"),
            ("areia", "Areia", Item.Category.MATERIAL, "m3"),
            ("betoneira", "Betoneira", Item.Category.EQUIPMENT, "un"),
            (
                "andaime",
                "Andaime",
                Item.Category.REUSABLE_MATERIAL,
                "md",
            ),
            (
                "escora",
                "Escora",
                Item.Category.REUSABLE_MATERIAL,
                "un",
            ),
            ("tinta", "Tinta", Item.Category.MATERIAL, "l"),
        )

        items = {}
        for key, name, category, unit in definitions:
            item, _ = Item.objects.update_or_create(
                name=f"{DEMO_NAME_PREFIX}{name}",
                defaults={
                    "category": category,
                    "unit": unit,
                    "description": "Artigo criado pelo comando seed_demo.",
                    "is_active": True,
                },
            )
            items[key] = item

        return items

    def _seed_purchases(self, today, suppliers, items):
        materials, _ = Purchase.objects.update_or_create(
            notes=f"{DEMO_NOTE_PREFIX} Compra de materiais",
            defaults={
                "supplier": suppliers["materials"],
                "purchase_date": today - timedelta(days=20),
                "total": Decimal("320.00"),
            },
        )
        tools, _ = Purchase.objects.update_or_create(
            notes=f"{DEMO_NOTE_PREFIX} Compra de ferramentas",
            defaults={
                "supplier": suppliers["tools"],
                "purchase_date": today - timedelta(days=10),
                "total": Decimal("450.00"),
            },
        )

        purchase_items = {
            "cement": self._seed_purchase_line(
                materials,
                item=items["cimento"],
                description=items["cimento"].name,
                unit=items["cimento"].unit,
                quantity=Decimal("20.000"),
                unit_price=Decimal("6.50"),
            ),
            "brick": self._seed_purchase_line(
                materials,
                item=items["tijolo"],
                description=items["tijolo"].name,
                unit=items["tijolo"].unit,
                quantity=Decimal("500.000"),
                unit_price=Decimal("0.35"),
            ),
            "sand": self._seed_purchase_line(
                materials,
                item=items["areia"],
                description=items["areia"].name,
                unit=items["areia"].unit,
                quantity=Decimal("5.000"),
                unit_price=Decimal("25.00"),
            ),
            "mixer": self._seed_purchase_line(
                tools,
                item=items["betoneira"],
                description=items["betoneira"].name,
                unit=items["betoneira"].unit,
                quantity=Decimal("1.000"),
                unit_price=Decimal("450.00"),
            ),
            "scaffolding": self._seed_purchase_line(
                tools,
                item=items["andaime"],
                description=items["andaime"].name,
                unit=items["andaime"].unit,
                quantity=Decimal("10.000"),
                unit_price=Decimal("12.50"),
            ),
            "reusable": self._seed_purchase_line(
                tools,
                item=items["escora"],
                description=items["escora"].name,
                unit=items["escora"].unit,
                quantity=Decimal("8.000"),
                unit_price=Decimal("9.50"),
            ),
        }

        recalculate_purchase_total(materials)
        recalculate_purchase_total(tools)

        return {
            "materials": materials,
            "tools": tools,
        }, purchase_items

    def _seed_purchase_line(
        self,
        purchase,
        *,
        description,
        unit,
        quantity,
        item=None,
        unit_price=None,
    ):
        purchase_item, _ = PurchaseItem.objects.update_or_create(
            purchase=purchase,
            description=description,
            defaults={
                "item": item,
                "unit": unit,
                "quantity": quantity,
                "unit_price": unit_price,
            },
        )
        return purchase_item

    def _seed_movements(
        self,
        *,
        today,
        warehouse,
        project_locations,
        items,
        purchases,
        purchase_items,
        user,
    ):
        remodelacao = project_locations["remodelacao"]
        moradia = project_locations["moradia"]
        materials_date = purchases["materials"].purchase_date

        def marker(label):
            return f"{DEMO_NOTE_PREFIX} {label}"

        self._ensure_movement(
            marker("receção cimento Remodelação Centro"),
            receive_purchase_item,
            purchase_item=purchase_items["cement"],
            location=remodelacao,
            quantity=Decimal("10.000"),
            movement_date=materials_date,
            user=user,
        )
        self._ensure_movement(
            marker("receção cimento armazém"),
            receive_purchase_item,
            purchase_item=purchase_items["cement"],
            location=warehouse,
            quantity=Decimal("5.000"),
            movement_date=materials_date,
            user=user,
        )
        self._ensure_movement(
            marker("receção tijolo Remodelação Centro"),
            receive_purchase_item,
            purchase_item=purchase_items["brick"],
            location=remodelacao,
            quantity=Decimal("300.000"),
            movement_date=materials_date,
            user=user,
        )
        self._ensure_movement(
            marker("receção tijolo armazém"),
            receive_purchase_item,
            purchase_item=purchase_items["brick"],
            location=warehouse,
            quantity=Decimal("200.000"),
            movement_date=materials_date,
            user=user,
        )
        self._ensure_movement(
            marker("receção areia Moradia Norte"),
            receive_purchase_item,
            purchase_item=purchase_items["sand"],
            location=moradia,
            quantity=Decimal("3.000"),
            movement_date=materials_date,
            user=user,
        )
        self._ensure_movement(
            marker("receção betoneira Remodelação Centro"),
            receive_purchase_item,
            purchase_item=purchase_items["mixer"],
            location=remodelacao,
            quantity=Decimal("1.000"),
            movement_date=purchases["tools"].purchase_date,
            user=user,
        )
        self._ensure_movement(
            marker("receção andaime Remodelação Centro"),
            receive_purchase_item,
            purchase_item=purchase_items["scaffolding"],
            location=remodelacao,
            quantity=Decimal("6.000"),
            movement_date=purchases["tools"].purchase_date,
            user=user,
        )
        self._ensure_movement(
            marker("receção andaime armazém"),
            receive_purchase_item,
            purchase_item=purchase_items["scaffolding"],
            location=warehouse,
            quantity=Decimal("4.000"),
            movement_date=purchases["tools"].purchase_date,
            user=user,
        )

        self._ensure_movement(
            marker("entrada inicial tinta armazém"),
            create_initial_entry,
            item=items["tinta"],
            to_location=warehouse,
            quantity=Decimal("10.000"),
            movement_date=today - timedelta(days=30),
            user=user,
        )

        self._ensure_movement(
            marker("transferência cimento armazém para Moradia Norte"),
            create_transfer,
            item=items["cimento"],
            from_location=warehouse,
            to_location=moradia,
            quantity=Decimal("3.000"),
            movement_date=today - timedelta(days=15),
            user=user,
        )
        self._ensure_movement(
            marker("devolução andaime para armazém"),
            return_to_warehouse,
            item=items["andaime"],
            from_location=remodelacao,
            quantity=Decimal("2.000"),
            movement_date=today - timedelta(days=12),
            user=user,
        )
        self._ensure_movement(
            marker("transferência betoneira Remodelação Centro para Moradia Norte"),
            create_transfer,
            item=items["betoneira"],
            from_location=remodelacao,
            to_location=moradia,
            quantity=Decimal("1.000"),
            movement_date=today - timedelta(days=8),
            user=user,
        )
        self._ensure_movement(
            marker("transferência tinta armazém para Remodelação Centro"),
            create_transfer,
            item=items["tinta"],
            from_location=warehouse,
            to_location=remodelacao,
            quantity=Decimal("2.000"),
            movement_date=today - timedelta(days=6),
            user=user,
        )

        self._ensure_movement(
            marker("correção de entrada de tijolo no armazém"),
            create_adjustment_in,
            item=items["tijolo"],
            to_location=warehouse,
            quantity=Decimal("5.000"),
            movement_date=today - timedelta(days=5),
            user=user,
        )
        self._ensure_movement(
            marker("correção de saída de cimento no armazém"),
            create_adjustment_out,
            item=items["cimento"],
            from_location=warehouse,
            quantity=Decimal("2.000"),
            movement_date=today - timedelta(days=4),
            user=user,
        )

        cancelled_marker = marker("entrada inicial de escora no armazém")
        cancelled_movement = self._ensure_movement(
            cancelled_marker,
            create_initial_entry,
            item=items["escora"],
            to_location=warehouse,
            quantity=Decimal("4.000"),
            movement_date=today - timedelta(days=3),
            user=user,
        )
        if cancelled_movement is None:
            cancelled_movement = StockMovement.objects.filter(
                notes=cancelled_marker
            ).first()
        if (
            cancelled_movement is not None
            and not cancelled_movement.is_cancelled
        ):
            cancel_stock_movement(
                movement=cancelled_movement,
                user=user,
                reason="Registo duplicado (demo)",
            )

    def _ensure_movement(self, marker, service, **kwargs):
        if StockMovement.objects.filter(notes=marker).exists():
            return None
        return service(notes=marker, **kwargs)
