from datetime import date

from inventory.models import Item
from inventory.services import ensure_project_location, get_warehouse_location
from projects.tests.base import create_project


def create_item(
    *,
    name="Cimento",
    category=Item.Category.MATERIAL,
    unit="sc",
    description="",
    is_active=True,
    **extra,
):
    return Item.objects.create(
        name=name,
        category=category,
        unit=unit,
        description=description,
        is_active=is_active,
        **extra,
    )


def warehouse():
    return get_warehouse_location()


def project_location(project=None):
    if project is None:
        project = create_project(name="Obra de teste")
    return ensure_project_location(project)


def create_initial_entry(
    *,
    item,
    location,
    quantity,
    user=None,
    movement_date=None,
    notes="",
    purchase_item=None,
):
    from inventory.services import create_initial_entry as service

    return service(
        item=item,
        to_location=location,
        quantity=quantity,
        movement_date=movement_date or date(2026, 1, 20),
        user=user,
        notes=notes,
        purchase_item=purchase_item,
    )
