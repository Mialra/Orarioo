"""
Django admin registration for subject records.
"""

from django.contrib import admin

from subject.models import Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    """Admin configuration for subject search, filtering, and inspection."""

    list_display = [
        "id",
        "name",
        "type",
        "teacher",
        "weekly_hours",
        "duration",
        "created_at",
    ]
    list_filter = ["type", "created_at"]
    search_fields = ["name", "teacher__name"]
    ordering = ["name", "id"]
