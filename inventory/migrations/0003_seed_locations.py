from django.db import migrations


def seed_locations(apps, schema_editor):
    Location = apps.get_model("inventory", "Location")
    Project = apps.get_model("projects", "Project")

    Location.objects.get_or_create(
        location_type="warehouse",
        defaults={"name": "Armazém"},
    )

    for project in Project.objects.all():
        Location.objects.get_or_create(
            project=project,
            defaults={"name": project.name, "location_type": "project"},
        )


def remove_locations(apps, schema_editor):
    Location = apps.get_model("inventory", "Location")
    Location.objects.filter(location_type="warehouse").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0002_initial"),
        ("projects", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_locations, remove_locations),
    ]
