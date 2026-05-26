"""URL patterns for the schedule app."""

from django.urls import path

from common.drf import build_crud_views
from schedule.views import ScheduleViewSet
from schedule.views_tc import (TCSessionCreateView, TCSessionDeleteView,
                               TCSessionListView, TCSessionSwapView)

schedule_list, schedule_detail = build_crud_views(ScheduleViewSet)
schedule_generate = ScheduleViewSet.as_view({"post": "generate"})
schedule_generate_status = ScheduleViewSet.as_view({"get": "generate_status"})
schedule_analyze = ScheduleViewSet.as_view({"post": "analyze"})
schedule_saved = ScheduleViewSet.as_view({"get": "saved"})
schedule_saved_summary = ScheduleViewSet.as_view({"get": "saved_summary"})
schedule_saved_detail = ScheduleViewSet.as_view({"get": "saved_detail"})
schedule_delete_saved_timetable = ScheduleViewSet.as_view(
    {"post": "delete_saved_timetable"}
)
schedule_rename_saved_timetable = ScheduleViewSet.as_view(
    {"post": "rename_saved_timetable"}
)
schedule_save_generated = ScheduleViewSet.as_view({"post": "save_generated"})
schedule_move = ScheduleViewSet.as_view({"post": "move"})
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
    path(
        "schedules/rename-saved-timetable/",
        schedule_rename_saved_timetable,
        name="schedule-rename-saved-timetable",
    ),
    path("schedules/export/", schedule_export, name="schedule-export"),
    path("schedules/generate/", schedule_generate, name="schedule-generate"),
    path(
        "schedules/generate/status/<uuid:job_id>/",
        schedule_generate_status,
        name="schedule-generate-status",
    ),
    path("schedules/analyze/", schedule_analyze, name="schedule-analyze"),
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
    path("schedules/<int:pk>/", schedule_detail, name="schedule-detail"),
    path("tc-sessions/", TCSessionListView.as_view(), name="tc-session-list"),
    path(
        "tc-sessions/create/", TCSessionCreateView.as_view(), name="tc-session-create"
    ),
    path("tc-sessions/swap/", TCSessionSwapView.as_view(), name="tc-session-swap"),
    path(
        "tc-sessions/<int:pk>/", TCSessionDeleteView.as_view(), name="tc-session-delete"
    ),
]
