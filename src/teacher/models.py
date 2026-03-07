from django.core.exceptions import ValidationError
from django.db import models

from auditableEntity.models import AuditableEntity


class Teacher(AuditableEntity):
    max_weekly_hours = models.PositiveIntegerField()
    working_hours = models.PositiveIntegerField(default=0)
    preferences = models.TextField(blank=True)
    availability = models.TextField(blank=True)
    unavailability = models.TextField(blank=True)

    class Meta:
        db_table = "teacher"
        ordering = ["name", "id"]

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
