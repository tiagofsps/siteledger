from django.test import TestCase
from django.urls import reverse

from projects.tests.base import create_user


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = create_user("login-user")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "registration/login.html")
        self.assertContains(response, "Entrar")
        self.assertContains(response, 'name="username"')
        self.assertContains(response, 'name="password"')
        self.assertNotContains(response, ">Obras</a>")

    def test_login_page_preserves_next(self):
        response = self.client.get(reverse("login"), {"next": "/projects/"})

        self.assertContains(response, 'name="next" value="/projects/"')

    def test_authenticated_user_is_redirected_away_from_login(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("projects:list"))

    def test_login_redirects_to_next(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "login-user",
                "password": "test-pass-123",
                "next": "/projects/",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/projects/")
        self.assertEqual(
            int(self.client.session["_auth_user_id"]),
            self.user.pk,
        )

    def test_login_uses_default_redirect(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "login-user",
                "password": "test-pass-123",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("projects:list"))

    def test_invalid_login_shows_error(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "login-user",
                "password": "wrong-password",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_inactive_user_cannot_log_in(self):
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])

        response = self.client.post(
            reverse("login"),
            {
                "username": "login-user",
                "password": "test-pass-123",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].non_field_errors())
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_login_rejects_external_next(self):
        response = self.client.post(
            reverse("login"),
            {
                "username": "login-user",
                "password": "test-pass-123",
                "next": "https://example.com/",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("projects:list"))

    def test_login_requires_csrf(self):
        client = self.client_class(enforce_csrf_checks=True)

        response = client.post(
            reverse("login"),
            {
                "username": "login-user",
                "password": "test-pass-123",
            },
        )

        self.assertEqual(response.status_code, 403)

    def test_protected_page_redirects_to_login(self):
        response = self.client.get(reverse("projects:list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])
        self.assertIn("next=", response["Location"])


class LogoutViewTests(TestCase):
    def setUp(self):
        self.user = create_user("logout-user")
        self.client.force_login(self.user)

    def test_logout_requires_post(self):
        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)

    def test_logout_clears_session_and_redirects(self):
        response = self.client.post(reverse("logout"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_requires_csrf(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.post(reverse("logout"))

        self.assertEqual(response.status_code, 403)
