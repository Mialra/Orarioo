"""
Application configuration for the securityIncident app.
"""

from django.apps import AppConfig


class SecurityIncidentConfig(AppConfig):
    """Register the securityIncident app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "securityIncident"
