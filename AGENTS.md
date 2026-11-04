# AGENTS.md

Permanent, repo-specific instructions for SiteLedger Operations Management. Read this before changing code.

## Project

- Internal Django application for a small civil construction and real-estate company.
- Manages projects, suppliers, purchases, a shared item catalogue, logical locations and an append-only stock movement history.
- UI in European Portuguese; code, comments, tests and documentation in English. Time zone: `Europe/Lisbon`.
- Fixed internal user base. No public registration or self-service account creation.

## Stack and architecture

- Django 5.2.18 monolith, server-rendered with Django Templates.
- Python 3.15.2 is intentional. Django 5.2 officially supports up to Python 3.14; do not change Python or Django versions without approval.
- SQLite for local development, PostgreSQL in production (`DJANGO_DB_ENGINE`).
- HTMX 2.0.11 is vendored at `static/vendor/htmx.min.js`; never use a CDN.
- Vanilla JavaScript lives in `static/js/app.js`; styling lives in `static/css/app.css`.
- No SPA, React/Vue, frontend framework, frontend build pipeline or REST API for the application UI.
- No Docker, external services or hosting changes without approval.
- All business logic, validation, authentication and authorisation stay on the server.

Apps:

- `projects`: `Project`.
- `purchases`: `Supplier`, `Purchase`, `PurchaseItem`.
- `inventory`: `Item`, `Location`, `StockMovement` and movement domain services.
- `config`: settings, root URLs, global search view and authentication URL wiring.

Key paths:

- `inventory/services.py`: authoritative quantity-changing domain operations.
- `config/views.py`: global search.
- `templates/base.html`, `templates/registration/login.html`, `templates/search/`, `templates/partials/`.
- `inventory/management/commands/seed_demo.py`: development/demo data.
- `docs/siteledger-data-model-specification.md`: domain model.
- `docs/commit-conventions.md`: commit format.

In application code, all quantity-changing writes must use `inventory/services.py`. Do not create or update `StockMovement` directly in views, admin, commands or templates.

## Business rules

- A purchase has a supplier, date, independent total and optional notes; it must contain at least one line.
- Purchase totals are independent from line subtotals. Line subtotals are shown only when a unit price exists.
- Purchase lines snapshot description and unit; the catalogue item and unit price are optional. Unit conversion is out of scope.
- Items have one reference unit. The catalogue is shared by materials, equipment and reusable materials.
- One logical warehouse exists; each project has exactly one project location, created through the domain service.
- A purchase may be saved partially or entirely unallocated. Allocation creates an `INITIAL_ENTRY` linked to the purchase line.
- Active allocation cannot exceed the purchase line quantity. A line quantity cannot be reduced below its active allocation.
- Purchase lines with movements cannot be deleted.
- Movement types: `INITIAL_ENTRY`, `TRANSFER`, `ADJUSTMENT_IN`, `ADJUSTMENT_OUT`. Quantities are always positive.
- Transfers require two different locations. Adjustments require a mandatory justification.
- Movement item and unit must match the linked purchase line when one exists. Allocation requires a catalogue item and matching unit.
- Movement history is append-only. Corrections use full cancellation and a replacement movement.
- Cancellation records user, timestamp and reason. Cancelled movements remain visible but are excluded from balances.
- Transfers and negative adjustments cannot make a source balance negative; cancellation cannot make an affected balance negative.
- Balances are derived from active movements and are recorded/theoretical, never confirmed physical stock.
- Purchase totals are never presented as project expenses.
- Archived projects block incoming movements but allow outgoing movements. Completed projects are not automatically archived.
- Inactive items, suppliers and locations remain in history but are not offered for new operations.
- Do not add stock counts, consumption calculations, purchase requests, requisitions, approvals, serial/lot tracking or reports that imply known physical stock.
- Do not add delete endpoints for domain records. Use cancellation, deactivation or archiving.
- Do not add functional models or apps without an explicit request.

## Authentication and permissions

- Use Django `LoginView` and `LogoutView`: `/login/` and POST-only `/logout/`.
- Settings: `LOGIN_URL = "login"`, `LOGIN_REDIRECT_URL = "projects:list"`, `LOGOUT_REDIRECT_URL = "login"`.
- No self-registration. Administrators create and manage users and recover passwords via Django Admin.
- `LoginRequiredMiddleware` applies by default; `/admin/login/` remains accessible.
- Permissions follow `view_/add_/change_<model>`. Allocation requires `change_purchase` and `view_location`; cancellation requires `change_stockmovement`; adjustments use `add_stockmovement` with a mandatory reason.
- Django Admin registers only `Project` from the domain models. Supplier, purchase, purchase-line, item, location and movement models stay unregistered.
- Admin rules: no project deletion, no `archived_at` editing, archived projects read-only, timestamps read-only.
- Check permissions server-side and never trust client-supplied IDs, prices, quantities or permissions.
- Do not disable authentication, CSRF or permission checks to make tests pass.
- Keep production HTTPS, secure cookie and HSTS settings intact.

## Frontend and HTMX

- The base template has authenticated and anonymous shells. The login page must not show application navigation, search or operational actions.
- Mobile-first CSS. Keep touch targets usable and provide visible focus states and appropriate `aria-*` attributes.
- JavaScript is presentation-only. Do not put business validation, authorisation or data rules in the client.
- Core forms, links and read-only workflows must remain usable without JavaScript.
- Guided forms are progressive enhancement. The server remains authoritative and returns `wizard_initial_step` when errors belong to a later step.
- HTMX returns HTML partials, not JSON. Read endpoints use GET; writes use POST with CSRF.
- Check authentication and permissions on every HTMX endpoint.
- Global search is GET-only, permission-filtered, grouped HTML and has a full-page fallback. It lives in `config/views.py`.
- The purchase item row endpoint is GET-only, authenticated, permission-checked, limited to 50 rows and returns one row plus an out-of-band `TOTAL_FORMS` update.
- Any HTMX update requires verifying the official distribution, licence and integrity and recording the change in the documentation.

## Data, concurrency and files

- Use `DecimalField`/`Decimal` for quantities and money; round displayed money with `ROUND_HALF_UP`.
- Use database constraints for simple invariants and form/service validation for user-facing errors.
- Balance checks and movement creation must occur in the same `transaction.atomic()` and use `select_for_update()` on items, locations, purchase lines and movements.
- SQLite does not provide PostgreSQL-equivalent row locking. Verify concurrency behaviour against PostgreSQL before production.
- Use Django migrations. Do not edit the database manually to bypass migrations.
- `media/` is private; do not add public media routes. Upload validation belongs on the server.
- Never commit `.env`, `.venv/`, `db.sqlite3`, uploads, caches, secrets or credentials.

## Demo data

- `seed_demo` is for development and demo environments only.
- It must be idempotent and use domain services for every stock movement.
- It must never insert `StockMovement` records directly.
- It refuses to run with `DEBUG=False` unless `--force` is used.
- Keep the README and documentation current when its dataset or behaviour changes.

## Commands

```bash
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo
python manage.py seed_demo --user admin
python manage.py seed_demo --force
python manage.py runserver
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
python manage.py test projects
python manage.py test purchases
python manage.py test inventory
python manage.py test tests.test_authentication
python manage.py test tests.test_search
python manage.py test inventory.tests.test_seed_demo
```

Run a single test with a dotted path, for example:

```bash
python manage.py test tests.test_authentication.LoginViewTests.test_login_page_renders
```

## Tests and definition of done

- Use Django's native test runner only; do not add pytest or another test framework without approval.
- Tests live in `<app>/tests/` and in root `tests/`.
- Tests may create movements directly only to exercise model constraints; application flows must still use the domain services.
- Cover authentication, CSRF, permissions, search filtering, HTMX partials, seed idempotency and guided-form error routing.
- For interface changes, manually verify mobile widths, keyboard operation and the no-JavaScript fallback.
- Before completing a task:
  - run `python manage.py check`
  - run `python manage.py test`
  - run `python manage.py makemigrations --check --dry-run` when models or migrations change
  - update documentation when setup, behaviour or workflows change
  - ensure no secrets, database files, uploads or virtual environments are committed
  - consider mobile and no-JavaScript behaviour for UI changes
- The absence of tests in a change must be justified.

## Git and change control

- Follow `docs/commit-conventions.md` for commit messages.
- Commit only after the checks and tests in this file pass.
- Do not commit, push, rewrite history, force-push or delete branches without explicit request.
- Inspect the existing state before changing files.
- Do not delete files or overwrite configuration without authorisation.
- Do not change the defined architecture, versions or dependencies without justification and approval.
- Keep `.gitignore` current.

## References

- `README.md`: setup, routes and operating notes.
- `docs/siteledger-data-model-specification.md`: domain specification.
- `docs/commit-conventions.md`: commit conventions.
