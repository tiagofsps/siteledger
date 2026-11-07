from django.test import TestCase
from django.urls import reverse

from inventory.models import Location
from projects.models import Project

from .base import create_project, create_user


class ProjectViewTests(TestCase):
    def setUp(self):
        self.user = create_user(
            "manager",
            permissions=(
                "projects.view_project",
                "projects.add_project",
                "projects.change_project",
            ),
        )
        self.client.force_login(self.user)

    def test_list_filters_and_paginates(self):
        create_project(name="Obra Ativa")
        create_project(name="Obra Arquivada").archive()

        response = self.client.get(reverse("projects:list"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Obra Ativa")
        self.assertNotContains(response, "Obra Arquivada")

        response = self.client.get(reverse("projects:list"), {"estado": "archived"})
        self.assertContains(response, "Obra Arquivada")

    def test_list_status_all_shows_active_and_archived(self):
        create_project(name="Obra Ativa")
        create_project(name="Obra Arquivada").archive()

        response = self.client.get(reverse("projects:list"), {"estado": "all"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Obra Ativa")
        self.assertContains(response, "Obra Arquivada")

    def test_list_filters_by_valid_status(self):
        create_project(name="Obra Planeada", status=Project.Status.PLANNED)
        create_project(name="Obra Em Curso", status=Project.Status.IN_PROGRESS)

        response = self.client.get(
            reverse("projects:list"),
            {"estado": Project.Status.PLANNED},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Obra Planeada")
        self.assertNotContains(response, "Obra Em Curso")

    def test_list_filters_by_query(self):
        create_project(name="Obra Alpha")
        create_project(name="Obra Beta")

        response = self.client.get(reverse("projects:list"), {"q": "Alpha"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Obra Alpha")
        self.assertNotContains(response, "Obra Beta")

    def test_list_htmx_partial(self):
        create_project(name="Obra Ativa")

        response = self.client.get(
            reverse("projects:list"),
            HTTP_HX_REQUEST="true",
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "projects/partials/project_results.html",
        )

    def test_archive_and_unarchive_confirmation_pages(self):
        project = create_project()
        response = self.client.get(reverse("projects:archive", args=[project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "projects/project_confirm_archive.html",
        )

        project.archive()
        response = self.client.get(reverse("projects:unarchive", args=[project.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "projects/project_confirm_unarchive.html",
        )

    def test_create_project(self):
        response = self.client.post(
            reverse("projects:create"),
            {
                "name": "Obra Nova",
                "address": "Rua Nova",
                "description": "",
                "start_date": "2026-02-01",
                "status": Project.Status.PLANNED,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Project.objects.filter(name="Obra Nova").exists())

    def test_create_project_creates_project_location(self):
        response = self.client.post(
            reverse("projects:create"),
            {
                "name": "Obra com localização",
                "address": "",
                "description": "",
                "start_date": "",
                "status": Project.Status.PLANNED,
            },
        )
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(name="Obra com localização")
        self.assertTrue(
            Location.objects.filter(
                project=project,
                location_type=Location.Type.PROJECT,
            ).exists()
        )

    def test_detail_and_update(self):
        project = create_project(name="Obra Original")
        response = self.client.get(project.get_absolute_url())
        self.assertContains(response, "Obra Original")

        response = self.client.post(
            reverse("projects:update", args=[project.pk]),
            {
                "name": "Obra Editada",
                "address": "",
                "description": "",
                "start_date": "",
                "status": Project.Status.IN_PROGRESS,
            },
        )
        self.assertEqual(response.status_code, 302)
        project.refresh_from_db()
        self.assertEqual(project.name, "Obra Editada")

    def test_archived_project_cannot_be_updated(self):
        project = create_project()
        project.archive()

        response = self.client.get(reverse("projects:update", args=[project.pk]))
        self.assertEqual(response.status_code, 404)

    def test_archive_and_unarchive(self):
        project = create_project()
        response = self.client.post(reverse("projects:archive", args=[project.pk]))
        self.assertEqual(response.status_code, 302)
        project.refresh_from_db()
        self.assertTrue(project.is_archived)

        response = self.client.post(reverse("projects:unarchive", args=[project.pk]))
        self.assertEqual(response.status_code, 302)
        project.refresh_from_db()
        self.assertFalse(project.is_archived)

    def test_permissions_are_required(self):
        self.client.force_login(create_user("viewer"))
        response = self.client.get(reverse("projects:list"))
        self.assertEqual(response.status_code, 403)

        response = self.client.post(
            reverse("projects:create"),
            {
                "name": "Obra",
                "address": "",
                "description": "",
                "start_date": "",
                "status": Project.Status.PLANNED,
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_csrf_is_required_for_state_changes(self):
        client = self.client_class(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.post(
            reverse("projects:create"),
            {
                "name": "Obra",
                "address": "",
                "description": "",
                "start_date": "",
                "status": Project.Status.PLANNED,
            },
        )
        self.assertEqual(response.status_code, 403)
