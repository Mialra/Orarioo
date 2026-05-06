"""
Group domain model scoped to a collaboration team.
"""

from django.db import models

from auditableEntity.models import AuditableEntity, TeamScopedModel
from common.stages import GroupEducationalStage as EducationalStage  # noqa: F401 – kept for backward compat
from namedEntity.models import team_scoped_case_insensitive_name_constraint


class Group(TeamScopedModel, AuditableEntity):
    """Academic group (course) belonging to a team, classified by educational stage."""

    stage = models.CharField(max_length=50)

    class Meta:
        db_table = "group"
        ordering = ["name", "id"]
        constraints = [
            team_scoped_case_insensitive_name_constraint(
                "group_team_name_ci_unique"
            )
        ]

    def __str__(self):
        """Return name and stage label for admin lists and audit logs.
        Input: self - Group instance
        Output: str in the form 'Name (Stage)'
        """
        return f"{self.name} ({self.stage})"
