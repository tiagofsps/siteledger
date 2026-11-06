from decimal import ROUND_HALF_UP, Decimal

from django.db import migrations

ZERO = Decimal("0.00")


def _line_subtotal(line):
    if line.unit_price is None:
        return None
    return (line.quantity * line.unit_price).quantize(
        Decimal("0.01"),
        rounding=ROUND_HALF_UP,
    )


def recalculate_purchase_totals(apps, schema_editor):
    Purchase = apps.get_model("purchases", "Purchase")
    PurchaseItem = apps.get_model("purchases", "PurchaseItem")

    for purchase in Purchase.objects.all().iterator():
        subtotals = [
            _line_subtotal(line)
            for line in PurchaseItem.objects.filter(purchase=purchase)
        ]
        if not subtotals or any(subtotal is None for subtotal in subtotals):
            continue

        total = sum(subtotals, ZERO)
        if purchase.total != total:
            Purchase.objects.filter(pk=purchase.pk).update(total=total)


class Migration(migrations.Migration):
    dependencies = [
        ("purchases", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            recalculate_purchase_totals,
            migrations.RunPython.noop,
        ),
    ]
