"""
Audit models and abstract base classes shared by auditable apps.
"""

from django.conf import settings
from django.db import models

from namedEntity.models import NamedEntity


class TeamScopedModel(models.Model):
    """Abstract model that scopes each record to a collaboration team."""

    team = models.ForeignKey(
        "user.CollaborationTeam",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_items",
    )

    class Meta:
        abstract = True


class AuditableEntity(NamedEntity):
    """Base abstract entity with audit fields."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=150, blank=True)
    updated_by = models.CharField(max_length=150, blank=True)

    class Meta:
        abstract = True


class AuditActionType(models.TextChoices):
    """Enumeration of audit operations persisted in AuditEntry rows."""

    CREATE = "CREATE", "Create"
    UPDATE = "UPDATE", "Update"
    DELETE = "DELETE", "Delete"


class AuditEntry(models.Model):
    """Immutable audit log row for a change performed on an auditable entity."""

    team = models.ForeignKey(
        "user.CollaborationTeam",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    entity_type = models.CharField(max_length=50)
    entity_id = models.PositiveBigIntegerField()
    entity_name = models.CharField(max_length=255, blank=True)
    action_type = models.CharField(max_length=10, choices=AuditActionType.choices)
    detail = models.TextField()
    changed_fields = models.JSONField(default=list, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_entries",
    )
    actor_name = models.CharField(max_length=255, blank=True)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "audit_entry"
        ordering = ["-occurred_at", "-id"]
        indexes = [
            models.Index(
                fields=["team", "occurred_at"],
                name="audit_entry_team_oc_f2a670_idx",
            ),
            models.Index(
                fields=["entity_type", "entity_id"],
                name="audit_entry_entity__202b83_idx",
            ),
            models.Index(
                fields=["action_type"],
                name="audit_entry_action__54a4e1_idx",
            ),
            models.Index(
                fields=["actor_name"],
                name="audit_entry_actor_n_5fe643_idx",
            ),
            models.Index(
                fields=["occurred_at"],
                name="audit_entry_occurre_d942b7_idx",
            ),
        ]

    def __str__(self):
        """Return a short readable representation of the audit row."""
        entity_name = self.entity_name or self.entity_type
        return f"{self.action_type} {entity_name} by {self.actor_name or 'unknown'}"
