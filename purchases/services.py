from decimal import Decimal

from django.db.models import Sum

ZERO_TOTAL = Decimal("0.00")


def active_allocated_quantity(purchase_item, *, exclude_movement=None):
    movements = purchase_item.movements.filter(
        movement_type="initial_entry",
        cancelled_at__isnull=True,
    )
    if exclude_movement is not None and exclude_movement.pk:
        movements = movements.exclude(pk=exclude_movement.pk)
    return movements.aggregate(total=Sum("quantity"))["total"] or Decimal("0.000")


def purchase_item_subtotal(purchase_item):
    """Return a line's rounded subtotal, or zero when it has no unit price."""
    subtotal = purchase_item.subtotal
    if subtotal is None:
        return ZERO_TOTAL
    return subtotal


def calculate_purchase_total(purchase):
    """Sum the rounded subtotals of every line in the purchase."""
    return sum(
        (purchase_item_subtotal(line) for line in purchase.items.all()),
        ZERO_TOTAL,
    )


def recalculate_purchase_total(purchase):
    """Recalculate and persist the purchase total, rounded per line."""
    total = calculate_purchase_total(purchase)
    if purchase.total != total:
        purchase.total = total
        purchase.save(update_fields=["total", "updated_at"])
    return total
