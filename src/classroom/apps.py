"""
Application configuration for the classroom app.
"""

from django.apps import AppConfig


class ClassroomConfig(AppConfig):
    """Register the classroom app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "classroom"
