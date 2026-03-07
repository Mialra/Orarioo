from django.db import models

from namedEntity.models import NamedEntity


class AuditableEntity(NamedEntity):
    """Base abstract entity with audit fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=150, blank=True)
    updated_by = models.CharField(max_length=150, blank=True)

    class Meta:
        abstract = True
