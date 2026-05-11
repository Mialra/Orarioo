"""
Group domain model scoped to a collaboration team.
"""

from django.db import models

from auditableEntity.models import AuditableEntity, TeamScopedModel
from common.stages import GroupEducationalStage as EducationalStage
from namedEntity.models import team_scoped_case_insensitive_name_constraint

__all__ = ["EducationalStage", "Group"]


class Group(TeamScopedModel, AuditableEntity):
    """Academic group (course) belonging to a team, classified by educational stage."""

    stage = models.CharField(max_length=50)

    class Meta:
        db_table = "group"
        ordering = ["name", "id"]
        constraints = [
            team_scoped_case_insensitive_name_constraint("group_team_name_ci_unique")
        ]

    def get_stage_display(self):
        config = getattr(getattr(self, "team", None), "schedule_config", None) or {}
        label = (config.get(self.stage) or {}).get("label")
        return label or self.stage

    def __str__(self):
        """Return name and stage label for admin lists and audit logs.
        Input: self - Group instance
        Output: str in the form 'Name (Stage)'
        """
        return f"{self.name} ({self.stage})"
