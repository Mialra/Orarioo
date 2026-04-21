"""
Application configuration for the teacher app.
"""

from django.apps import AppConfig


class TeacherConfig(AppConfig):
    """Register the teacher app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "teacher"
