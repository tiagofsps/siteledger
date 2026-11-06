# Partilha Louca Operations Management

Internal web application for Partilha Louca to manage construction projects, material purchases, a shared item catalogue and recorded material movements between logical locations.

The application manages `Project`, `Supplier`, `Purchase`, `PurchaseItem`, `Item`, `Location` and `StockMovement`.

## Objectives

- Record purchases, purchase lines and their allocation to the warehouse or a project.
- Record transfers, adjustments and returns between locations as independent events.
- Keep an append-only movement history and derive recorded balances from it.
- Fit the company's informal way of working with the minimum number of steps.
- Keep a mobile-first, simple, fast and accessible interface.

Recorded balances are theoretical quantities derived from active movements. They are not physical stock counts and must not be presented as confirmed physical inventory.

## Domain model

- `Project`: construction project with a name, address, optional description, start date, status and archive timestamp.
- `Supplier`: shop or supplier with a case-insensitively unique name and an active flag.
- `Purchase`: supplier, purchase date, independent total and optional notes.
- `PurchaseItem`: purchase line with an optional catalogue item, snapshot description, snapshot unit, positive quantity and optional unit price.
- `Item`: shared catalogue of materials, equipment and reusable materials, with one reference unit.
- `Location`: one logical warehouse and one location per project.
- `StockMovement`: append-only quantity change with an item, optional source and destination locations, optional purchase line, positive quantity, type, date, notes, creation user and cancellation fields.

Movement types:

- `INITIAL_ENTRY`: purchased or legacy quantity entering a location.
- `TRANSFER`: quantity moving between two different locations.
- `ADJUSTMENT_IN`: audited positive correction.
- `ADJUSTMENT_OUT`: audited negative correction.

## Key business rules

- A purchase must contain at least one item.
- Purchase totals are independent from item subtotals.
- Item subtotals are displayed only when a unit price exists and use `ROUND_HALF_UP`.
- A purchase and its lines may be saved partially or entirely unallocated.
- After saving a purchase, quantities can be allocated immediately from the purchase allocation page, or later from the purchase record.
- Each allocation creates an `INITIAL_ENTRY` movement linked to the purchase line.
- Active allocations cannot exceed the purchase line quantity.
- Purchase line quantities cannot be reduced below their active allocated quantity.
- Movement quantities are always positive; direction is represented by source and destination.
- Transfers and negative adjustments cannot make a source location's recorded balance negative.
- Completed movements are not edited. Corrections use full cancellation and a replacement movement.
- Cancelled movements remain in history and are excluded from balances.
- Cancellation records the user, timestamp and reason.
- Adjustments require a mandatory justification but no separate permission.
- Archived projects allow outgoing movements so quantities can be returned or moved, but block new incoming movements.
- Completed projects may retain recorded quantities and are not automatically archived.
- Items, locations, purchases, purchase lines and movements cannot be deleted through the application.
- Inactive items and locations are not offered for new movements.

## Technologies

- Python 3.15.2
- Django 5.2.18
- Django Templates
- HTMX 2.0.11 vendored at `static/vendor/htmx.min.js`
- SQLite in development
- PostgreSQL in production
- HTML, CSS and JavaScript only when necessary

## Prerequisites

- Python 3.15.2 available on the system.
- Git.
- PostgreSQL only for production execution.

> **Compatibility note:** Django 5.2.18 officially supports Python up to 3.14. Local
> development uses Python 3.15.2, which is not officially guaranteed. The production
> deployment therefore runs Python 3.14.10 on Render and in CI. The test suite passes on
> both versions. Keep local and production behaviour aligned when changing dependencies.

## Virtual environment

From the project root:

```bash
python3.15 -m venv .venv
source .venv/bin/activate
```

## Installing dependencies

```bash
pip install -r requirements.txt
```

## Environment configuration

```bash
cp .env.example .env
```

Adjust the local `.env`. The `.env` file must not be versioned and must never contain real credentials in public text.

Main variables:

- `DJANGO_SECRET_KEY`: secret key; required when `DJANGO_DEBUG=False`.
- `DJANGO_DEBUG`: `True` in development, `False` in production.
- `DJANGO_ALLOWED_HOSTS`: comma-separated list.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: trusted origins, comma-separated.
- `DJANGO_DB_ENGINE`: `sqlite` or `postgresql`.
- `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`: PostgreSQL configuration.
- Upload limits: `DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE`, `DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE` and `DJANGO_DATA_UPLOAD_MAX_NUMBER_FILES`.
- Production security: `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SESSION_COOKIE_SECURE`, `DJANGO_CSRF_COOKIE_SECURE`, `DJANGO_SECURE_HSTS_SECONDS` and `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`.
- `DJANGO_TRUST_X_FORWARDED_PROTO`: enable only when an explicitly configured trusted proxy exists.

## Migrations

```bash
python manage.py migrate
```

The initial inventory migration seeds the logical warehouse. Project locations are created through the project creation and update flows.

## Demo data

For local development, populate the database with deterministic demo data:

```bash
python manage.py seed_demo
```

Associate the created movements with an existing user:

```bash
python manage.py seed_demo --user admin
```

The command is idempotent: running it again does not duplicate demo records. It refuses to run when `DJANGO_DEBUG=False` unless `--force` is provided. It is intended for development and demo environments only, not for production data.

To restore a completely clean demo state, delete the local SQLite database and recreate it:

```bash
rm db.sqlite3
python manage.py migrate
python manage.py seed_demo
```

## Starting the server

```bash
python manage.py runserver
```

The application login is available at `/login/`. The Django Admin remains available at `/admin/`.

## Authentication

The application uses Django's built-in authentication views with a custom login page. There is no public registration flow.

- `/login/`: application login.
- `/logout/`: POST-only logout action.

Create the first administrator with:

```bash
python manage.py createsuperuser
```

Create the remaining users in the Django Admin at `/admin/auth/user/add/` and assign only the required permissions or groups. Password recovery is handled by the administrator through the Django Admin.

## Application routes

Authentication:

- `/login/`: application login.
- `/logout/`: POST-only logout.

Help:

- `/ajuda/`: complete workflow guide in European Portuguese.

Search:

- `/search/`: global search across projects, purchases, suppliers, items and movements, with an HTMX dropdown and a full results page.

Projects:

- `/projects/`: project list, search and filters.
- `/projects/new/`: create a project.
- `/projects/<id>/`: project detail with recorded balances and movement history.
- `/projects/<id>/edit/`: edit an active project.
- `/projects/<id>/archive/`: confirm archiving.
- `/projects/<id>/unarchive/`: confirm reactivation.

Purchases and suppliers:

- `/purchases/`: purchase list with search, supplier and project filters.
- `/purchases/new/`: record a purchase and its items.
- `/purchases/<id>/`: purchase detail.
- `/purchases/<id>/edit/`: edit a purchase and its items.
- `/purchases/<id>/allocations/`: allocate remaining quantities across the purchase lines.
- `/purchases/<purchase_id>/items/<item_id>/allocations/`: manage allocations for one purchase line.
- `/purchases/suppliers/`: supplier list.
- `/purchases/suppliers/new/`: create a supplier.
- `/purchases/suppliers/<id>/edit/`: edit a supplier.
- `/purchases/items/row/`: authenticated, permission-checked HTMX endpoint for one purchase-item row, limited to 50 rows.

Inventory:

- `/inventory/items/`: item catalogue.
- `/inventory/items/new/`: create an item.
- `/inventory/items/<id>/`: item detail with recorded balances and movement history.
- `/inventory/items/<id>/edit/`: edit an item.
- `/inventory/locations/`: warehouse and project locations.
- `/inventory/movements/`: movement history with search, item, location and type filters.
- `/inventory/movements/new/`: choose the movement type and start guided recording.
- `/inventory/movements/new/initial/`: record an initial entry.
- `/inventory/movements/new/transfer/`: record a transfer.
- `/inventory/movements/new/return/`: quick return to the warehouse.
- `/inventory/movements/new/adjustment-in/`: record a positive adjustment.
- `/inventory/movements/new/adjustment-out/`: record a negative adjustment.
- `/inventory/movements/<id>/`: movement detail.
- `/inventory/movements/<id>/cancel/`: confirm full cancellation with a reason.

## Permissions

Project operations use `projects.view_project`, `projects.add_project` and `projects.change_project`.

Supplier operations use `purchases.view_supplier`, `purchases.add_supplier` and `purchases.change_supplier`.

Purchase operations use `purchases.view_purchase`, `purchases.add_purchase` and `purchases.change_purchase`.

Item operations use `inventory.view_item`, `inventory.add_item` and `inventory.change_item`.

Location viewing uses `inventory.view_location`.

Movement operations use `inventory.view_stockmovement`, `inventory.add_stockmovement` and `inventory.change_stockmovement`.

Purchase-line allocation requires `purchases.change_purchase` and `inventory.view_location`.

Movement cancellation requires `inventory.change_stockmovement`.

Permissions can be assigned to users or groups in the Django Admin.

## Django Admin

The Django Admin manages `Project` and user/permission administration. It does not allow deleting projects, does not allow changing `archived_at`, and shows archived projects as read-only.

Purchase, purchase line, item, location and movement models are not registered in the Django Admin. Supplier management is performed through the application.

## Concurrency and database limitations

Quantity-changing operations use `transaction.atomic()` and `select_for_update()` on items, locations, purchase lines and movements. Balance checks and movement creation occur in the same transaction.

SQLite does not provide row locking equivalent to PostgreSQL. The concurrency behaviour must be verified against PostgreSQL before production.

## Checks

```bash
python manage.py check
python manage.py test
python manage.py test projects
python manage.py test purchases
python manage.py test inventory
python manage.py makemigrations --check --dry-run
```

Continuous integration runs the same checks on every push to `main` and every pull
request, against PostgreSQL, using Python 3.14.10. See
[`docs/render-deployment.md`](docs/render-deployment.md).

## Commit conventions

Commit messages follow the conventions documented in
[`docs/commit-conventions.md`](docs/commit-conventions.md).

## Application structure

- `config/`: project configuration, URLs, WSGI/ASGI entry points and the cross-cutting search view.
- `projects/`: project model, forms, views, URLs, admin, templates and tests.
- `purchases/`: supplier, purchase and purchase-line models, forms, formsets, services, views, URLs, templates and tests.
- `inventory/`: item, location and stock-movement models, domain services, forms, views, URLs, templates, migrations and tests.
- `templates/`: shared templates; reusable fragments in `templates/partials/`.
- `static/`: CSS, JavaScript and vendored dependencies.
- `media/`: local development uploads, never served publicly.
- `tests/`: cross-cutting foundation and integration tests.

## Production

Render deployment is documented in
[`docs/render-deployment.md`](docs/render-deployment.md).

The current Render environment is a free evaluation deployment: the web service
and database are free instances, the database expires after 30 days and has no
backups. Do not enter real company data until it is upgraded to paid plans.

- Configure `DJANGO_DEBUG=False`, a real `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`.
- Use `DATABASE_URL` for Render PostgreSQL; `DJANGO_DB_ENGINE=postgresql` and the `DB_*` variables remain available as the alternative.
- Ensure HTTPS and the appropriate security headers.
- Keep `media/` private. Documents must be served only by authenticated views with permission checks.
- Do not serve `MEDIA_ROOT` directly from the web server.
- Do not add Docker or other hosting providers without authorisation.
