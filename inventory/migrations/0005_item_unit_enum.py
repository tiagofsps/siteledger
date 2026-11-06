from django.db import migrations, models

ALIASES = {
    "un": "un",
    "unidade": "un",
    "unidades": "un",
    "unid": "un",
    "cx": "cx",
    "caixa": "cx",
    "caixas": "cx",
    "sc": "sc",
    "saco": "sc",
    "sacos": "sc",
    "pl": "pl",
    "palete": "pl",
    "paletes": "pl",
    "rl": "rl",
    "rolo": "rl",
    "rolos": "rl",
    "pct": "pct",
    "pacote": "pct",
    "pacotes": "pct",
    "md": "md",
    "modulo": "md",
    "módulo": "md",
    "módulos": "md",
    "m": "m",
    "metro": "m",
    "metros": "m",
    "m2": "m2",
    "m²": "m2",
    "m3": "m3",
    "m³": "m3",
    "kg": "kg",
    "kgs": "kg",
    "quilograma": "kg",
    "quilogramas": "kg",
    "t": "t",
    "ton": "t",
    "tonelada": "t",
    "toneladas": "t",
    "l": "l",
    "lt": "l",
    "litro": "l",
    "litros": "l",
    "lata": "l",
    "latas": "l",
}


def map_unit(value):
    text = (value or "").strip().casefold()
    if text in ALIASES:
        return ALIASES[text]
    if text.endswith("s") and text[:-1] in ALIASES:
        return ALIASES[text[:-1]]
    print(f"WARNING: unmapped unit {value!r} converted to 'un'")
    return "un"


def forwards(apps, schema_editor):
    Item = apps.get_model("inventory", "Item")
    for item in Item.objects.all().iterator():
        mapped = map_unit(item.unit)
        if mapped != item.unit:
            Item.objects.filter(pk=item.pk).update(unit=mapped)


class Migration(migrations.Migration):
    dependencies = [
        (
            "inventory",
            "0004_stockmovement_stock_movement_purchase_item_only_initial",
        ),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="item",
            name="unit",
            field=models.CharField(
                choices=[
                    ("un", "un"),
                    ("cx", "caixa"),
                    ("sc", "saco"),
                    ("pl", "palete"),
                    ("rl", "rolo"),
                    ("pct", "pacote"),
                    ("md", "módulo"),
                    ("m", "m"),
                    ("m2", "m²"),
                    ("m3", "m³"),
                    ("kg", "kg"),
                    ("t", "t"),
                    ("l", "l"),
                ],
                max_length=8,
                verbose_name="unidade de referência",
            ),
        ),
        migrations.AddConstraint(
            model_name="item",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    unit__in=[
                        "un",
                        "cx",
                        "sc",
                        "pl",
                        "rl",
                        "pct",
                        "md",
                        "m",
                        "m2",
                        "m3",
                        "kg",
                        "t",
                        "l",
                    ]
                ),
                name="item_unit_valid",
            ),
        ),
    ]
