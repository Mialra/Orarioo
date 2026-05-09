"""
Domain models for subjects, including type/stage choices and time-preference states.
"""

from django.core.exceptions import ValidationError
from django.db import models

from auditableEntity.models import AuditableEntity, TeamScopedModel
from common.stages import EducationalStage, canonical_group_stage  # noqa: F401 – EducationalStage kept for backward compat
from namedEntity.models import team_scoped_case_insensitive_name_constraint


class SubjectType(models.TextChoices):
    """Type of subject."""

    NORMAL = "NORMAL", "Normal"
    TC = "TC", "TC"


class SubjectTimePreferenceState(models.TextChoices):
    """Preference state for each weekly slot in subject scheduling."""

    AVAILABLE = "AVAILABLE", "Available"
    PREFER_YES = "PREFER_YES", "Preferably yes"
    PREFER_NO = "PREFER_NO", "Preferably no"
    UNAVAILABLE = "UNAVAILABLE", "Unavailable"


class Subject(TeamScopedModel, AuditableEntity):
    """Subject model representing an academic subject."""

    weekly_hours = models.PositiveIntegerField()
    duration = models.FloatField(default=1.0)
    preferred_time_slot = models.CharField(max_length=150, blank=True)
    time_preferences = models.JSONField(default=dict, blank=True)
    type = models.CharField(
        max_length=20,
        choices=SubjectType.choices,
        default=SubjectType.NORMAL,
    )
    teacher = models.ForeignKey(
        "teacher.Teacher",
        on_delete=models.CASCADE,
        related_name="subjects",
    )
    group = models.ForeignKey(
        "group.Group",
        on_delete=models.CASCADE,
        related_name="subjects",
    )
    mandatory_classroom = models.ForeignKey(
        "classroom.Classroom",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mandatory_subjects",
    )

    class Meta:
        db_table = "subject"
        ordering = ["name", "id"]
        constraints = [
            team_scoped_case_insensitive_name_constraint("subject_team_name_ci_unique")
        ]

    def clean(self):
        """Enforce model-level constraints on duration and weekly_hours.
        Input: self - Subject instance being validated
        Output: None; raises ValidationError if duration or weekly_hours are not positive
        """
        if self.duration <= 0:
            raise ValidationError({"duration": "Duration must be greater than zero."})
        if self.weekly_hours <= 0:
            raise ValidationError(
                {"weekly_hours": "Weekly hours must be greater than zero."}
            )

    def get_stage_display(self):
        group_stage = canonical_group_stage(getattr(self.group, "stage", None), default=None)
        config = getattr(getattr(self, "team", None), "schedule_config", None) or {}
        label = (config.get(group_stage) or {}).get("label")
        return label or group_stage or ""

    def __str__(self):
        group_stage = getattr(self.group, "stage", "")
        return f"{self.name} ({group_stage})"
