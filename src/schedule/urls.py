from django.urls import path

from common.drf import build_crud_views
from schedule.views import ScheduleViewSet

schedule_list, schedule_detail = build_crud_views(ScheduleViewSet)
schedule_generate = ScheduleViewSet.as_view({"post": "generate"})
schedule_saved = ScheduleViewSet.as_view({"get": "saved"})
schedule_saved_summary = ScheduleViewSet.as_view({"get": "saved_summary"})
schedule_saved_detail = ScheduleViewSet.as_view({"get": "saved_detail"})
schedule_delete_saved_timetable = ScheduleViewSet.as_view(
    {"post": "delete_saved_timetable"}
)
schedule_save_generated = ScheduleViewSet.as_view({"post": "save_generated"})
schedule_move = ScheduleViewSet.as_view({"post": "move"})
schedule_apply_manual_change = ScheduleViewSet.as_view({"post": "apply_manual_change"})
schedule_export = ScheduleViewSet.as_view({"get": "export"})

urlpatterns = [
    path("schedules/", schedule_list, name="schedule-list"),
    path("schedules/saved/", schedule_saved, name="schedule-saved"),
    path(
        "schedules/saved-summary/",
        schedule_saved_summary,
        name="schedule-saved-summary",
    ),
    path(
        "schedules/saved-detail/",
        schedule_saved_detail,
        name="schedule-saved-detail",
    ),
    path(
        "schedules/delete-saved-timetable/",
        schedule_delete_saved_timetable,
        name="schedule-delete-saved-timetable",
    ),
    path("schedules/export/", schedule_export, name="schedule-export"),
    path("schedules/generate/", schedule_generate, name="schedule-generate"),
    path(
        "schedules/save-generated/",
        schedule_save_generated,
        name="schedule-save-generated",
    ),
    path(
        "schedules/move/",
        schedule_move,
        name="schedule-move",
    ),
    path(
        "schedules/apply-manual-change/",
        schedule_apply_manual_change,
        name="schedule-apply-manual-change",
    ),
    path("schedules/<int:pk>/", schedule_detail, name="schedule-detail"),
]
