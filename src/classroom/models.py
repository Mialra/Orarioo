from django.db import models
from django.db.models import UniqueConstraint
from django.db.models.functions import Lower

from auditableEntity.models import AuditableEntity


class Classroom(AuditableEntity):
    is_shared = models.BooleanField(default=True)

    class Meta:
        db_table = "classroom"
        ordering = ["name", "id"]
        constraints = [
            UniqueConstraint(
                Lower("name"),
                name="classroom_name_ci_unique",
            ),
        ]

    def __str__(self):
        return self.name
