from django.test import TestCase
from django.urls import reverse

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
