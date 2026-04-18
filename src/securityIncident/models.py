"""
Security incident model for tracking account lockouts and breach events.
"""

from django.conf import settings
from django.db import models


class SecurityIncident(models.Model):
    """Minimal security incident tracker for blocked accounts and breaches."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="security_incidents",
        help_text="User affected by the incident; NULL if user was deleted.",
    )
    created_at = models.DateTimeField(
        auto_now_add=True, help_text="Incident timestamp."
    )
    description = models.TextField(
        help_text="Incident details: reason, scope, action taken."
    )

    class Meta:
        db_table = "security_incident"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["user", "created_at"],
                name="sec_incident_user_created_idx",
            ),
            models.Index(
                fields=["created_at"],
                name="sec_incident_created_idx",
            ),
        ]

    def _user_label(self):
        """Return a short human-readable label identifying the affected user.
        Input: self - SecurityIncident instance
        Output: str 'User <email>' if user exists, or 'Deleted user'
        """
        return f"User {self.user.email}" if self.user else "Deleted user"

    def __str__(self):
        """Return a readable representation for admin lists and logs.
        Input: self - SecurityIncident instance
        Output: str with id, user label, and timestamp
        """
        return f"SecurityIncident {self.id} ({self._user_label()}) - {self.created_at}"
