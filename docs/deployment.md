# Deployment

How to deploy SiteLedger. The included `render.yaml` is a working blueprint, but
nothing here depends on Render specifically — any host that runs a Python web
process and provides PostgreSQL will do.

## Requirements

- Python 3.14 or newer (Django 5.2 supports up to 3.14; the repository is
  developed on 3.15).
- PostgreSQL 17. SQLite is not suitable: the filesystem is ephemeral and the
  application relies on `select_for_update()` row locking, which SQLite does not
  provide.
- A process manager or platform that runs a WSGI server.

## Environment variables

Required in production:

| Variable | Notes |
| --- | --- |
| `DJANGO_DEBUG` | Must be `False` |
| `DJANGO_SECRET_KEY` | Long random value; the app refuses to start without it when debug is off |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames |
| `DATABASE_URL` | Managed PostgreSQL connection string |
| `DJANGO_TRUST_X_FORWARDED_PROTO` | `True` only behind a trusted proxy that sets the header |

Optional:

| Variable | Notes |
| --- | --- |
| `SITE_NAME`, `SITE_SUBTITLE`, `SITE_EMAIL`, `SITE_LOGO` | Branding; see the README |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | If the app is served from another origin |
| `DJANGO_SECURE_SSL_REDIRECT`, `DJANGO_SESSION_COOKIE_SECURE`, `DJANGO_CSRF_COOKIE_SECURE`, `DJANGO_SECURE_HSTS_SECONDS` | Default to secure values when debug is off |
| `DB_*` variables | Alternative to `DATABASE_URL` when `DJANGO_DB_ENGINE=postgresql` |

## Build and start

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
```

Start the application with a WSGI server, for example:

```bash
gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 60
```

Platforms without a pre-deploy step (Render's free tier, for instance) can run
`migrate` as part of the build command. On platforms with one, keep migrations
there so a failed migration never replaces a working instance.

## Static and media files

- Static files are collected into `staticfiles/` and served by WhiteNoise. The
  manifest storage is enabled only when `DJANGO_DEBUG=False`, so `collectstatic`
  must run in the build step.
- `media/` holds uploaded documents and must never be served publicly. Serve it
  through authenticated views with permission checks; do not map `MEDIA_ROOT` in
  the web server configuration.

## Health check

`/login/` is a cheap endpoint that does not touch the database and is suitable as
a health check path.

## Using the Render blueprint

`render.yaml` defines a web service and a PostgreSQL database. To use it:

1. Fork the repository.
2. In Render, create a new Blueprint and point it at your fork.
3. Render generates `DJANGO_SECRET_KEY` and injects `DATABASE_URL`; set
   `DJANGO_ALLOWED_HOSTS` to your service hostname.
4. The first deploy runs migrations and `collectstatic` automatically.

The blueprint uses free instances, which sleep after inactivity and expire the
database after a period; that is fine for a demo and not for real data. Switch
both resources to paid plans before entering anything that matters.

## Security checklist

- `DJANGO_DEBUG=False` and a real `DJANGO_SECRET_KEY`.
- HTTPS enforced, with `DJANGO_TRUST_X_FORWARDED_PROTO=True` only behind a proxy
  that sets it.
- `DJANGO_ALLOWED_HOSTS` limited to the real hostnames.
- Database backups enabled.
- `media/` private.
- No demo accounts or demo data in a production database.
