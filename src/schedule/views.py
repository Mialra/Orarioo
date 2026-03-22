import logging
import random

from rest_framework import status
from rest_framework.response import Response

from common.drf import AuditableModelViewSet
from schedule.algorithm import BasicScheduleGenerator, ScheduleGenerationError
from schedule.algorithm.generator import ScheduleReplanner
from schedule.constants import AUTO_GENERATED_OBSERVATION, SAVED_TIMETABLE_PREFIX
from schedule.models import Schedule
from schedule.serializers import ScheduleSerializer
from user.models import User

logger = logging.getLogger(__name__)


class ScheduleViewSet(AuditableModelViewSet):
    """CRUD API for schedules."""

    GENERATION_FAILED_DETAIL = (
        "Unable to generate schedule with the current input constraints."
    )

    queryset = Schedule.objects.all().select_related(
        "teacher", "classroom", "group", "subject"
    )
    serializer_class = ScheduleSerializer

    def generate(self, request):
        actor = getattr(request.user, "email", "")
        raw_seed = request.data.get("seed")
        if raw_seed in (None, ""):
            generation_seed = random.SystemRandom().randrange(1, 2**31 - 1)
        else:
            try:
                generation_seed = int(raw_seed)
            except (TypeError, ValueError):
                return Response(
                    {"detail": "seed must be an integer value."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        try:
            schedules = BasicScheduleGenerator.generate(
                actor_email=actor,
                user=request.user,
                random_seed=generation_seed,
            )
        except ScheduleGenerationError as exc:
            logger.warning(
                "Schedule generation rejected: actor=%s, reason=%s",
                actor,
                exc,
            )
            return Response(
                {
                    "detail": self.GENERATION_FAILED_DETAIL,
                    "error_code": "schedule_generation_failed",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        serialized = self.get_serializer(schedules, many=True)
        return Response(
            {
                "detail": "Schedule generated successfully.",
                "seed": generation_seed,
                "schedules": serialized.data,
                "generated_count": len(serialized.data),
            },
            status=status.HTTP_201_CREATED,
        )

    def saved(self, request):
        saved_queryset = (
            self.get_queryset()
            .exclude(observations=AUTO_GENERATED_OBSERVATION)
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
            normalized_values = [int(value) for value in raw_values]
        except (TypeError, ValueError):
            return None, Response(
                {"detail": f"{field_name} must contain integer values."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if any(value <= 0 for value in normalized_values):
            return None, Response(
                {field_name: f"{field_name} must contain positive integer values."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(set(normalized_values)) != len(normalized_values):
            return None, Response(
                {field_name: f"{field_name} cannot contain duplicated values."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return normalized_values, None

    @staticmethod
    def _ensure_request_user_in_user_ids(request_user_id, normalized_user_ids):
        if request_user_id not in normalized_user_ids:
            normalized_user_ids.append(request_user_id)
        return normalized_user_ids

    @staticmethod
    def _fetch_target_users(normalized_user_ids):
        requested_ids = set(normalized_user_ids)
        target_users = list(User.objects.filter(id__in=requested_ids))
        if len(target_users) != len(requested_ids):
            return None, Response(
                {"detail": "Some user_ids do not exist."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return target_users, None

    @staticmethod
    def _fetch_eligible_schedules(normalized_ids, request_user, actor_email):
        requested_ids = set(normalized_ids)
        schedules = list(
            Schedule.objects.filter(
                id__in=normalized_ids,
                users=request_user,
                created_by=actor_email,
                observations=AUTO_GENERATED_OBSERVATION,
            )
        )
        if len(schedules) != len(requested_ids):
            return None, Response(
                {
                    "detail": (
                        "Some schedules were not found or are not eligible to be saved "
                        "(must belong to current user and be auto-generated)."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return schedules, None

    @staticmethod
    def _persist_saved_schedules(
        *, schedules, timetable_name, actor_email, target_users
    ):
        saved_observation = f"{SAVED_TIMETABLE_PREFIX}: {timetable_name}"
        for schedule in schedules:
            schedule.name = timetable_name
            schedule.observations = saved_observation
            schedule.updated_by = actor_email
            schedule.save(
                update_fields=["name", "observations", "updated_by", "updated_at"]
            )
            schedule.users.add(*target_users)

    def save_generated(self, request):
        actor = getattr(request.user, "email", "")
        timetable_name = (request.data.get("timetable_name") or "").strip()

        if not timetable_name:
            return Response(
                {"timetable_name": "timetable_name is required."},
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

        normalized_user_ids = self._ensure_request_user_in_user_ids(
            request.user.id,
            normalized_user_ids,
        )

        target_users, error_response = self._fetch_target_users(normalized_user_ids)
        if error_response is not None:
            return error_response

        schedules, error_response = self._fetch_eligible_schedules(
            normalized_ids,
            request.user,
            actor,
        )
        if error_response is not None:
            return error_response

        self._persist_saved_schedules(
            schedules=schedules,
            timetable_name=timetable_name,
            actor_email=actor,
            target_users=target_users,
        )

        serialized = self.get_serializer(schedules, many=True)
        return Response(
            {
                "detail": "Generated schedules saved successfully.",
                "saved_count": len(schedules),
                "schedules": serialized.data,
            },
            status=status.HTTP_200_OK,
        )

    def apply_manual_change(self, request):
        """Apply a manual session-to-slot change and replan the entire schedule."""
        actor = getattr(request.user, "email", "")

        schedule_id = request.data.get("schedule_id")
        new_slot_index = request.data.get("new_slot_index")

        # Validate inputs
        if schedule_id is None:
            return Response(
                {"detail": "schedule_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_slot_index is None:
            return Response(
                {"detail": "new_slot_index is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            schedule_id = int(schedule_id)
            new_slot_index = int(new_slot_index)
        except (TypeError, ValueError):
            return Response(
                {"detail": "schedule_id and new_slot_index must be integers."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if schedule_id <= 0:
            return Response(
                {"schedule_id": "schedule_id must be a positive integer."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_slot_index < 0:
            return Response(
                {"new_slot_index": "new_slot_index must be zero or greater."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            new_schedules = ScheduleReplanner.replan_with_manual_change(
                user=request.user,
                schedule_to_move_id=schedule_id,
                new_slot_index=new_slot_index,
                actor_email=actor,
            )
        except ScheduleGenerationError:
            logger.warning(
                "ScheduleGenerationError while applying manual change: "
                "schedule_id=%s, new_slot_index=%s, actor=%s",
                schedule_id,
                new_slot_index,
                actor,
            )
            return Response(
                {"detail": "Failed to replan schedule with manual change."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serialized = self.get_serializer(new_schedules, many=True)
        return Response(
            {
                "detail": "Schedule replanned with manual change successfully.",
                "schedules": serialized.data,
                "generated_count": len(serialized.data),
            },
            status=status.HTTP_200_OK,
        )
