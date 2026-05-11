"""CRUD and swap views for TCSession (Trabajo de Centro duty hours)."""

from datetime import timedelta

from django.db import transaction
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.tenancy import get_active_team
from schedule.algorithm.slots import DAY_CODE_BY_WEEKDAY
from schedule.constants import SAVED_TIMETABLE_PREFIX
from schedule.models import Schedule, TCSession
from schedule.serializers_tc import TCSessionSerializer
from teacher.models import Teacher, TeacherTimePreferenceState

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_DAY_LABELS = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]


def _is_teacher_unavailable(teacher, day, start_time, end_time):
    """Return True if the teacher is UNAVAILABLE in any stage for the given slot."""
    prefs = teacher.time_preferences or {}
    day_code = DAY_CODE_BY_WEEKDAY.get(day, "")
    start_str = start_time.strftime("%H:%M")
    end_str = end_time.strftime("%H:%M")
    for stage in ("PRESCHOOL", "PRIMARY", "SECONDARY", "ALEVELS"):
        key = f"{stage}_{day_code}_{start_str}_{end_str}"
        if prefs.get(key) == TeacherTimePreferenceState.UNAVAILABLE:
            return True
    return False


def _teacher_has_schedule_at(teacher_id, team, day, start_time):
    """Return True if the teacher already has a Schedule at (day, start_time) for the team."""
    # Django iso_week_day: Monday=1 … Friday=5; our day is 0-indexed Mon=0
    return Schedule.objects.filter(
        teacher_id=teacher_id,
        team=team,
        start_time__iso_week_day=day + 1,
        start_time__time=start_time,
    ).exists()


def _teacher_has_tc_at(teacher_id, team, day, start_time, exclude_id=None):
    """Return True if the teacher already has a draft TCSession at (day, start_time) for the team."""
    qs = TCSession.objects.filter(
        teacher_id=teacher_id,
        team=team,
        observations="",
        day=day,
        start_time=start_time,
    )
    if exclude_id is not None:
        qs = qs.exclude(pk=exclude_id)
    return qs.exists()


def _slot_duration(start_time, end_time):
    """Return the duration of a slot as a timedelta."""
    start_delta = timedelta(hours=start_time.hour, minutes=start_time.minute)
    end_delta = timedelta(hours=end_time.hour, minutes=end_time.minute)
    return end_delta - start_delta


def _build_hours_warning(teacher, team, extra_minutes):
    """Return a warning string if adding extra_minutes violates weekly_hours_exact, else None."""
    if not teacher.weekly_hours_exact:
        return None
    max_minutes = teacher.max_weekly_hours * 60 + teacher.max_weekly_minutes
    existing_tc_minutes = _sum_tc_minutes(teacher, team)
    schedule_minutes = _sum_schedule_minutes(teacher, team)
    total_after = schedule_minutes + existing_tc_minutes + extra_minutes
    if total_after > max_minutes:
        total_hours = total_after // 60
        return (
            f"El docente {teacher.name} pasaría a tener {total_hours}h, "
            f"superando sus horas exactas de {teacher.max_weekly_hours}h."
        )
    return None


def _build_delete_hours_warning(teacher, team, removed_minutes):
    """Return a warning string if removing removed_minutes violates weekly_hours_exact, else None."""
    if not teacher.weekly_hours_exact:
        return None
    max_minutes = teacher.max_weekly_hours * 60 + teacher.max_weekly_minutes
    existing_tc_minutes = _sum_tc_minutes(teacher, team)
    schedule_minutes = _sum_schedule_minutes(teacher, team)
    total_after = schedule_minutes + existing_tc_minutes - removed_minutes
    if total_after < max_minutes:
        total_hours = total_after // 60
        return (
            f"El docente {teacher.name} pasa a tener {total_hours}h. "
            f"Sus horas exactas son {teacher.max_weekly_hours}h."
        )
    return None


def _sum_tc_minutes(teacher, team):
    total = 0
    for tc in TCSession.objects.filter(teacher=teacher, team=team):
        total += _slot_duration(tc.start_time, tc.end_time).seconds // 60
    return total


def _sum_schedule_minutes(teacher, team):
    total = 0
    for sch in Schedule.objects.filter(teacher=teacher, team=team):
        delta = sch.end_time - sch.start_time
        total += int(delta.total_seconds()) // 60
    return total


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------


class TCSessionListView(generics.ListAPIView):
    """GET /api/tc-sessions/ — list TCSession for the active team.

    Filters: ?teacher=<id>  ?day=<0-4>
    """

    serializer_class = TCSessionSerializer
    pagination_class = None

    def get_queryset(self):
        team = get_active_team(self.request)
        timetable_name = self.request.query_params.get("timetable_name", "")
        if timetable_name:
            obs_filter = f"{SAVED_TIMETABLE_PREFIX}: {timetable_name}"
            qs = TCSession.objects.filter(
                team=team, observations=obs_filter
            ).select_related("teacher")
        else:
            qs = (
                TCSession.objects.filter(team=team)
                .exclude(observations__startswith=SAVED_TIMETABLE_PREFIX)
                .select_related("teacher")
            )

        teacher_id = self.request.query_params.get("teacher")
        if teacher_id:
            qs = qs.filter(teacher_id=teacher_id)

        day = self.request.query_params.get("day")
        if day is not None:
            qs = qs.filter(day=day)

        return qs.order_by("day", "start_time")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def _parse_day(raw):
    """Return (day_int, error) where day_int is 0-4 (Mon-Fri)."""
    try:
        day = int(raw)
        if day not in range(5):
            raise ValueError
        return day, None
    except (TypeError, ValueError):
        return None, Response(
            {"detail": "day must be an integer between 0 (Monday) and 4 (Friday)."},
            status=status.HTTP_400_BAD_REQUEST,
        )


def _get_teacher(teacher_id, team):
    """Return (teacher, error) for the given pk and team."""
    try:
        return Teacher.objects.get(pk=teacher_id, team=team), None
    except Teacher.DoesNotExist:
        return None, Response(
            {"detail": "Teacher not found."}, status=status.HTTP_404_NOT_FOUND
        )


def _parse_time_str(raw, field):
    """Return (time, error) parsed from an HH:MM string."""
    from datetime import time as time_type

    try:
        parts = str(raw).split(":")
        return time_type(int(parts[0]), int(parts[1])), None
    except (ValueError, IndexError):
        return None, Response(
            {"detail": f"{field} must be in HH:MM or HH:MM:SS format."},
            status=status.HTTP_400_BAD_REQUEST,
        )


def _parse_tc_create_params(request, team):
    """Validate and parse TCSession creation params. Returns (params_dict, error_Response)."""
    teacher_id = request.data.get("teacher")
    day_raw = request.data.get("day")
    start_time_raw = request.data.get("start_time")
    end_time_raw = request.data.get("end_time")

    if any(v is None for v in [teacher_id, day_raw, start_time_raw, end_time_raw]):
        return None, Response(
            {"detail": "teacher, day, start_time and end_time are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    day, err = _parse_day(day_raw)
    if err:
        return None, err

    teacher, err = _get_teacher(teacher_id, team)
    if err:
        return None, err

    start_time, err = _parse_time_str(start_time_raw, "start_time")
    if err:
        return None, err
    end_time, err = _parse_time_str(end_time_raw, "end_time")
    if err:
        return None, err

    if end_time <= start_time:
        return None, Response(
            {"detail": "end_time must be after start_time."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    return {
        "teacher": teacher,
        "day": day,
        "start_time": start_time,
        "end_time": end_time,
    }, None


def _check_tc_slot_conflicts(teacher, team, day, start_time, end_time):
    """Return a conflict Response if the slot is taken, else None."""
    if _teacher_has_schedule_at(teacher.id, team, day, start_time):
        return Response(
            {
                "detail": f"{teacher.name} ya tiene una clase el {_DAY_LABELS[day]} a las {start_time:%H:%M}."
            },
            status=status.HTTP_409_CONFLICT,
        )
    if _teacher_has_tc_at(teacher.id, team, day, start_time):
        return Response(
            {
                "detail": f"{teacher.name} ya tiene una guardia TC el {_DAY_LABELS[day]} a las {start_time:%H:%M}."
            },
            status=status.HTTP_409_CONFLICT,
        )
    if _is_teacher_unavailable(teacher, day, start_time, end_time):
        return Response(
            {
                "detail": f"{teacher.name} está marcado como no disponible el {_DAY_LABELS[day]} a las {start_time:%H:%M}."
            },
            status=status.HTTP_409_CONFLICT,
        )
    return None


class TCSessionCreateView(APIView):
    """POST /api/tc-sessions/create/ — manually create a TCSession."""

    def post(self, request):
        team = get_active_team(request)

        params, err = _parse_tc_create_params(request, team)
        if err:
            return err

        teacher = params["teacher"]
        day = params["day"]
        start_time = params["start_time"]
        end_time = params["end_time"]

        conflict = _check_tc_slot_conflicts(teacher, team, day, start_time, end_time)
        if conflict:
            return conflict

        duration_minutes = _slot_duration(start_time, end_time).seconds // 60
        warning = _build_hours_warning(teacher, team, duration_minutes)

        tc = TCSession.objects.create(
            teacher=teacher,
            day=day,
            start_time=start_time,
            end_time=end_time,
            team=team,
        )

        response_data = {"tc_session": TCSessionSerializer(tc).data}
        if warning:
            response_data["warning"] = warning
        return Response(response_data, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TCSessionDeleteView(APIView):
    """DELETE /api/tc-sessions/<pk>/ — remove a TCSession."""

    def delete(self, request, pk):
        team = get_active_team(request)
        try:
            tc = TCSession.objects.select_related("teacher").get(pk=pk, team=team)
        except TCSession.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        duration_minutes = _slot_duration(tc.start_time, tc.end_time).seconds // 60
        warning = _build_delete_hours_warning(tc.teacher, team, duration_minutes)
        tc.delete()

        response_data = {"deleted": True}
        if warning:
            response_data["warning"] = warning
        return Response(response_data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Swap
# ---------------------------------------------------------------------------


class TCSessionSwapView(APIView):
    """POST /api/tc-sessions/swap/ — swap slot between two TCSession records.

    Body: {"tc_session_a": <id>, "tc_session_b": <id>}
    Same-teacher swaps (different slots) are valid.
    """

    def post(self, request):
        team = get_active_team(request)

        id_a = request.data.get("tc_session_a")
        id_b = request.data.get("tc_session_b")

        if id_a is None or id_b is None:
            return Response(
                {"detail": "tc_session_a and tc_session_b are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            tc_a = TCSession.objects.select_related("teacher").get(pk=id_a, team=team)
            tc_b = TCSession.objects.select_related("teacher").get(pk=id_b, team=team)
        except TCSession.DoesNotExist:
            return Response(
                {"detail": "One or both TCSession records not found."},
                status=status.HTTP_404_NOT_FOUND,
            )

        dur_a = _slot_duration(tc_a.start_time, tc_a.end_time)
        dur_b = _slot_duration(tc_b.start_time, tc_b.end_time)
        if dur_a != dur_b:
            return Response(
                {"detail": "Cannot swap TCSession records with different durations."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check that teacher A can occupy slot B
        if _teacher_has_schedule_at(tc_a.teacher_id, team, tc_b.day, tc_b.start_time):
            return Response(
                {
                    "detail": (
                        f"{tc_a.teacher.name} ya tiene una clase el "
                        f"{_DAY_LABELS[tc_b.day]} a las {tc_b.start_time:%H:%M}."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Check that teacher B can occupy slot A
        if _teacher_has_schedule_at(tc_b.teacher_id, team, tc_a.day, tc_a.start_time):
            return Response(
                {
                    "detail": (
                        f"{tc_b.teacher.name} ya tiene una clase el "
                        f"{_DAY_LABELS[tc_a.day]} a las {tc_a.start_time:%H:%M}."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        # Check UNAVAILABLE for each teacher in the target slot
        if _is_teacher_unavailable(
            tc_a.teacher, tc_b.day, tc_b.start_time, tc_b.end_time
        ):
            return Response(
                {
                    "detail": (
                        f"{tc_a.teacher.name} está marcado como no disponible el "
                        f"{_DAY_LABELS[tc_b.day]} a las {tc_b.start_time:%H:%M}."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        if _is_teacher_unavailable(
            tc_b.teacher, tc_a.day, tc_a.start_time, tc_a.end_time
        ):
            return Response(
                {
                    "detail": (
                        f"{tc_b.teacher.name} está marcado como no disponible el "
                        f"{_DAY_LABELS[tc_a.day]} a las {tc_a.start_time:%H:%M}."
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )

        with transaction.atomic():
            slot_a = (tc_a.day, tc_a.start_time, tc_a.end_time)
            slot_b = (tc_b.day, tc_b.start_time, tc_b.end_time)

            tc_a.day, tc_a.start_time, tc_a.end_time = slot_b
            tc_b.day, tc_b.start_time, tc_b.end_time = slot_a

            tc_a.save()
            tc_b.save()

        return Response(
            {
                "tc_session_a": TCSessionSerializer(tc_a).data,
                "tc_session_b": TCSessionSerializer(tc_b).data,
            },
            status=status.HTTP_200_OK,
        )
