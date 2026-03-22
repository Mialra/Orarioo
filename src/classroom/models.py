from django.db import models

from auditableEntity.models import AuditableEntity


class Classroom(AuditableEntity):
    classroom_type = models.CharField(max_length=150, blank=True, default="")

    class Meta:
        db_table = "classroom"
        ordering = ["name", "id"]

    def __str__(self):
        return self.name
