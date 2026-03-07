from rest_framework import permissions, viewsets

from schedule.models import Schedule
from schedule.serializers import ScheduleSerializer


class ScheduleViewSet(viewsets.ModelViewSet):
    """CRUD API for schedules."""

    queryset = Schedule.objects.all()
    serializer_class = ScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(created_by=actor, updated_by=actor)

    def perform_update(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(updated_by=actor)
