from django.urls import path

from schedule.views import ScheduleViewSet

schedule_list = ScheduleViewSet.as_view({"get": "list", "post": "create"})
schedule_detail = ScheduleViewSet.as_view(
    {
        "get": "retrieve",
        "put": "update",
        "patch": "partial_update",
        "delete": "destroy",
    }
)

urlpatterns = [
    path("schedules/", schedule_list, name="schedule-list"),
    path("schedules/<int:pk>/", schedule_detail, name="schedule-detail"),
]
