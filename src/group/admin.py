"""
Django admin registration for group records.
"""

from django.contrib import admin

from group.models import Group


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    """Minimal admin configuration for group search, filter, and inspection."""

    list_display = ("id", "name", "stage", "created_at", "updated_at")
    search_fields = ("name",)
    list_filter = ("stage",)
