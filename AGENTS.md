# AGENTS.md

Permanent instructions for all work on the **Partilha Louca Operations Management** project.

This document takes precedence over generic tooling preferences. Every agent must read it before changing the project.

## 1. Identity and objective

- **Project:** Partilha Louca Operations Management.
- **Directory and repository:** `partilha-louca-operations`.
- **Company:** Partilha Louca, a small civil construction company that also operates as a real-estate agency.
- **Initial objective:** operational management of construction projects, material purchases, item quantities and material movements between locations.
- **Current scope:** the application manages projects, suppliers, purchases, a shared item catalogue, logical locations and an append-only history of stock movements. Quantities are tracked by item and location. Recorded balances are derived from active movements and do not represent confirmed physical stock.
- **Interface language:** European Portuguese.
- **Documentation and code language:** English.
- **Time zone:** `Europe/Lisbon`.

The application must adapt to the company's real, informal way of working. It must not force workers into complex administrative processes.

## 2. Functional scope and business rules

The real workflow is simple and informal:

- Workers buy materials and equipment from different suppliers.
- Purchased quantities may be sent directly to construction projects or kept in the company's logical warehouse.
- Materials and equipment are occasionally transferred between projects and the warehouse.
- A purchase can contain several items.
- The quantity of one item can be split across several locations.
- A transfer is an independent event, separate from a purchase.
- A transfer does not represent a new purchase or a new cost.
- The application records real events.
- Historical records do not necessarily represent the current physical inventory of a project.

### Current data model behaviour

- Purchases are recorded with a supplier, purchase date, independent total and optional notes.
- Purchase items are recorded with a free-text description, free-text unit, positive quantity, optional unit price and an optional catalogue item.
- A purchase must contain at least one item.
- Purchase totals are independent from item subtotals.
- Item subtotals are calculated for display only when a unit price is present.
- The item catalogue is shared by materials, equipment and reusable materials.
- Each item has one reference unit. Unit conversion is out of scope.
- The company has one logical warehouse location. Each project has exactly one project location.
- Every quantity change is represented by a `StockMovement`:
  - `INITIAL_ENTRY`: a purchased or legacy quantity entering a location.
  - `TRANSFER`: a quantity moving between two different locations.
  - `ADJUSTMENT_IN`: an audited positive correction.
  - `ADJUSTMENT_OUT`: an audited negative correction.
- Movement quantities are always positive. Direction is represented by source and destination.
- Balances are calculated from active movements: incoming quantities minus outgoing quantities.
- Balances are recorded/theoretical balances. They are not physical stock counts and must never be presented as confirmed physical inventory.
- Completed movements are not freely edited. Corrections use cancellation and a replacement movement.
- Cancellation is always a full cancellation. Cancelled movements remain in history and are excluded from balances.
- Cancellation records the user, timestamp and reason.
- The active initial-entry quantity linked to a purchase line may never exceed the purchase line's quantity.
- A purchase and its lines may be saved partially or entirely unallocated. Remaining quantities can be allocated later.
- Items with any movement cannot be deleted.
- Purchase item quantities cannot be reduced below their active allocated quantity.
- Archived projects allow outgoing movements so remaining quantities can be returned or moved, but block new incoming movements.
- Completed projects may retain recorded quantities and are not automatically archived.
- Adjustments require a mandatory justification but do not require a separate permission.
- New movements involving inactive items or inactive locations are rejected.
- Inactive items and suppliers remain available in historical records but are not offered for new operational records.

### Explicitly prohibited features without future authorisation

Do not implement, plan as mandatory, or infer:

- Physical inventory counts or stocktaking workflows.
- Estimated stock or confirmed physical inventory.
- Automatic material-consumption calculations.
- Mandatory inventories.
- Material requisitions.
- Formal approvals.
- Bureaucratic workflows.
- Serial-number, lot or batch tracking after transfers.

Do not create fields, calculations, alerts or reports that suggest the system knows the real physical stock of a project. The append-only movement history and the recorded balances derived from it are explicitly permitted and required.

## 3. Required architecture

- Traditional Django monolith, rendered on the server.
- Python 3.15.2 in this phase.
- Django 5.2 LTS, currently 5.2.18.
- Django Templates.
- HTMX served locally.
- PostgreSQL in production.
- SQLite only for local development.
- HTML, CSS and JavaScript only when necessary.
- Git for version control.

### Prohibited

- React, Next.js, Vue or any SPA.
- Microservices.
- Supabase as a backend.
- Direct database access from the browser.
- REST APIs without a justified functional need.
- Business logic, validation, authentication or authorisation in the client.

All business logic, validation, authentication and authorisation run on the Django server. PostgreSQL is never directly accessible from the browser.

### Known compatibility issue

Django 5.2.18 officially supports Python up to 3.14. The project uses Python 3.15.2 by decision of the current phase. `manage.py check` passes, but compatibility is not officially guaranteed. Before production, the Python/Django combination must be reviewed and approved. Do not change Python or Django versions without prior authorisation.

## 4. Technologies and dependencies

Current direct dependencies, pinned in `requirements.txt`:

```text
Django==5.2.18
python-dotenv==1.2.4
psycopg[binary]==3.3.6
```

- Do not add libraries without a justified need.
- Do not change Python or Django versions without justification and authorisation.
- Check Python 3.15 compatibility before installing any package.
- Prefer the standard library and native Django features.
- Do not add Docker, external services or hosting in this phase.
- HTMX is not a Python dependency. It is vendored at `static/vendor/htmx.min.js`, version 2.0.11, 0BSD licence, from the official `htmx.org` npm package.
- Recorded integrity: tarball `htmx.org-2.0.11.tgz` with SHA-512 `sha512-Thx/WtpeOQqSrqBCw/A1cwGJGg4UrVa3+sW0GmrM3p4gJgO89ecH4qtbnyzDDWFvBTqjnIMCgELTNt636dtamA==` and final file with SHA-256 `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717`.
- Any HTMX update requires verification of the official distribution, licence and integrity, and must be recorded in the documentation.

## 5. Directory structure

```text
partilha-louca-operations/
├── config/
├── projects/
├── purchases/
├── inventory/
├── templates/
│   ├── base.html
│   └── partials/
├── static/
│   ├── css/
│   ├── js/
│   └── vendor/
├── media/
├── tests/
├── docs/
├── .venv/
├── .env.example
├── .gitignore
├── AGENTS.md
├── README.md
├── requirements.txt
└── manage.py
```

- `templates/` contains shared templates.
- `templates/partials/` contains reusable fragments, including HTMX fragments.
- `static/` contains CSS, JavaScript and vendored dependencies.
- `media/` contains local development uploads. It is never served publicly.
- `tests/` contains cross-cutting foundation and integration tests.
- `docs/` contains project specifications and decision records.
- Each app may have its own `templates/<app>/` and `static/<app>/` directories when appropriate.

## 6. Django application responsibilities

### `projects`

- Construction-project management and information.
- `Project` model with name, address, optional description, start date, status, `archived_at`, `created_at` and `updated_at`.
- Active statuses: Planned, In progress and Completed.
- The effective "Archived" status is represented by `archived_at`, preserving the previous status.
- Archiving and reactivating are explicit operations with confirmation; they do not delete records.
- Archived project metadata is read-only in the application and the Django Admin.
- The Django Admin does not allow deleting projects or changing `archived_at`.
- A project has exactly one associated project location, created and maintained through an explicit service operation.
- Archived project locations remain available for historical consultation and outgoing movements.
- Does not calculate physical stock or consumption.
- Displays recorded item balances and movement history for a project, without purchase totals as project expenses.

### `purchases`

- Purchases.
- Suppliers.
- Purchase lines.
- Quantities and values.
- Purchase documents, including photographs of invoices and receipts, in a later phase.
- `Supplier` with a case-insensitively unique name and an `is_active` flag.
- `Purchase` with supplier, purchase date, independent total and optional notes.
- `PurchaseItem` with purchase, optional catalogue item, snapshot description, snapshot unit, positive quantity and optional non-negative unit price.
- A purchase line may remain partially or entirely unallocated.
- Allocation is represented by `INITIAL_ENTRY` stock movements linked to the purchase line.
- The active initial-entry quantity linked to a purchase line may never exceed the line quantity.
- Purchase item quantities cannot be reduced below their active allocated quantity.
- Purchase lines with movements cannot be deleted.
- No physical stock, estimated stock, inventory or consumption calculations.

### `inventory`

- Shared catalogue of materials, equipment and reusable materials.
- Logical locations: one warehouse and one location per project.
- Append-only stock movement history.
- Derived recorded balances per item and location.
- `Item` with name, category, reference unit, optional description and `is_active`.
- `Location` with type (`WAREHOUSE` or `PROJECT`), optional one-to-one project, and `is_active`.
- `StockMovement` with item, optional source location, optional destination location, optional purchase line, positive quantity, movement type, movement date, notes, creation user, cancellation fields and timestamps.
- Initial entries, transfers, adjustments, returns to warehouse and purchase-line allocations.
- Transfer validation must not allow the source location's recorded balance to become negative.
- Cancellation validation must not allow any affected location's recorded balance to become negative.
- No physical stock counts, consumption calculations or automatic inventory reconciliation.

Do not create functional models without an explicit request.

## 7. Code conventions

- Follow PEP 8.
- Use 4 spaces, never tabs.
- Class, function and variable names are clear and in English.
- User-facing text is in European Portuguese.
- Documentation, comments and docstrings are in English.
- Keep views small; move reusable logic into services or helper functions when justified.
- Use the Django ORM. Do not write manual SQL without justified need.
- Do not duplicate business rules across views, templates and JavaScript.
- Do not add obvious comments. Use docstrings only when they add context.
- Do not create premature abstractions.
- Do not create REST APIs for the application's own interface. Use Django views and HTMX.
- Keep configuration in a single `config/settings.py` in this phase, without premature environment separation.
- Use `DecimalField` for quantities and money.
- Use `ROUND_HALF_UP` for displayed monetary rounding.
- Use database constraints for invariants where possible and form validation for user-facing errors.
- All quantity-changing write paths must use the same domain service operations. Do not rely exclusively on form validation or model `save()` overrides.
- Do not edit completed movements. Correct mistakes through cancellation and replacement movements.

## 8. Templates and components

- `templates/base.html` is the common interface base.
- App-specific templates belong in `<app>/templates/<app>/`.
- Reusable fragments and HTMX partials belong in `templates/partials/` or `<app>/templates/<app>/partials/`.
- Use `{% extends %}` and `{% block %}` for composition.
- Do not put business logic in templates.
- Do not rely on HTML-only validation.
- Keep HTML semantic and accessible.
- The interface is mobile-first, responsive, simple, modern, professional and fast.
- The objective is to record purchases, allocations and movements with the minimum number of steps.
- Do not develop a complete design without an explicit request.
- Do not present recorded balances as confirmed physical stock.

## 9. HTMX

- HTMX improves the experience; it does not replace the server-rendered architecture.
- The server returns HTML, never JSON, unless a functional need is justified.
- Always validate all data on the server.
- Use CSRF on every state-changing request.
- Include the CSRF token in the form or in `hx-headers` from `{{ csrf_token }}`.
- Do not depend on JavaScript for essential business rules.
- Prefer normal HTML forms with progressive enhancement.
- HTMX fragments must have a single responsibility and clear names.
- Handle loading indicators and error states for asynchronous operations.
- The vendored version is 2.0.11. Do not use a CDN in production.
- Never use `hx-get` or `hx-post` for operations without server-side authentication and permission checks.
- The purchase item row endpoint is GET-only, authenticated, permission-checked and limited to 50 rows.
- The row endpoint returns one form row and an out-of-band `TOTAL_FORMS` update.

## 10. Security

The application is not automatically secure just because it uses Django.

Mandatory rules:

- Authentication is required by default through `LoginRequiredMiddleware`.
- The Django Admin login must remain accessible without authentication.
- Project operations use Django model permissions: `view_project`, `add_project` and `change_project`.
- The Django Admin does not allow deleting projects; `has_delete_permission()` always returns `False`.
- Archived projects are read-only for metadata in the Django Admin; `has_change_permission()` returns `False` for archived projects.
- `archived_at`, `created_at` and `updated_at` are read-only in the Django Admin.
- Supplier operations use `view_supplier`, `add_supplier` and `change_supplier`.
- Purchase operations use `view_purchase`, `add_purchase` and `change_purchase`.
- Item operations use `view_item`, `add_item` and `change_item`.
- Location viewing uses `view_location`.
- Movement operations use `view_stockmovement`, `add_stockmovement` and `change_stockmovement`.
- Purchase-line allocation requires both `change_purchase` and `view_location`.
- Movement cancellation requires `change_stockmovement`.
- Adjustments use `add_stockmovement` and require a mandatory reason.
- There are no deletion endpoints for projects, suppliers, purchases, purchase lines, items, locations or movements.
- Purchase, purchase line, item, location and movement models are not registered in the Django Admin. Supplier management is performed through the application.
- Check permissions on every operation, on the server.
- Filter querysets by user, project or applicable permission.
- Use `get_object_or_404` with already filtered querysets to prevent unauthorised access to records.
- Do not trust IDs, prices, quantities, permissions or file types sent by the client.
- Use CSRF protection on every form and state-changing request.
- In production: `Secure`, `HttpOnly` and `SameSite=Lax` cookies.
- In production: mandatory HTTPS, HSTS and HTTP redirection.
- `SECURE_PROXY_SSL_HEADER` may only be enabled when an explicitly configured trusted proxy exists. Never trust `X-Forwarded-Proto` from the client indiscriminately.
- Secrets only through environment variables. Never in code, Git or logs.
- Do not expose `SECRET_KEY`, database credentials or external-service keys.
- Do not serve `media/` publicly or through predictable URLs.
- User-uploaded documents must be served by an authenticated view with permission checks.
- Validate uploads on the server: size, count, extension, real MIME type and content where applicable.
- Use safe or random file names; never trust the original name.
- Keep upload limits configured in `settings.py`.
- Do not disable security, CSRF, authentication or permission checks to make tests pass.
- Keep dependencies controlled and updated after review.

### Application authentication

- `LOGIN_URL = "login"`.
- `LOGIN_REDIRECT_URL = "projects:list"`.
- `LOGOUT_REDIRECT_URL = "login"`.
- The application login page is `/login/`.
- Logout is POST-only at `/logout/`.
- There is no public registration or self-service account creation.
- Users are created and managed by an administrator in the Django Admin.
- Password recovery is handled by an administrator.
- The Django Admin login remains available at `/admin/login/`.

## 11. Database and files

- Local development: SQLite.
- Production: PostgreSQL.
- Selection through `DJANGO_DB_ENGINE=sqlite|postgresql`.
- Database credentials only through environment variables.
- Use Django migrations for all schema changes.
- Do not edit the database manually to bypass migrations.
- `media/` is private in production.
- Do not add routes that serve `MEDIA_ROOT` directly.
- Invoice and receipt uploads must be treated as private documents.
- Row locking with `select_for_update()` is used for items, locations, purchase lines and stock movements.
- Balance checks and movement creation must occur in the same database transaction.
- SQLite does not provide PostgreSQL-equivalent row locking. Document this limitation and verify concurrency behaviour against PostgreSQL before production.

## 12. Tests

- Use Django's native test runner: `python manage.py test`.
- Do not add pytest or other frameworks without justification and authorisation.
- Use `SimpleTestCase` for configuration and templates without a database.
- Use `TestCase` for views, models, permissions and uploads.
- Project tests are in `projects/tests/` and cover models, forms, views, filters, pagination, permissions, CSRF, templates, the Django Admin and project-location creation.
- Purchase tests are in `purchases/tests/` and cover models, constraints, forms, formsets, services, views, permissions, CSRF, HTMX, allocation integration and the absence of admin registrations.
- Inventory tests are in `inventory/tests/` and cover models, constraints, balances, initial entries, transfers, adjustments, cancellation, locations, permissions, CSRF and views.
- Cross-app integration tests cover purchase allocation, movement history, project archiving and recorded balances.
- Test authentication and authorisation on every sensitive operation.
- Test that a user cannot access records from another user or projects where they lack permission.
- Test upload validation when uploads exist.
- Test CSRF on state-changing requests.
- Do not mask errors or disable checks to obtain green tests.
- Run `python manage.py check` before completing any task.
- When present, also run migrations and deployment checks.
- The absence of tests in a change must be justified.

## 13. Git and changes

- Do not commit, push or create pull requests without an explicit request.
- Do not change remote repositories.
- Do not publish code or credentials.
- Inspect the existing state before changing files.
- Do not delete files without authorisation.
- Do not overwrite configuration without analysing it.
- Do not introduce external services, Docker or hosting without authorisation.
- Do not change the defined architecture.
- Do not make functional decisions on your own initiative.
- Architectural changes require justification, impact, alternatives and prior approval.
- Python, Django or main dependency updates require justification and prior approval.
- Keep `.gitignore` up to date.
- Follow `docs/commit-conventions.md` for commit message format and scope naming.
- Never version `.env`, `.venv/`, `db.sqlite3`, uploads, caches or temporary files.

## 14. Reference commands

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py runserver
python manage.py check
python manage.py test
python manage.py test projects
python manage.py test purchases
python manage.py test inventory
```
