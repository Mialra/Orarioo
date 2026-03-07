from django.contrib import admin

from teacher.models import Teacher


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "working_hours", "max_weekly_hours", "created_at")
    search_fields = ("name",)
