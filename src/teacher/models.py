"""
Domain model for teachers, including time-preference states and hour constraints.
"""

from django.core.exceptions import ValidationError
from django.db import models

from auditableEntity.models import AuditableEntity, TeamScopedModel
from namedEntity.models import team_scoped_case_insensitive_name_constraint


class TeacherTimePreferenceState(models.TextChoices):
    """Preference state for each weekly slot in teacher scheduling."""

    AVAILABLE = "AVAILABLE", "Available"
    PREFER_YES = "PREFER_YES", "Preferably yes"
    PREFER_NO = "PREFER_NO", "Preferably no"
    UNAVAILABLE = "UNAVAILABLE", "Unavailable"


class Teacher(TeamScopedModel, AuditableEntity):
    """Teacher model representing a staff member with scheduling constraints."""

    max_weekly_hours = models.PositiveIntegerField()
    working_hours = models.PositiveIntegerField(default=0)
    time_preferences = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "teacher"
        ordering = ["name", "id"]
        constraints = [
            team_scoped_case_insensitive_name_constraint(
                "teacher_team_name_ci_unique"
            )
        ]

    def clean(self):
        """Enforce that working_hours does not exceed max_weekly_hours.
        Input: self - Teacher instance being validated
        Output: None; raises ValidationError if working_hours > max_weekly_hours
        """
        if self.working_hours > self.max_weekly_hours:
            raise ValidationError(
                {
                    "working_hours": (
                        "working_hours cannot be greater than max_weekly_hours."
                    )
                }
            )

    def __str__(self):
        """Return the teacher's name as its string representation.
        Input: self - Teacher instance
        Output: str teacher name
        """
        return self.name
