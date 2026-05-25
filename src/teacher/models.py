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
    max_weekly_minutes = models.PositiveIntegerField(default=0)
    weekly_hours_exact = models.BooleanField(default=False)
    time_preferences = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "teacher"
        ordering = ["name", "id"]
        constraints = [
            team_scoped_case_insensitive_name_constraint("teacher_team_name_ci_unique")
        ]

    def clean(self):
        """Enforce workload field constraints.
        Input: self - Teacher instance being validated
        Output: None; raises ValidationError on constraint violations
        """
        if self.max_weekly_minutes not in (0, 30):
            raise ValidationError({"max_weekly_minutes": "Minutes must be 0 or 30."})
        if self.max_weekly_hours == 0 and self.max_weekly_minutes == 0:
            raise ValidationError(
                {"max_weekly_hours": "Total weekly load cannot be zero."}
            )

    def __str__(self):
        """Return the teacher's name as its string representation.
        Input: self - Teacher instance
        Output: str teacher name
        """
        return self.name
