from django.conf import settings
from django.db import models
from django.urls import reverse

from .units import Unit


class Item(models.Model):
    class Category(models.TextChoices):
        MATERIAL = "material", "Material"
        EQUIPMENT = "equipment", "Equipamento"
        REUSABLE_MATERIAL = "reusable_material", "Material reutilizável"

    name = models.CharField("nome", max_length=200)
    category = models.CharField("categoria", max_length=30, choices=Category.choices)
    unit = models.CharField(
        "unidade de referência",
        max_length=8,
        choices=Unit.choices,
    )
    description = models.TextField("descrição", blank=True)
    is_active = models.BooleanField("ativo", default=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "artigo"
        verbose_name_plural = "artigos"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(unit__in=Unit.values),
                name="item_unit_valid",
            ),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_unit_display()})"

    def get_absolute_url(self):
        return reverse("inventory:item_detail", kwargs={"pk": self.pk})


class Location(models.Model):
    class Type(models.TextChoices):
        WAREHOUSE = "warehouse", "Armazém"
        PROJECT = "project", "Obra"

    name = models.CharField("nome", max_length=200)
    location_type = models.CharField(
        "tipo",
        max_length=20,
        choices=Type.choices,
    )
    project = models.OneToOneField(
        "projects.Project",
        on_delete=models.PROTECT,
        related_name="location",
        verbose_name="obra",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField("ativa", default=True)
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "localização"
        verbose_name_plural = "localizações"
        constraints = [
            models.UniqueConstraint(
                fields=["location_type"],
                condition=models.Q(location_type="warehouse"),
                name="unique_warehouse_location",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(location_type="warehouse", project__isnull=True)
                    | models.Q(location_type="project", project__isnull=False)
                ),
                name="location_type_matches_project",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def is_warehouse(self):
        return self.location_type == self.Type.WAREHOUSE

    @property
    def is_project(self):
        return self.location_type == self.Type.PROJECT


class StockMovement(models.Model):
    class Type(models.TextChoices):
        INITIAL_ENTRY = "initial_entry", "Entrada inicial"
        TRANSFER = "transfer", "Transferência"
        ADJUSTMENT_IN = "adjustment_in", "Correção de entrada"
        ADJUSTMENT_OUT = "adjustment_out", "Correção de saída"

    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="artigo",
    )
    from_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="outgoing_movements",
        verbose_name="localização de origem",
        null=True,
        blank=True,
    )
    to_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="incoming_movements",
        verbose_name="localização de destino",
        null=True,
        blank=True,
    )
    purchase_item = models.ForeignKey(
        "purchases.PurchaseItem",
        on_delete=models.PROTECT,
        related_name="movements",
        verbose_name="artigo da compra",
        null=True,
        blank=True,
    )
    quantity = models.DecimalField("quantidade", max_digits=12, decimal_places=3)
    movement_type = models.CharField(
        "tipo de movimento",
        max_length=30,
        choices=Type.choices,
    )
    movement_date = models.DateField("data do movimento")
    notes = models.TextField("observações", blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_stock_movements",
        verbose_name="criado por",
        null=True,
        blank=True,
    )
    cancelled_at = models.DateTimeField("cancelado em", null=True, blank=True)
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_stock_movements",
        verbose_name="cancelado por",
        null=True,
        blank=True,
    )
    cancellation_reason = models.TextField("motivo do cancelamento", blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["-movement_date", "-created_at"]
        verbose_name = "movimento"
        verbose_name_plural = "movimentos"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="stock_movement_quantity_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        movement_type="initial_entry",
                        from_location__isnull=True,
                        to_location__isnull=False,
                    )
                    | models.Q(
                        movement_type="transfer",
                        from_location__isnull=False,
                        to_location__isnull=False,
                    )
                    | models.Q(
                        movement_type="adjustment_in",
                        from_location__isnull=True,
                        to_location__isnull=False,
                    )
                    | models.Q(
                        movement_type="adjustment_out",
                        from_location__isnull=False,
                        to_location__isnull=True,
                    )
                ),
                name="stock_movement_locations_match_type",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(from_location__isnull=True)
                    | ~models.Q(from_location=models.F("to_location"))
                ),
                name="stock_movement_locations_different",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(purchase_item__isnull=True)
                    | models.Q(movement_type="initial_entry")
                ),
                name="stock_movement_purchase_item_only_initial",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_movement_type_display()} - "
            f"{self.item.name} - {self.quantity} {self.item.get_unit_display()}"
        )

    @property
    def is_cancelled(self):
        return self.cancelled_at is not None

    def get_absolute_url(self):
        return reverse("inventory:movement_detail", kwargs={"pk": self.pk})
