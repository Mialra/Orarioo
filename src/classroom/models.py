"""
Classroom domain model scoped to a collaboration team.
"""

from auditableEntity.models import AuditableEntity, TeamScopedModel
from namedEntity.models import team_scoped_case_insensitive_name_constraint


class Classroom(TeamScopedModel, AuditableEntity):
    """Classroom entity used by schedules and subjects."""

    class Meta:
        db_table = "classroom"
        ordering = ["name", "id"]
        constraints = [
            team_scoped_case_insensitive_name_constraint(
                "classroom_team_name_ci_unique"
            ),
        ]

    def __str__(self):
        """Return the classroom name for admin lists and logs."""
        return self.name
