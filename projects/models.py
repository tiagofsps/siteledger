from django.db import models
from django.urls import reverse
from django.utils import timezone


class Project(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planeada"
        IN_PROGRESS = "in_progress", "Em curso"
        COMPLETED = "completed", "Concluída"

    name = models.CharField("nome", max_length=200)
    address = models.CharField("morada", max_length=300, blank=True)
    description = models.TextField("descrição", blank=True)
    start_date = models.DateField("data de início", null=True, blank=True)
    status = models.CharField(
        "estado",
        max_length=20,
        choices=Status.choices,
        default=Status.PLANNED,
    )
    archived_at = models.DateTimeField("arquivada em", null=True, blank=True)
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "obra"
        verbose_name_plural = "obras"

    def __str__(self):
        return self.name

    @property
    def is_archived(self):
        return self.archived_at is not None

    @property
    def display_status(self):
        if self.is_archived:
            return "Arquivada"
        return self.get_status_display()

    def get_absolute_url(self):
        return reverse("projects:detail", kwargs={"pk": self.pk})

    def archive(self):
        if self.archived_at is None:
            self.archived_at = timezone.now()
        self.save(update_fields=["archived_at", "updated_at"])

    def unarchive(self):
        if self.archived_at is not None:
            self.archived_at = None
        self.save(update_fields=["archived_at", "updated_at"])
