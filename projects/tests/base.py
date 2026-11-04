from datetime import date

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db.models import Q

from projects.models import Project


def create_user(username, *, permissions=(), **extra):
    user = get_user_model().objects.create_user(
        username=username,
        password="test-pass-123",
        **extra,
    )
    if permissions:
        permission_query = Q()
        for permission in permissions:
            app_label, codename = permission.split(".", 1)
            permission_query |= Q(
                content_type__app_label=app_label,
                codename=codename,
            )
        user.user_permissions.add(*Permission.objects.filter(permission_query))
    return user


def create_project(
    *,
    name="Obra de teste",
    address="Rua de teste, 1",
    description="",
    start_date=None,
    status=Project.Status.PLANNED,
    **extra,
):
    return Project.objects.create(
        name=name,
        address=address,
        description=description,
        start_date=start_date if start_date is not None else date(2026, 1, 15),
        status=status,
        **extra,
    )
