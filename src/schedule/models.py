from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from auditableEntity.models import AuditableEntity
from auditableEntity.models import TeamScopedModel


class Schedule(TeamScopedModel, AuditableEntity):
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    observations = models.TextField(blank=True)
    teacher = models.ForeignKey(
        "teacher.Teacher",
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    classroom = models.ForeignKey(
        "classroom.Classroom",
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    group = models.ForeignKey(
        "group.Group",
        on_delete=models.CASCADE,
        related_name="schedules",
    )
    subject = models.ForeignKey(
        "subject.Subject",
        on_delete=models.CASCADE,
        related_name="schedules",
        null=True,
        blank=True,
    )
    users = models.ManyToManyField("user.User", related_name="schedules")

    class Meta:
        db_table = "schedule"
        ordering = ["start_time", "id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(end_time__gt=F("start_time")),
                name="schedule_end_after_start",
            )
        ]

    def clean(self):
        if not self.name or not self.name.strip():
            raise ValidationError({"name": "name cannot be empty or whitespace only."})
        self.name = self.name.strip()

        if self.observations is not None:
            self.observations = self.observations.strip()

        if self.end_time <= self.start_time:
            raise ValidationError(
                {"end_time": "end_time must be greater than start_time."}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name}: {self.start_time} - {self.end_time}"
