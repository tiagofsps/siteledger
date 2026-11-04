from decimal import Decimal

from django.db.models import Sum


def active_allocated_quantity(purchase_item, *, exclude_movement=None):
    movements = purchase_item.movements.filter(
        movement_type="initial_entry",
        cancelled_at__isnull=True,
    )
    if exclude_movement is not None and exclude_movement.pk:
        movements = movements.exclude(pk=exclude_movement.pk)
    return movements.aggregate(total=Sum("quantity"))["total"] or Decimal("0.000")
