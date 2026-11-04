from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from .models import Item, Location, StockMovement

ZERO = Decimal("0.000")


def get_warehouse_location():
    location, _ = Location.objects.get_or_create(
        location_type=Location.Type.WAREHOUSE,
        defaults={"name": "Armazém"},
    )
    return location


def ensure_project_location(project):
    location, created = Location.objects.get_or_create(
        project=project,
        defaults={
            "name": project.name,
            "location_type": Location.Type.PROJECT,
        },
    )
    if not created and location.name != project.name:
        location.name = project.name
        location.save(update_fields=["name", "updated_at"])
    return location


def location_balance(item, location):
    incoming = (
        StockMovement.objects.filter(
            item=item,
            to_location=location,
            cancelled_at__isnull=True,
        ).aggregate(total=Sum("quantity"))["total"]
        or ZERO
    )
    outgoing = (
        StockMovement.objects.filter(
            item=item,
            from_location=location,
            cancelled_at__isnull=True,
        ).aggregate(total=Sum("quantity"))["total"]
        or ZERO
    )
    return incoming - outgoing


def get_item_location_balances(item):
    movement_locations = StockMovement.objects.filter(
        item=item,
        cancelled_at__isnull=True,
    ).values_list("to_location_id", "from_location_id")
    ids = set()
    for to_id, from_id in movement_locations:
        if to_id:
            ids.add(to_id)
        if from_id:
            ids.add(from_id)

    balances = []
    for location in Location.objects.filter(pk__in=ids).select_related("project").order_by("name"):
        balances.append(
            {
                "location": location,
                "quantity": location_balance(item, location),
            }
        )
    return balances


def get_project_location_balances(project):
    location = Location.objects.filter(project=project).first()
    if location is None:
        return None, []
    item_ids = (
        StockMovement.objects.filter(
            Q(to_location=location) | Q(from_location=location),
            cancelled_at__isnull=True,
        )
        .values_list("item_id", flat=True)
        .distinct()
    )
    balances = []
    for item in Item.objects.filter(pk__in=item_ids).order_by("name"):
        balances.append(
            {
                "item": item,
                "quantity": location_balance(item, location),
            }
        )
    return location, balances


def _lock_locations(locations):
    pks = sorted({location.pk for location in locations if location and location.pk})
    return {
        location.pk: location
        for location in Location.objects.select_for_update()
        .select_related("project")
        .filter(pk__in=pks)
        .order_by("pk")
    }


def _lock_item(item):
    return Item.objects.select_for_update().get(pk=item.pk)


def _validate_positive(quantity):
    if quantity is None or quantity <= ZERO:
        raise ValidationError("A quantidade tem de ser positiva.")


def _validate_item_active(item):
    if not item.is_active:
        raise ValidationError("O artigo está inativo.")


def _validate_incoming_location(location):
    if not location.is_active:
        raise ValidationError("A localização de destino está inativa.")
    if location.is_project and location.project.is_archived:
        raise ValidationError(
            "Não é possível registar entradas numa obra arquivada."
        )


def _validate_outgoing_location(location):
    if not location.is_active:
        raise ValidationError("A localização de origem está inativa.")


def _validate_purchase_item(purchase_item, item):
    if purchase_item.item_id is None:
        raise ValidationError(
            "O artigo da compra tem de estar associado ao catálogo."
        )
    if purchase_item.item_id != item.pk:
        raise ValidationError(
            "O artigo do movimento tem de coincidir com o artigo da compra."
        )
    if purchase_item.unit.strip().casefold() != item.unit.strip().casefold():
        raise ValidationError(
            "A unidade da compra tem de coincidir com a unidade de referência do artigo."
        )


def _validate_allocation_limit(purchase_item, quantity, *, exclude_movement=None):
    from purchases.services import active_allocated_quantity

    allocated = active_allocated_quantity(
        purchase_item,
        exclude_movement=exclude_movement,
    )
    if allocated + quantity > purchase_item.quantity:
        raise ValidationError(
            "A quantidade alocada excede a quantidade da linha de compra."
        )


def _require_reason(notes):
    if not notes or not notes.strip():
        raise ValidationError("É obrigatório indicar um motivo.")


@transaction.atomic
def create_initial_entry(
    *,
    item,
    to_location,
    quantity,
    movement_date,
    user,
    purchase_item=None,
    notes="",
):
    _validate_positive(quantity)
    item = _lock_item(item)
    locations = _lock_locations([to_location])
    to_location = locations[to_location.pk]

    _validate_item_active(item)
    _validate_incoming_location(to_location)

    if purchase_item is not None:
        from purchases.models import PurchaseItem

        purchase_item = (
            PurchaseItem.objects.select_for_update()
            .select_related("purchase", "item")
            .get(pk=purchase_item.pk)
        )
        _validate_purchase_item(purchase_item, item)
        _validate_allocation_limit(purchase_item, quantity)

    return StockMovement.objects.create(
        item=item,
        to_location=to_location,
        purchase_item=purchase_item,
        quantity=quantity,
        movement_type=StockMovement.Type.INITIAL_ENTRY,
        movement_date=movement_date,
        notes=notes,
        created_by=user,
    )


@transaction.atomic
def allocate_purchase_item(
    *,
    purchase_item,
    location,
    quantity,
    movement_date,
    user,
    notes="",
):
    from purchases.models import PurchaseItem

    purchase_item = PurchaseItem.objects.select_related("purchase", "item").get(
        pk=purchase_item.pk
    )
    if purchase_item.item_id is None:
        raise ValidationError(
            "O artigo da compra tem de estar associado ao catálogo antes de ser alocado."
        )
    return create_initial_entry(
        item=purchase_item.item,
        to_location=location,
        quantity=quantity,
        movement_date=movement_date,
        user=user,
        purchase_item=purchase_item,
        notes=notes,
    )


@transaction.atomic
def create_transfer(
    *,
    item,
    from_location,
    to_location,
    quantity,
    movement_date,
    user,
    notes="",
):
    _validate_positive(quantity)
    item = _lock_item(item)
    locations = _lock_locations([from_location, to_location])
    from_location = locations[from_location.pk]
    to_location = locations[to_location.pk]

    if from_location.pk == to_location.pk:
        raise ValidationError("A origem e o destino têm de ser diferentes.")

    _validate_item_active(item)
    _validate_outgoing_location(from_location)
    _validate_incoming_location(to_location)

    if location_balance(item, from_location) < quantity:
        raise ValidationError(
            "A quantidade transferida excede o saldo registado na origem."
        )

    return StockMovement.objects.create(
        item=item,
        from_location=from_location,
        to_location=to_location,
        quantity=quantity,
        movement_type=StockMovement.Type.TRANSFER,
        movement_date=movement_date,
        notes=notes,
        created_by=user,
    )


@transaction.atomic
def return_to_warehouse(
    *,
    item,
    from_location,
    quantity,
    movement_date,
    user,
    notes="",
):
    return create_transfer(
        item=item,
        from_location=from_location,
        to_location=get_warehouse_location(),
        quantity=quantity,
        movement_date=movement_date,
        user=user,
        notes=notes,
    )


@transaction.atomic
def create_adjustment_in(
    *,
    item,
    to_location,
    quantity,
    movement_date,
    user,
    notes,
):
    _validate_positive(quantity)
    _require_reason(notes)
    item = _lock_item(item)
    locations = _lock_locations([to_location])
    to_location = locations[to_location.pk]

    _validate_item_active(item)
    _validate_incoming_location(to_location)

    return StockMovement.objects.create(
        item=item,
        to_location=to_location,
        quantity=quantity,
        movement_type=StockMovement.Type.ADJUSTMENT_IN,
        movement_date=movement_date,
        notes=notes,
        created_by=user,
    )


@transaction.atomic
def create_adjustment_out(
    *,
    item,
    from_location,
    quantity,
    movement_date,
    user,
    notes,
):
    _validate_positive(quantity)
    _require_reason(notes)
    item = _lock_item(item)
    locations = _lock_locations([from_location])
    from_location = locations[from_location.pk]

    _validate_item_active(item)
    _validate_outgoing_location(from_location)

    if location_balance(item, from_location) < quantity:
        raise ValidationError(
            "A quantidade corrigida excede o saldo registado na localização."
        )

    return StockMovement.objects.create(
        item=item,
        from_location=from_location,
        quantity=quantity,
        movement_type=StockMovement.Type.ADJUSTMENT_OUT,
        movement_date=movement_date,
        notes=notes,
        created_by=user,
    )


@transaction.atomic
def cancel_stock_movement(*, movement, user, reason):
    _require_reason(reason)
    movement = (
        StockMovement.objects.select_for_update()
        .select_related("item", "from_location", "to_location")
        .get(pk=movement.pk)
    )
    if movement.is_cancelled:
        raise ValidationError("O movimento já está cancelado.")

    item = _lock_item(movement.item)
    locations = _lock_locations(
        [
            location
            for location in (movement.from_location, movement.to_location)
            if location is not None
        ]
    )

    if movement.to_location_id is not None:
        destination = locations[movement.to_location_id]
        if location_balance(item, destination) - movement.quantity < ZERO:
            raise ValidationError(
                "O cancelamento deixaria o saldo da localização de destino negativo."
            )

    if movement.purchase_item_id is not None:
        from purchases.models import PurchaseItem

        PurchaseItem.objects.select_for_update().get(pk=movement.purchase_item_id)

    movement.cancelled_at = timezone.now()
    movement.cancelled_by = user
    movement.cancellation_reason = reason
    movement.save(
        update_fields=[
            "cancelled_at",
            "cancelled_by",
            "cancellation_reason",
            "updated_at",
        ]
    )
    return movement
