"""Django admin registration for the Schedule and TCSession models."""

from django.contrib import admin

from schedule.models import Schedule, TCSession


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "name",
        "start_time",
        "end_time",
        "teacher",
        "group",
        "subject",
    )
    search_fields = ("name", "observations")
    list_filter = ("teacher", "classroom", "group", "subject")


@admin.register(TCSession)
class TCSessionAdmin(admin.ModelAdmin):
    list_display = ["teacher", "day", "start_time", "end_time", "team"]
    list_filter = ["day", "team"]
    ordering = ["day", "start_time"]
