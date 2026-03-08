from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from schedule.algorithm import BasicScheduleGenerator, ScheduleGenerationError
from schedule.models import Schedule
from schedule.serializers import ScheduleSerializer


class ScheduleViewSet(viewsets.ModelViewSet):
    """CRUD API for schedules."""

    queryset = Schedule.objects.all().select_related(
        "teacher", "classroom", "group", "subject"
    )
    serializer_class = ScheduleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(created_by=actor, updated_by=actor)

    def perform_update(self, serializer):
        actor = getattr(self.request.user, "email", "")
        serializer.save(updated_by=actor)

    def generate(self, request):
        actor = getattr(request.user, "email", "")
        try:
            schedules = BasicScheduleGenerator.generate(
                actor_email=actor,
                user=request.user,
            )
        except ScheduleGenerationError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serialized = self.get_serializer(schedules, many=True)
        return Response(
            {
                "detail": "Schedule generated successfully.",
                "schedules": serialized.data,
                "generated_count": len(serialized.data),
            },
            status=status.HTTP_201_CREATED,
        )
