from django.contrib import admin

from group.models import Group


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "stage", "created_at", "updated_at")
    search_fields = ("name",)
    list_filter = ("stage",)
