from auditableEntity.models import AuditableEntity


class Classroom(AuditableEntity):
    class Meta:
        db_table = "classroom"
        ordering = ["name", "id"]

    def __str__(self):
        return self.name
