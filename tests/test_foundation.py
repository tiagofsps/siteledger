from django.apps import apps
from django.conf import settings
from django.contrib.auth.models import AnonymousUser, User
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse


class ApplicationRegistryTests(SimpleTestCase):
    def test_business_apps_are_installed(self):
        for app_label in ("projects", "purchases", "inventory"):
            with self.subTest(app_label=app_label):
                self.assertTrue(apps.is_installed(app_label))


class FoundationConfigurationTests(SimpleTestCase):
    def test_shared_directories_are_configured(self):
        self.assertIn(settings.BASE_DIR / "templates", settings.TEMPLATES[0]["DIRS"])
        self.assertIn(settings.BASE_DIR / "static", settings.STATICFILES_DIRS)
        self.assertEqual(settings.STATIC_ROOT, settings.BASE_DIR / "staticfiles")
        self.assertEqual(settings.MEDIA_ROOT, settings.BASE_DIR / "media")

    def test_authentication_is_required_by_default(self):
        self.assertIn(
            "django.contrib.auth.middleware.LoginRequiredMiddleware",
            settings.MIDDLEWARE,
        )
        self.assertEqual(settings.LOGIN_URL, "login")

    def test_security_defaults_are_enabled(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.CSRF_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)

    def test_upload_limits_are_configured(self):
        self.assertGreater(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 0)
        self.assertGreater(settings.FILE_UPLOAD_MAX_MEMORY_SIZE, 0)
        self.assertGreater(settings.DATA_UPLOAD_MAX_NUMBER_FILES, 0)


class BaseTemplateTests(SimpleTestCase):
    def render_base(self, user=None):
        request = RequestFactory().get("/")
        request.user = user or AnonymousUser()
        return render_to_string("base.html", request=request)

    def test_base_template_renders_with_local_htmx(self):
        html = self.render_base()

        self.assertIn("SiteLedger Operations Management", html)
        self.assertIn("/static/vendor/htmx.min.js", html)
        self.assertIn("/static/css/app.css", html)
        self.assertIn("/static/js/app.js", html)

    def test_base_template_contains_mobile_navigation(self):
        html = self.render_base(User(username="tester"))

        self.assertIn('id="nav-toggle"', html)
        self.assertIn('aria-controls="app-nav"', html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('id="app-nav"', html)
        self.assertIn('id="nav-close"', html)
        self.assertIn('id="nav-overlay"', html)
        self.assertIn('id="search-toggle"', html)
        self.assertIn('id="app-search-panel"', html)
        self.assertIn('id="global-search"', html)
        self.assertIn('id="global-search-results"', html)
        self.assertIn('id="theme-toggle"', html)
        self.assertIn('role="switch"', html)
        self.assertIn('class="theme-switch"', html)
        for label in ("Obras", "Compras", "Artigos", "Movimentos"):
            with self.subTest(label=label):
                self.assertIn(f">{label}</a>", html)

    def test_anonymous_base_hides_application_navigation(self):
        html = self.render_base()

        self.assertNotIn('id="nav-toggle"', html)
        self.assertNotIn('id="app-nav"', html)
        self.assertNotIn('id="global-search"', html)
        self.assertIn('id="theme-toggle"', html)
        self.assertIn('role="switch"', html)
        self.assertIn(reverse("login"), html)

    def test_mobile_javascript_asset_is_available(self):
        self.assertIsNotNone(finders.find("js/app.js"))


class AdminAuthenticationTests(TestCase):
    def test_admin_login_remains_accessible_without_authentication(self):
        response = self.client.get(reverse("admin:index"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])
