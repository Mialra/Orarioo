from django.contrib import admin

from schedule.models import Schedule


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
