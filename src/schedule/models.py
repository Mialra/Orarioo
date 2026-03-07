from django.core.exceptions import ValidationError
from django.db import models

from auditableEntity.models import AuditableEntity


class Schedule(AuditableEntity):
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

    def clean(self):
        if self.end_time <= self.start_time:
            raise ValidationError(
                {"end_time": "end_time must be greater than start_time."}
            )

    def __str__(self):
        return f"{self.name}: {self.start_time} - {self.end_time}"
