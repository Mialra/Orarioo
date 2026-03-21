from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from schedule.algorithm import BasicScheduleGenerator, ScheduleGenerationError
from schedule.models import Schedule
from schedule.serializers import ScheduleSerializer
from user.models import User


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

    def saved(self, request):
        auto_observation = "Auto-generated with CP-SAT basic constraints."
        saved_queryset = (
            self.get_queryset()
            .exclude(observations=auto_observation)
            .filter(users=request.user)
            .order_by("start_time", "id")
        )
        serialized = self.get_serializer(saved_queryset, many=True)
        return Response(
            {
                "count": len(serialized.data),
                "results": serialized.data,
            },
            status=status.HTTP_200_OK,
        )

    @staticmethod
    def _parse_int_list(payload, field_name):
        raw_values = payload.get(field_name) or []
        if field_name == "schedule_ids":
            if not isinstance(raw_values, list) or not raw_values:
                return None, Response(
                    {"detail": "schedule_ids must be a non-empty list."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        elif not isinstance(raw_values, list):
            return None, Response(
                {"detail": f"{field_name} must be a list."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            return [int(value) for value in raw_values], None
        except (TypeError, ValueError):
            return None, Response(
                {"detail": f"{field_name} must contain integer values."},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def save_generated(self, request):
        actor = getattr(request.user, "email", "")
        timetable_name = (request.data.get("timetable_name") or "").strip()

        if not timetable_name:
            return Response(
                {"detail": "timetable_name is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        normalized_ids, error_response = self._parse_int_list(
            request.data,
            "schedule_ids",
        )
        if error_response is not None:
            return error_response

        normalized_user_ids, error_response = self._parse_int_list(
            request.data,
            "user_ids",
        )
        if error_response is not None:
            return error_response

        if request.user.id not in normalized_user_ids:
            normalized_user_ids.append(request.user.id)

        target_users = list(User.objects.filter(id__in=set(normalized_user_ids)))
        if len(target_users) != len(set(normalized_user_ids)):
            return Response(
                {"detail": "Some user_ids do not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        auto_observation = "Auto-generated with CP-SAT basic constraints."
        schedules = list(
            Schedule.objects.filter(
                id__in=normalized_ids,
                users=request.user,
                created_by=actor,
                observations=auto_observation,
            )
        )

        if len(schedules) != len(set(normalized_ids)):
            return Response(
                {
                    "detail": (
                        "Some schedules were not found or are not eligible to be saved "
                        "(must belong to current user and be auto-generated)."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        saved_observation = f"Saved timetable: {timetable_name}"
        for schedule in schedules:
            schedule.name = timetable_name
            schedule.observations = saved_observation
            schedule.updated_by = actor
            schedule.save(update_fields=["name", "observations", "updated_by", "updated_at"])
            schedule.users.add(*target_users)

        serialized = self.get_serializer(schedules, many=True)
        return Response(
            {
                "detail": "Generated schedules saved successfully.",
                "saved_count": len(schedules),
                "schedules": serialized.data,
            },
            status=status.HTTP_200_OK,
        )
