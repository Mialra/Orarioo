"""
Classroom domain model scoped to a collaboration team.
"""

from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from auditableEntity.models import AuditableEntity, TeamScopedModel


class Classroom(TeamScopedModel, AuditableEntity):
    """Classroom entity used by schedules and subjects."""

    is_shared = models.BooleanField(default=True)

    class Meta:
        db_table = "classroom"
        ordering = ["name", "id"]
        constraints = [
            UniqueConstraint(
                Lower("name"),
                name="classroom_name_ci_unique",
            ),
        ]

    def __str__(self):
        """Return the classroom name for admin lists and logs."""
        return self.name
