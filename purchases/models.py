from decimal import ROUND_HALF_UP, Decimal

from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Lower
from django.urls import reverse


class Supplier(models.Model):
    name = models.CharField("nome", max_length=200)
    is_active = models.BooleanField("ativo", default=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "fornecedor"
        verbose_name_plural = "fornecedores"
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_supplier_name_ci",
            ),
        ]

    def __str__(self):
        return self.name


class Purchase(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchases",
        verbose_name="fornecedor",
    )
    purchase_date = models.DateField("data da compra")
    total = models.DecimalField("total", max_digits=12, decimal_places=2)
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["-purchase_date", "-created_at"]
        verbose_name = "compra"
        verbose_name_plural = "compras"
        constraints = [
            models.CheckConstraint(
                condition=Q(total__gte=0),
                name="purchase_total_non_negative",
            ),
        ]

    def __str__(self):
        return f"Compra de {self.purchase_date:%d/%m/%Y} — {self.supplier.name}"

    def get_absolute_url(self):
        return reverse("purchases:purchase_detail", kwargs={"pk": self.pk})


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.PROTECT,
        related_name="items",
        verbose_name="compra",
    )
    item = models.ForeignKey(
        "inventory.Item",
        on_delete=models.PROTECT,
        related_name="purchase_items",
        verbose_name="artigo do catálogo",
        null=True,
        blank=True,
    )
    description = models.CharField("artigo", max_length=300)
    unit = models.CharField("unidade", max_length=30)
    quantity = models.DecimalField("quantidade", max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(
        "preço unitário",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizado em", auto_now=True)

    class Meta:
        ordering = ["pk"]
        verbose_name = "artigo"
        verbose_name_plural = "artigos"
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0),
                name="purchase_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_price__isnull=True) | Q(unit_price__gte=0),
                name="purchase_item_unit_price_non_negative",
            ),
        ]

    def __str__(self):
        return self.description

    @property
    def subtotal(self):
        if self.unit_price is None:
            return None
        return (self.quantity * self.unit_price).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def get_active_allocated_quantity(self):
        return (
            self.movements.filter(
                movement_type="initial_entry",
                cancelled_at__isnull=True,
            ).aggregate(total=Sum("quantity"))["total"]
            or Decimal("0.000")
        )

    @property
    def remaining_quantity(self):
        allocated = getattr(self, "active_allocated", None)
        if allocated is None:
            allocated = self.get_active_allocated_quantity()
        return self.quantity - allocated
