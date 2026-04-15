"""
Application configuration for audit models and signal registration.
"""

from django.apps import AppConfig


class AuditableEntityConfig(AppConfig):
    """Configure the audit app and connect its signals once Django is ready."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "auditableEntity"

    def ready(self):
        """Register audit signal handlers after the app registry is populated."""
        from auditableEntity.signals import register_audit_signals

        register_audit_signals()
