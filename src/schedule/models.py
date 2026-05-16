"""Schedule model for the Orarioo timetable management system."""

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from auditableEntity.models import AuditableEntity, TeamScopedModel


class TimeSlotMixin(models.Model):
    """Abstract mixin with weekday + time-of-day fields for recurring weekly slots."""

    day = models.SmallIntegerField()  # 0=lunes … 4=viernes
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        abstract = True


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
        on_delete=models.SET_NULL,
        related_name="schedules",
        null=True,
        blank=True,
    )
    group = models.ForeignKey(
        "group.Group",
        on_delete=models.SET_NULL,
        related_name="schedules",
        null=True,
        blank=True,
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
        """Validate and normalise schedule fields before persisting.
        Input: self - Schedule instance with values to validate
        Output: None; raises ValidationError if name is blank or end_time <= start_time
        """
        if not self.name or not self.name.strip():
            raise ValidationError({"name": "name cannot be empty or whitespace only."})
        self.name = self.name.strip()

        if self.observations is not None:
            self.observations = self.observations.strip()

        if self.end_time <= self.start_time:
            raise ValidationError(
                {"end_time": "end_time must be greater than start_time."}
            )

        if not self.classroom_id:
            raise ValidationError({"classroom": "classroom is required."})
        if not self.group_id:
            raise ValidationError({"group": "group is required."})

    def save(self, *args, **kwargs):
        """Run full_clean before saving to enforce model-level validations.
        Input: args, kwargs - standard Model.save arguments
        Output: None; persists the record or raises ValidationError if validation fails
        """
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        """Human-readable representation of the schedule.
        Input: self - Schedule instance
        Output: string in the format 'name: start_time - end_time'
        """
        return f"{self.name}: {self.start_time} - {self.end_time}"


class TCSession(TimeSlotMixin, TeamScopedModel):
    """Duty hour (Trabajo de Centro) for a teacher — available at school but not teaching.

    Independent from Schedule. Never overlaps (teacher, day, start_time) with a Schedule
    or another TCSession for the same teacher.

    observations = ""                    → draft (last generation run, not yet saved)
    observations = "Saved timetable: X"  → frozen with saved timetable "X"
    """

    teacher = models.ForeignKey(
        "teacher.Teacher",
        on_delete=models.CASCADE,
        related_name="tc_sessions",
    )
    name = models.CharField(max_length=120, blank=True, default="")
    observations = models.TextField(blank=True, default="")

    class Meta:
        db_table = "tc_session"
        ordering = ["day", "start_time"]
        indexes = [
            models.Index(fields=["teacher", "day"]),
            models.Index(fields=["team", "day"]),
            models.Index(fields=["team", "observations"]),
        ]

    def __str__(self):
        days = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
        return f"TC {self.teacher} — {days[self.day]} {self.start_time}–{self.end_time}"


class ScheduleGenerationJob(TeamScopedModel):
    """Persistent record of an async schedule generation task.

    Created immediately when a generation request arrives; updated by the
    background thread as it progresses.  The polling endpoint reads this
    table so any Gunicorn worker can serve status queries.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        RUNNING = "RUNNING", "Running"
        DONE = "DONE", "Done"
        ERROR = "ERROR", "Error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="schedule_generation_jobs",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    generation_options = models.JSONField(default=dict)
    result_data = models.JSONField(null=True, blank=True)
    error_data = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "schedule_generation_job"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["team", "created_by", "status"]),
        ]

    def __str__(self):
        return f"GenerationJob {self.id} [{self.status}]"
