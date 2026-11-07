from django.test import TestCase

from projects.models import Project

from .base import create_project


class ProjectModelTests(TestCase):
    def test_display_status_and_archive_lifecycle(self):
        project = create_project(status=Project.Status.IN_PROGRESS)

        self.assertEqual(project.display_status, "Em curso")
        self.assertFalse(project.is_archived)

        project.archive()
        project.refresh_from_db()
        self.assertTrue(project.is_archived)
        self.assertEqual(project.status, Project.Status.IN_PROGRESS)
        self.assertEqual(project.display_status, "Arquivada")

        project.unarchive()
        project.refresh_from_db()
        self.assertFalse(project.is_archived)
        self.assertEqual(project.display_status, "Em curso")

    def test_default_status_is_planned(self):
        project = Project.objects.create(name="Obra")
        self.assertEqual(project.status, Project.Status.PLANNED)

    def test_absolute_url_uses_projects_namespace(self):
        project = create_project()
        self.assertEqual(project.get_absolute_url(), f"/projects/{project.pk}/")

    def test_archive_and_unarchive_are_idempotent(self):
        project = create_project()

        project.archive()
        project.archive()
        self.assertTrue(project.is_archived)

        project.unarchive()
        project.unarchive()
        self.assertFalse(project.is_archived)
