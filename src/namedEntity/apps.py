"""
Application configuration for the namedEntity app.
"""

from django.apps import AppConfig


class NamedEntityConfig(AppConfig):
    """Register the namedEntity app with Django."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "namedEntity"
