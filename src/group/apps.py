"""
Application configuration for the group app.
"""

from django.apps import AppConfig


class GroupConfig(AppConfig):
    """Register the group app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "group"
