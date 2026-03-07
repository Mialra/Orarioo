from django.db import models

from auditableEntity.models import AuditableEntity


class EducationalStage(models.TextChoices):
    PRESCHOOL = "preschool", "Preschool"
    PRIMARY = "primary", "Primary"
    SECONDARY = "secondary", "Secondary"


class Group(AuditableEntity):
    stage = models.CharField(max_length=20, choices=EducationalStage.choices)

    class Meta:
        db_table = "group"
        ordering = ["name", "id"]

    def __str__(self):
        return f"{self.name} ({self.get_stage_display()})"
