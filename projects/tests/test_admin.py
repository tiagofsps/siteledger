from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from inventory.models import Location
from projects.models import Project

from .base import create_project


class ProjectAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="test-pass-123",
        )
        self.client.force_login(self.admin)

    def test_project_is_registered_and_delete_is_disabled(self):
        project = create_project()

        response = self.client.get(
            reverse("admin:projects_project_delete", args=[project.pk])
        )
        self.assertEqual(response.status_code, 403)

    def test_admin_creation_creates_project_location(self):
        response = self.client.post(
            reverse("admin:projects_project_add"),
            {
                "name": "Obra Admin",
                "address": "",
                "description": "",
                "start_date": "",
                "status": Project.Status.PLANNED,
            },
        )
        self.assertEqual(response.status_code, 302)
        project = Project.objects.get(name="Obra Admin")
        self.assertTrue(Location.objects.filter(project=project).exists())

    def test_archived_project_is_read_only(self):
        project = create_project()
        project.archive()

        response = self.client.post(
            reverse("admin:projects_project_change", args=[project.pk]),
            {
                "name": "Nome alterado",
                "address": "",
                "description": "",
                "start_date": "",
                "status": "planned",
            },
        )
        self.assertEqual(response.status_code, 403)
        project.refresh_from_db()
        self.assertEqual(project.name, "Obra de teste")
