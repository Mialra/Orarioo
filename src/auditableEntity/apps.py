from django.apps import AppConfig


class AuditableEntityConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "auditableEntity"

    def ready(self):
        from auditableEntity.signals import register_audit_signals

        register_audit_signals()
