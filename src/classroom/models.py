from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from auditableEntity.models import AuditableEntity


class Classroom(AuditableEntity):
    classroom_type = models.CharField(max_length=150, blank=True, default="")

    class Meta:
        db_table = "classroom"
        ordering = ["name", "id"]
        constraints = [
            UniqueConstraint(
                Lower("name"),
                name="classroom_name_ci_unique",
            )
        ]

    def __str__(self):
        return self.name
