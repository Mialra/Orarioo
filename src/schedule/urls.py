from django.urls import path

from common.drf import build_crud_views
from schedule.views import ScheduleViewSet

schedule_list, schedule_detail = build_crud_views(ScheduleViewSet)
schedule_generate = ScheduleViewSet.as_view({"post": "generate"})
schedule_saved = ScheduleViewSet.as_view({"get": "saved"})
schedule_save_generated = ScheduleViewSet.as_view({"post": "save_generated"})

urlpatterns = [
    path("schedules/", schedule_list, name="schedule-list"),
    path("schedules/saved/", schedule_saved, name="schedule-saved"),
    path("schedules/generate/", schedule_generate, name="schedule-generate"),
    path(
        "schedules/save-generated/",
        schedule_save_generated,
        name="schedule-save-generated",
    ),
    path("schedules/<int:pk>/", schedule_detail, name="schedule-detail"),
]
