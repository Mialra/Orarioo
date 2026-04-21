"""
Application configuration for the subject app.
"""

from django.apps import AppConfig


class SubjectConfig(AppConfig):
    """Register the subject app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "subject"
