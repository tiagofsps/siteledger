from django.db import migrations, models
import django.db.models.deletion


def backfill_catalogue_items(apps, schema_editor):
    PurchaseItem = apps.get_model("purchases", "PurchaseItem")
    Item = apps.get_model("inventory", "Item")

    for line in PurchaseItem.objects.filter(item__isnull=True).iterator():
        name = (line.description or "Artigo sem designação").strip()[:200]
        item = Item.objects.create(
            name=name,
            category="material",
            unit=line.unit,
            description="Criado ao associar uma linha de compra existente.",
            is_active=True,
        )
        PurchaseItem.objects.filter(pk=line.pk).update(item=item)


class Migration(migrations.Migration):
    dependencies = [
        ("purchases", "0003_purchase_item_unit_enum"),
    ]

    operations = [
        migrations.RunPython(backfill_catalogue_items, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="purchaseitem",
            name="item",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="purchase_items",
                to="inventory.item",
                verbose_name="artigo do catálogo",
            ),
        ),
    ]
