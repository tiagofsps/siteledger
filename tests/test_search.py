from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from inventory.tests.base import create_initial_entry, create_item, project_location
from projects.tests.base import create_project, create_user
from purchases.tests.base import (
    create_purchase,
    create_purchase_item,
    create_supplier,
)


SEARCH_PERMISSIONS = (
    "projects.view_project",
    "purchases.view_purchase",
    "purchases.view_supplier",
    "inventory.view_item",
    "inventory.view_stockmovement",
)


class SearchViewTests(TestCase):
    def setUp(self):
        self.user = create_user(
            "searcher",
            permissions=SEARCH_PERMISSIONS,
        )
        self.client.force_login(self.user)
        self.project = create_project(name="Obra Cimento")
        self.supplier = create_supplier(name="Fornecedor Cimento")
        self.item = create_item(name="Cimento")
        self.purchase = create_purchase(
            supplier=self.supplier,
            notes="Compra Cimento",
        )
        self.purchase_item = create_purchase_item(
            purchase=self.purchase,
            item=self.item,
            description=self.item.name,
            unit=self.item.unit,
            quantity=Decimal("5"),
        )
        self.location = project_location(self.project)
        self.movement = create_initial_entry(
            item=self.item,
            location=self.location,
            quantity=Decimal("1"),
            notes="Movimento Cimento",
        )

    def test_search_requires_authentication(self):
        self.client.logout()

        response = self.client.get(reverse("search"), {"q": "Cimento"})

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("login"), response["Location"])

    def test_search_is_get_only(self):
        response = self.client.post(reverse("search"), {"q": "Cimento"})

        self.assertEqual(response.status_code, 405)

    def test_search_finds_across_domains(self):
        response = self.client.get(reverse("search"), {"q": "Cimento"})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "search/search_results.html")
        self.assertContains(response, self.project.get_absolute_url())
        self.assertContains(response, self.purchase.get_absolute_url())
        self.assertContains(response, self.item.get_absolute_url())
        self.assertContains(response, self.movement.get_absolute_url())
        self.assertContains(response, self.supplier.name)

    def test_search_htmx_uses_results_partial(self):
        response = self.client.get(
            reverse("search"),
            {"q": "Cimento"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "search/partials/results.html")

    def test_search_empty_query(self):
        response = self.client.get(reverse("search"), {"q": ""})
        self.assertContains(response, "Introduza um termo de pesquisa")

        response = self.client.get(
            reverse("search"),
            {"q": ""},
            HTTP_HX_REQUEST="true",
        )
        self.assertEqual(response.content, b"")

    def test_search_without_results(self):
        response = self.client.get(reverse("search"), {"q": "sem-resultados"})

        self.assertContains(response, "Sem resultados")

    def test_search_limits_htmx_results(self):
        for index in range(6):
            create_project(name=f"Limite Obra {index}")

        response = self.client.get(
            reverse("search"),
            {"q": "Limite Obra"},
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.content.decode().count("Limite Obra"), 5)

    def test_search_hides_domains_without_permission(self):
        create_project(name="Oculto Obra")
        create_item(name="Oculto Artigo")
        create_supplier(name="Oculto Fornecedor")
        self.client.force_login(
            create_user(
                "project-viewer",
                permissions=("projects.view_project",),
            )
        )

        response = self.client.get(reverse("search"), {"q": "Oculto"})

        self.assertContains(response, "Oculto Obra")
        self.assertNotContains(response, "Oculto Artigo")
        self.assertNotContains(response, "Oculto Fornecedor")
