"""
Abstract base model providing a name field shared by all named entities.
"""

from django.db import models
from django.db.models import F, UniqueConstraint
from django.db.models.functions import Lower


class NamedEntity(models.Model):
    """Base abstract entity with an identifier and readable name."""

    name = models.CharField(max_length=150)

    class Meta:
        abstract = True


def team_scoped_case_insensitive_name_constraint(name):
    """Build a team-scoped case-insensitive uniqueness constraint for `name`."""
    return UniqueConstraint(F("team"), Lower("name"), name=name)
