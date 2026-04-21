"""
Group domain model scoped to a collaboration team.
"""

from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from auditableEntity.models import AuditableEntity, TeamScopedModel
from common.stages import GroupEducationalStage as EducationalStage


class Group(TeamScopedModel, AuditableEntity):
    """Academic group (course) belonging to a team, classified by educational stage."""

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
        """Return name and stage label for admin lists and audit logs.
        Input: self - Group instance
        Output: str in the form 'Name (Stage label)'
        """
        return f"{self.name} ({self.get_stage_display()})"
