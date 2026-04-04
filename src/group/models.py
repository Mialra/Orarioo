from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from auditableEntity.models import AuditableEntity
from auditableEntity.models import TeamScopedModel


class EducationalStage(models.TextChoices):
    PRESCHOOL = "preschool", "Preschool"
    PRIMARY = "primary", "Primary"
    SECONDARY = "secondary", "Secondary"


class Group(TeamScopedModel, AuditableEntity):
    stage = models.CharField(max_length=20, choices=EducationalStage.choices)

    class Meta:
        db_table = "group"
        ordering = ["name", "id"]
        constraints = [
            UniqueConstraint(
                Lower("name"),
                name="group_name_ci_unique",
            )
        ]

    def __str__(self):
        return f"{self.name} ({self.get_stage_display()})"
