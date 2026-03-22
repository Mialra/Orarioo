from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from auditableEntity.models import AuditableEntity


class TeacherTimePreferenceState(models.TextChoices):
    """Preference state for each weekly slot in teacher scheduling."""

    AVAILABLE = "AVAILABLE", "Available"
    PREFER_YES = "PREFER_YES", "Preferably yes"
    PREFER_NO = "PREFER_NO", "Preferably no"
    UNAVAILABLE = "UNAVAILABLE", "Unavailable"


class Teacher(AuditableEntity):
    max_weekly_hours = models.PositiveIntegerField()
    working_hours = models.PositiveIntegerField(default=0)
    time_preferences = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = "teacher"
        ordering = ["name", "id"]
        constraints = [
            UniqueConstraint(
                Lower("name"),
                name="teacher_name_ci_unique",
            )
        ]

    def clean(self):
        if self.working_hours > self.max_weekly_hours:
            raise ValidationError(
                {
                    "working_hours": (
                        "working_hours cannot be greater than max_weekly_hours."
                    )
                }
            )

    def __str__(self):
        return self.name
