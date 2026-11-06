from django.core.exceptions import ValidationError
from django.db import models


class Unit(models.TextChoices):
    UNIT = "un", "un"
    BOX = "cx", "caixa"
    BAG = "sc", "saco"
    PALLET = "pl", "palete"
    ROLL = "rl", "rolo"
    PACK = "pct", "pacote"
    MODULE = "md", "módulo"
    METRE = "m", "m"
    SQUARE_METRE = "m2", "m²"
    CUBIC_METRE = "m3", "m³"
    KILOGRAM = "kg", "kg"
    TONNE = "t", "t"
    LITRE = "l", "l"


# Units counted in whole pieces. Everything else accepts up to three decimals.
DISCRETE_UNITS = frozenset(
    {
        Unit.UNIT,
        Unit.BOX,
        Unit.BAG,
        Unit.PALLET,
        Unit.ROLL,
        Unit.PACK,
        Unit.MODULE,
    }
)

CONTINUOUS_STEP = "0.001"
DISCRETE_STEP = "1"


def is_discrete(unit):
    return unit in DISCRETE_UNITS


def quantity_step(unit):
    return DISCRETE_STEP if is_discrete(unit) else CONTINUOUS_STEP


def validate_quantity(unit, quantity):
    """Reject fractional quantities for piece-counted units."""
    if quantity is None or not is_discrete(unit):
        return
    if quantity != quantity.to_integral_value():
        raise ValidationError(
            "A unidade deste artigo só admite quantidades inteiras."
        )
