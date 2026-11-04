from django.test import TestCase
from django.urls import reverse

from projects.tests.base import create_user


class HelpViewTests(TestCase):
    def setUp(self):
        self.user = create_user("help-user")

    def test_help_requires_authentication(self):
        response = self.client.get(reverse("help"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_help_renders_complete_workflow(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("help"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "help.html")
        self.assertContains(response, "Como funciona o sistema")
        self.assertContains(response, "Fluxo rápido")
        self.assertContains(response, "Alocação de compras")
        self.assertContains(response, "Movimentos")
        self.assertContains(response, "Saldos registados")
        self.assertContains(response, "Erros comuns")
        self.assertContains(response, "contagem de stock físico confirmada")
