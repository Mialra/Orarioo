from django.contrib import admin

from subject.models import Subject


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "name",
        "stage",
        "type",
        "teacher",
        "weekly_hours",
        "duration",
        "created_at",
    ]
    list_filter = ["stage", "type", "created_at"]
    search_fields = ["name", "teacher__name"]
    ordering = ["name", "id"]
