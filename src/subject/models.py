from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from auditableEntity.models import AuditableEntity


class EducationalStage(models.TextChoices):
    """Educational stages for subjects."""

    PRESCHOOL = "PRESCHOOL", "Preschool"
    PRIMARY = "PRIMARY", "Primary"
    SECONDARY = "SECONDARY", "Secondary"


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


class Subject(AuditableEntity):
    """Subject model representing an academic subject."""

    weekly_hours = models.PositiveIntegerField()
    duration = models.FloatField(default=1.0)
    preferred_time_slot = models.CharField(max_length=150, blank=True)
    time_preferences = models.JSONField(default=dict, blank=True)
    stage = models.CharField(
        max_length=20,
        choices=EducationalStage.choices,
        default=EducationalStage.PRIMARY,
    )
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
    allowed_classrooms = models.ManyToManyField(
        "classroom.Classroom",
        blank=True,
        related_name="allowed_subjects",
    )

    class Meta:
        db_table = "subject"
        ordering = ["name", "id"]
        constraints = [
            UniqueConstraint(
                Lower("name"),
                name="subject_name_ci_unique",
            )
        ]

    def clean(self):
        if self.duration <= 0:
            raise ValidationError({"duration": "Duration must be greater than zero."})
        if self.weekly_hours <= 0:
            raise ValidationError(
                {"weekly_hours": "Weekly hours must be greater than zero."}
            )

    def __str__(self):
        return f"{self.name} ({self.stage})"
