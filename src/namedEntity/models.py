"""
Abstract base model providing a name field shared by all named entities.
"""

from django.db import models


class NamedEntity(models.Model):
    """Base abstract entity with an identifier and readable name."""

    name = models.CharField(max_length=150)

    class Meta:
        abstract = True
