# SiteLedger --- Data Model Specification

**Status:** Approved and implemented\
**Scope:** Proposed Django data models and domain rules\
**User interface language:** European Portuguese (PT-PT)\
**Technical notation:** English

------------------------------------------------------------------------

## 1. Purpose

This document describes the proposed data model for SiteLedger's
construction-material and equipment tracking application.

The model is intended to support a small company managing a few active
construction projects and a small number of users. It prioritises quick,
progressive record-keeping over formal procurement, warehouse,
inventory, or approval workflows.

The specification describes the domain and its implemented Django
representation. The previously open business decisions are recorded in
section 14.

## 2. Design principles

-   Use English for all technical notation: model names, fields, enum
    values, methods, constraints, identifiers, comments, and
    documentation.
-   Keep the user interface and user-facing messages in European
    Portuguese.
-   Use one shared `Item` model for materials, equipment, and reusable
    materials.
-   Track quantities by item and location. Do not identify individual
    physical units or serial numbers.
-   Represent the warehouse as a logical location. It does not imply
    that a physical warehouse exists.
-   Keep purchases independent from projects.
-   Represent all quantity changes through an append-only movement
    history.
-   Preserve historical records. Correct mistakes through cancellation
    and replacement movements rather than silently editing completed
    movements.
-   Calculate balances from active movements; do not treat them as
    confirmed physical inventory.
-   Avoid introducing procurement requests, approvals, consumption
    tracking, lot tracking, or complex logistics workflows at this
    stage.

## 3. Proposed model overview

The proposed domain contains the following models:

  Model             Purpose
  ----------------- -----------------------------------------------------
  `Project`         A construction project
  `Supplier`        A shop or supplier
  `Item`            Shared catalogue of materials and equipment
  `Purchase`        A purchase made from a supplier
  `PurchaseItem`    A line in a purchase
  `Location`        The logical location of an item's recorded quantity
  `StockMovement`   A recorded change in quantity between locations

### 3.1. Relationships

-   One `Supplier` can have many `Purchase` records.
-   One `Purchase` contains many `PurchaseItem` records.
-   A `PurchaseItem` may optionally reference an `Item`.
-   One `Project` has exactly one `Location`.
-   One `Item` can have many `StockMovement` records.
-   A `StockMovement` may reference a `PurchaseItem`, or may be
    independent of a purchase.
-   A `StockMovement` has an optional source location and an optional
    destination location, depending on its type.

## 4. Django model proposal

The following code is a proposed representation. Imports are shown where
useful; models may be split across Django applications according to the
final project structure.

### 4.1. Project

The project model is implemented as `Project` in the `projects` app.
The user-facing label remains `Obra`.

``` python
from django.db import models


class Project(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planeada"
        IN_PROGRESS = "in_progress", "Em curso"
        COMPLETED = "completed", "Concluída"

    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300, blank=True)
    description = models.TextField(blank=True)

    start_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )

    archived_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    @property
    def is_archived(self):
        return self.archived_at is not None
```

The existing project lifecycle remains unchanged:

-   `status` describes the project's operational state.
-   `archived_at` independently indicates whether the project is
    archived.
-   A completed project is not automatically archived.
-   Archived projects remain available for historical consultation.
-   The existing archive and unarchive behaviour should be preserved.

### 4.2. Supplier

A supplier represents a shop or other supplier.

``` python
from django.db import models
from django.db.models.functions import Lower


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_supplier_name_ci",
            ),
        ]

    def __str__(self):
        return self.name
```

Rules:

-   Supplier names are unique without regard to letter case.
-   NIF, contact details, and address are out of scope for now.
-   Suppliers with associated purchases must not be deleted.
-   Inactive suppliers remain available in historical purchase records
    but should not be offered for new purchases.

### 4.3. Item

`Item` is the shared catalogue for materials, equipment, and reusable
materials.

``` python
class Item(models.Model):
    class Category(models.TextChoices):
        MATERIAL = "material", "Material"
        EQUIPMENT = "equipment", "Equipamento"
        REUSABLE_MATERIAL = (
            "reusable_material",
            "Material reutilizável",
        )

    name = models.CharField(max_length=200)
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
    )

    unit = models.CharField(max_length=30)
    description = models.TextField(blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.unit})"
```

Examples:

  Name                 Category              Unit
  -------------------- --------------------- --------
  Cement               `MATERIAL`            bag
  Brick                `MATERIAL`            unit
  Concrete mixer       `EQUIPMENT`           unit
  Scaffolding module   `REUSABLE_MATERIAL`   module
  Metal prop           `REUSABLE_MATERIAL`   unit

Rules:

-   Item names are not globally unique. Similar names can exist; the
    user interface should help users find and reuse existing items.
-   Each item has one reference unit.
-   Quantities for the same item must use that reference unit. Unit
    conversion is out of scope.
-   Equipment is tracked by quantity, not by individually identified
    units.
-   Inactive items remain in historical records but should not be
    selectable for new operational records.
-   An item does not have to exist for every purchase line. However, a
    purchase line must reference an item before it can generate stock
    movements.

### 4.4. Purchase

A purchase records a transaction with a supplier. It does not belong
directly to a project.

``` python
class Purchase(models.Model):
    supplier = models.ForeignKey(
        Supplier,
        on_delete=models.PROTECT,
        related_name="purchases",
    )

    purchase_date = models.DateField()

    total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-purchase_date", "-created_at"]

    def __str__(self):
        return f"Purchase #{self.pk} - {self.supplier.name}"
```

Rules:

-   A purchase may contain items intended for several projects and the
    warehouse.
-   A purchase may be saved before all its quantities have been assigned
    to locations.
-   The purchase total is independent of purchase-line subtotals.
-   The purchase total must not be allocated to a project or presented
    as a project's expense.
-   A supplier referenced by a purchase cannot be deleted.

### 4.5. PurchaseItem

A purchase item represents one line in a purchase.

``` python
from decimal import Decimal, ROUND_HALF_UP


class PurchaseItem(models.Model):
    purchase = models.ForeignKey(
        Purchase,
        on_delete=models.PROTECT,
        related_name="items",
    )

    item = models.ForeignKey(
        Item,
        on_delete=models.PROTECT,
        related_name="purchase_items",
        null=True,
        blank=True,
    )

    description = models.CharField(max_length=300)
    unit = models.CharField(max_length=30)

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )

    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gt=0),
                name="purchase_item_quantity_positive",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(unit_price__isnull=True)
                    | models.Q(unit_price__gte=0)
                ),
                name="purchase_item_unit_price_non_negative",
            ),
        ]

    @property
    def subtotal(self):
        if self.unit_price is None:
            return None

        return (self.quantity * self.unit_price).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

    def __str__(self):
        return self.description
```

Rules:

-   `item` is optional to allow free-text purchase lines.
-   A line must reference an `Item` before it can generate stock
    movements.
-   `description` and `unit` preserve what was recorded on the purchase,
    even if the catalogue item is renamed later.
-   One purchase line may generate multiple initial-entry movements to
    different locations.
-   The total quantity of active initial-entry movements linked to a
    purchase line must not exceed the line's purchased quantity.
-   `unit_price` may be unknown (`None`). An unknown price must not be
    treated as zero.
-   A purchase line with associated movements must not be deleted.
-   The subtotal is calculated only when a unit price is known. It does
    not determine or override the purchase total.

### 4.6. Location

A location represents where an item's quantity is recorded.

There are two location types:

-   `WAREHOUSE`: the company's logical warehouse.
-   `PROJECT`: the location associated with a construction project.

``` python
class Location(models.Model):
    class Type(models.TextChoices):
        WAREHOUSE = "warehouse", "Armazém"
        PROJECT = "project", "Obra"

    name = models.CharField(max_length=200)

    location_type = models.CharField(
        max_length=20,
        choices=Type.choices,
    )

    project = models.OneToOneField(
        Project,
        on_delete=models.PROTECT,
        related_name="location",
        null=True,
        blank=True,
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["location_type"],
                condition=models.Q(location_type="warehouse"),
                name="unique_warehouse_location",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        location_type="warehouse",
                        project__isnull=True,
                    )
                    | models.Q(
                        location_type="project",
                        project__isnull=False,
                    )
                ),
                name="location_type_matches_project",
            ),
        ]

    def __str__(self):
        return self.name
```

Rules:

-   There can be at most one warehouse location in the current scope.
-   Each project has exactly one associated project location.
-   A project location remains in the database after its project is
    archived.
-   The warehouse is independent of projects and remains active
    regardless of project status.
-   Creating a project should also ensure that its location exists. This
    should be handled by an explicit domain/service operation or
    project-creation flow, rather than relying solely on Django signals.
-   The model constraints enforce the location type/project
    relationship, but cross-record lifecycle rules require service-layer
    validation.

### 4.7. StockMovement

`StockMovement` is the central model for recording quantity changes.

Every movement represents an initial entry, a transfer, or an
adjustment. A return to the warehouse is an ordinary transfer whose
destination is the warehouse location.

``` python
from django.conf import settings


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
    )

    from_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="outgoing_movements",
        null=True,
        blank=True,
    )

    to_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        related_name="incoming_movements",
        null=True,
        blank=True,
    )

    purchase_item = models.ForeignKey(
        PurchaseItem,
        on_delete=models.PROTECT,
        related_name="movements",
        null=True,
        blank=True,
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
    )

    movement_type = models.CharField(
        max_length=30,
        choices=Type.choices,
    )

    movement_date = models.DateField()

    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_stock_movements",
        null=True,
        blank=True,
    )

    cancelled_at = models.DateTimeField(null=True, blank=True)

    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="cancelled_stock_movements",
        null=True,
        blank=True,
    )

    cancellation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-movement_date", "-created_at"]
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
                    | ~models.Q(
                        from_location=models.F("to_location"),
                    )
                ),
                name="stock_movement_locations_different",
            ),
        ]

    @property
    def is_cancelled(self):
        return self.cancelled_at is not None

    def __str__(self):
        return (
            f"{self.get_movement_type_display()} - "
            f"{self.item.name} - {self.quantity} {self.item.unit}"
        )
```

#### Movement types

  ------------------------------------------------------------------------
  Type               Source            Destination       Purpose
  ------------------ ----------------- ----------------- -----------------
  `INITIAL_ENTRY`    None              Required          Record an initial
                                                         quantity,
                                                         purchased or
                                                         legacy

  `TRANSFER`         Required          Required          Move quantity
                                                         between projects
                                                         and/or warehouse

  `ADJUSTMENT_IN`    None              Required          Audited positive
                                                         quantity
                                                         correction

  `ADJUSTMENT_OUT`   Required          None              Audited negative
                                                         quantity
                                                         correction
  ------------------------------------------------------------------------

Rules:

-   `quantity` is always positive. Direction is represented by source
    and destination.
-   A transfer must have two different locations.
-   An initial entry must have a destination and no source.
-   An initial entry may reference a purchase line or may be a legacy
    entry without purchase information.
-   A transfer must not reference a purchase line.
-   An adjustment must have a justification in `notes` or another
    explicitly required reason field.
-   Adjustments require a mandatory justification and use the existing
    `add_stockmovement` permission. No separate adjustment permission is
    introduced.
-   `movement_date` records the effective date of the movement.
-   `created_at` records when the movement was entered into the
    application.
-   Completed movements must not be freely edited. Corrections should
    use cancellation and a replacement movement.
-   Cancelled movements remain visible in history and are excluded from
    balances.
-   Cancellation must record the user, timestamp, and reason.
-   The model does not track the provenance of individual units after
    transfers.

## 5. Movement and balance rules

### 5.1. Balance calculation

Balances are derived from active movements. A stored balance field is
not proposed.

For a given item and location:

`Balance = Active incoming quantities - Active outgoing quantities`

-   Incoming quantity: active movements where the location is
    `to_location`.
-   Outgoing quantity: active movements where the location is
    `from_location`.
-   Cancelled movements are excluded.
-   The balance is a recorded/theoretical balance, not a physical stock
    count.

Example:

  Movement                          Warehouse   Project A   Project B
  ------------------------------- ----------- ----------- -----------
  Initial entry of 100                   +100           0           0
  Transfer 60 to Project A                -60         +60           0
  Transfer 20 from A to B                   0         -20         +20
  Return 10 from A to warehouse           +10         -10           0
  **Recorded balance**                 **50**      **30**      **20**

### 5.2. Purchase-line allocation limit

For each purchase line:

`Allocated quantity = Sum of active INITIAL_ENTRY movements linked to that purchase line`

The allocated quantity must not exceed the purchase-line quantity.

A purchase line may remain partially or entirely unallocated. This is
intentional and must not prevent the purchase from being saved.

When registering a purchase, users must be able to allocate purchased quantities immediately to one or more locations.

Available destinations include:
- The logical warehouse (WAREHOUSE).
- Any active project location (PROJECT).
Each purchase line may be allocated to a single location or split across multiple locations.

Each allocation creates an INITIAL_ENTRY stock movement linked to the corresponding PurchaseItem.

Allocation is optional at purchase-registration time. A purchase and its purchase lines may be saved with quantities that remain partially or entirely unallocated.

Unallocated quantities can be allocated later through the purchase record.

The total quantity allocated from a purchase line must never exceed its purchased quantity.

### 5.3. Transfer balance validation

A transfer must not make the source location's balance negative.

The balance check and movement creation must occur within the same
database transaction. PostgreSQL concurrency protection must be designed
and tested before production. SQLite development behaviour is not a
substitute for PostgreSQL concurrency testing.

### 5.4. Item consistency

-   The movement item must match the item referenced by its purchase
    line, when a purchase line is present.
-   The purchase-line unit and item reference unit must be compatible
    before movements are created.
-   The same item must not be counted using incompatible units.
-   Unit conversion is out of scope.

## 6. Cancellation and historical integrity

Movements are historical records and should not be deleted.

Proposed cancellation behaviour:

1.  A user requests cancellation and provides a reason.
2.  The system checks whether cancelling the movement would make any
    affected location balance negative.
3.  If the cancellation would create a negative balance because of later
    movements, cancellation is rejected until the dependent movements
    have been corrected.
4.  A permitted cancellation records `cancelled_at`, `cancelled_by`, and
    `cancellation_reason`.
5.  A replacement movement is created when needed.
6. A cancellation is always a full cancellation.

## 7. Project lifecycle and locations

-   A project has one associated project location.
-   A completed project is not automatically archived.
-   A completed project may retain a recorded balance.
-   An archived project and its location remain available for historical
    consultation.
-   New movements involving inactive locations must be rejected.
-   Outgoing transfers from archived projects should instead be allowed so
    that remaining quantities can be returned to the warehouse or moved
    elsewhere.

## 8. Legacy quantities

The application must support quantities that already exist but have no
purchase record.

These are recorded as `INITIAL_ENTRY` movements with:

-   `purchase_item = None`;
-   an item reference;
-   a destination location;
-   a positive quantity;
-   a movement date;
-   explanatory notes identifying the entry as legacy information.

No separate legacy model is required.

## 9. Warehouse returns and transfers

The user interface should offer both:

-   An explicit transfer between two selected locations.
-   A quick **Return to warehouse** action.

Both actions create a `TRANSFER` movement. The quick action is a
user-interface shortcut, not a separate domain movement type.

Transfers can occur:

-   From the warehouse to a project.
-   From one project to another.
-   From a project to the warehouse.

The source location must have sufficient recorded balance.

## 10. Permissions and access control

The application uses Django authentication and permissions, with a
custom login page at `/login/` and POST-only logout at `/logout/`.
There is no public registration; users are created and managed by an
administrator in the Django Admin.

Proposed permission distinctions:

-   View projects, purchases, items, locations, and movement history.
-   Create and update suppliers, purchases, purchase lines, and items.
-   Create initial entries and transfers.
-   Cancel movements.
-   Create quantity adjustments.

Adjustments require a mandatory reason and use the existing
`inventory.add_stockmovement` permission. Cancellation requires
`inventory.change_stockmovement`. No separate adjustment permission is
introduced.

There is no project-specific user assignment or approval workflow in the
current scope. A user with the relevant permission may work with any
active project.

The implemented permission matrix is:

-   `projects.view_project`, `projects.add_project`,
    `projects.change_project`.
-   `purchases.view_supplier`, `purchases.add_supplier`,
    `purchases.change_supplier`.
-   `purchases.view_purchase`, `purchases.add_purchase`,
    `purchases.change_purchase`.
-   `inventory.view_item`, `inventory.add_item`,
    `inventory.change_item`.
-   `inventory.view_location`.
-   `inventory.view_stockmovement`, `inventory.add_stockmovement`,
    `inventory.change_stockmovement`.

Purchase-line allocation requires `purchases.change_purchase` and
`inventory.view_location`.

## 11. Deletion and deactivation

Historical integrity takes priority over deletion.

-   A supplier with purchases must not be deleted.
-   A purchase referenced by purchase lines must not be deleted.
-   A purchase line with movements must not be deleted.
-   An item referenced by movements or purchase lines must not be
    deleted.
-   A location referenced by movements must not be deleted.
-   A project referenced by a location must not be deleted.
-   Use deactivation or archiving where appropriate.
-   Cancelled movements remain in the database.

`on_delete=models.PROTECT` is proposed for historical relationships to
prevent accidental cascade deletion.

## 12. Validation responsibilities

Database constraints should enforce simple row-level invariants,
including:

-   Positive quantities.
-   Non-negative known unit prices.
-   Movement source/destination shape for each movement type.
-   Different source and destination locations.
-   At most one warehouse location.
-   Correct relationship between location type and project.

Domain/service-layer validation is required for cross-record or
transactional rules, including:

-   Transfer does not exceed source balance.
-   Purchase-line allocation does not exceed purchased quantity.
-   Movement item matches purchase-line item.
-   Unit compatibility.
-   Archived/inactive location restrictions.
-   Cancellation impact on later movements.
-   Adjustment permissions and justifications.
-   Concurrency-safe balance checks.

Do not rely exclusively on form validation or model `save()` overrides
for these rules. All write paths must use the same domain operations.

## 13. Explicitly out of scope

The current model does not include:

-   Individual serial-number tracking.
-   Lot or batch traceability after transfers.
-   Physical inventory counts or stocktaking workflows.
-   Automatic consumption or material usage.
-   Waste or breakage tracking as a dedicated process.
-   Purchase requests or approvals.
-   Procurement orders.
-   Delivery scheduling or logistics planning.
-   A physical warehouse-management system.
-   Multiple warehouses.
-   VAT, discounts, shipping, or detailed invoice accounting.
-   Purchase document uploads.
-   Project cost allocation based on the purchase total.
-   Automatic expense reporting for projects.

These may be considered later, but should not be introduced implicitly
into the current model.

## 14. Resolved decisions

1.  **Archived projects:** Incoming movements are blocked. Outgoing
    movements remain allowed so remaining quantities can be returned or
    moved.
2.  **Movement cancellation:** Cancellation is always full and
    all-or-nothing. Corrections use cancellation and a replacement
    movement.
3.  **Completed projects:** They may retain quantities without being
    archived, with no mandatory return to the warehouse.
4.  **Adjustments:** A mandatory justification is required. Adjustments
    use `inventory.add_stockmovement`; no separate permission is
    introduced.
5.  **Unallocated purchases:** A purchase may be saved while some or all
    purchase-line quantities remain unallocated. Quantities can be
    allocated later.

## 15. Implementation notes

The domain is implemented in three Django apps:

-   `projects`: `Project`.
-   `purchases`: `Supplier`, `Purchase`, `PurchaseItem`.
-   `inventory`: `Item`, `Location`, `StockMovement`.

All quantity-changing paths use domain service operations in
`inventory/services.py`. Balance checks and movement creation occur in
the same database transaction. Movement cancellation is full-only and
validates that no affected location balance becomes negative.

The initial inventory migration seeds the logical warehouse. Project
locations are created through the project creation, update and admin
flows.

The permission matrix is defined in section 10. User-facing labels and
messages remain in European Portuguese.

SQLite does not provide PostgreSQL-equivalent row locking. Concurrency
behaviour must be verified against PostgreSQL before production.
