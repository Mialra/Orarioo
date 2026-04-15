"""
Django admin registration for classroom records.
"""

from django.contrib import admin

from classroom.models import Classroom


@admin.register(Classroom)
class ClassroomAdmin(admin.ModelAdmin):
    """Minimal admin configuration for classroom search and inspection."""

    list_display = ("id", "name", "created_at", "updated_at")
    search_fields = ("name",)
