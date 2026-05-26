"""Move/swap validation helpers for the schedule timetable editor.

All functions validate or compute data for the move and swap operations.
They are pure logic helpers imported by ScheduleViewSet in views.py.
"""

from datetime import datetime, timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response

from schedule.algorithm.constraints.hard import (
    group_daily_limit,
    session_preference_state,
    teacher_preference_state,
)
from schedule.algorithm.slots import (
    STAGE_SLOT_WINDOWS,
    session_stage_code,
    slot_preference_key_from_datetime,
)
from subject.models import SubjectTimePreferenceState
from teacher.models import TeacherTimePreferenceState

DAY_NAME_TO_WEEKDAY = {
    "Lunes": 0,
    "Martes": 1,
    "Miércoles": 2,
    "Jueves": 3,
    "Viernes": 4,
}
WEEKDAY_TO_DAY_NAME = {value: key for key, value in DAY_NAME_TO_WEEKDAY.items()}


def parse_hhmm(raw_value, field_name):
    """Parse a time string in HH:MM format.
    Input: raw_value - raw string; field_name - name for error messages
    Output: tuple (time, None) on success, or (None, Response) with HTTP 400 on failure
    """
    value = (raw_value or "").strip()
    try:
        return datetime.strptime(value, "%H:%M").time(), None
    except ValueError:
        return None, Response(
            {"detail": f"{field_name} must follow HH:MM format."},
            status=status.HTTP_400_BAD_REQUEST,
        )


def normalize_move_mode(raw_mode):
    """Normalise and validate the move mode parameter.
    Input: raw_mode - raw string from request payload
    Output: tuple ('move'|'swap', None) on success, or (None, Response) with HTTP 400
    """
    mode = (raw_mode or "move").strip().lower()
    if mode not in {"move", "swap"}:
        return None, Response(
            {"detail": "mode must be one of: move, swap."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return mode, None


def parse_move_slot(slot_data, slot_label, *, require_schedule_id=False):
    """Parse and validate a slot descriptor dict from a move/swap request.
    Input: slot_data - dict with keys day, start, end and optionally schedule_id;
           slot_label - label used in error messages (e.g. 'source_slot');
           require_schedule_id - if True, schedule_id is mandatory
    Output: tuple (slot_dict, None) on success, or (None, Response) with HTTP 400;
            returned slot_dict includes day, start, end, start_time, end_time, schedule_id
    """
    if not isinstance(slot_data, dict):
        return None, Response(
            {"detail": f"{slot_label} must be an object."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    day_name = (slot_data.get("day") or "").strip()
    if day_name not in DAY_NAME_TO_WEEKDAY:
        return None, Response(
            {
                "detail": (
                    f"{slot_label}.day must be one of: "
                    "Lunes, Martes, Miércoles, Jueves, Viernes."
                )
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    start_raw = slot_data.get("start")
    end_raw = slot_data.get("end")
    start_time, start_error = parse_hhmm(start_raw, f"{slot_label}.start")
    if start_error is not None:
        return None, start_error
    end_time, end_error = parse_hhmm(end_raw, f"{slot_label}.end")
    if end_error is not None:
        return None, end_error
    if end_time <= start_time:
        return None, Response(
            {"detail": f"{slot_label}.end must be greater than {slot_label}.start."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    schedule_id = None
    raw_schedule_id = slot_data.get("schedule_id")
    if require_schedule_id and raw_schedule_id in (None, ""):
        return None, Response(
            {"detail": f"{slot_label}.schedule_id is required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if raw_schedule_id not in (None, ""):
        from schedule.views_generate import parse_positive_int

        parsed_schedule_id, parse_error = parse_positive_int(
            raw_schedule_id,
            f"{slot_label}.schedule_id",
        )
        if parse_error is not None:
            return None, parse_error
        schedule_id = parsed_schedule_id

    return {
        "day": day_name,
        "start": start_time.strftime("%H:%M"),
        "end": end_time.strftime("%H:%M"),
        "start_time": start_time,
        "end_time": end_time,
        "schedule_id": schedule_id,
    }, None


def slot_descriptor_from_datetimes(start_dt, end_dt):
    """Build a slot descriptor dict from two aware datetimes.
    Input: start_dt - aware datetime; end_dt - aware datetime
    Output: dict with day, start and end string keys
    """
    local_start = timezone.localtime(start_dt)
    local_end = timezone.localtime(end_dt)
    return {
        "day": WEEKDAY_TO_DAY_NAME.get(local_start.weekday(), ""),
        "start": local_start.strftime("%H:%M"),
        "end": local_end.strftime("%H:%M"),
    }


def resolve_slot_datetimes_for_source_week(
    *,
    source_start,
    day_name,
    start_time,
    end_time,
):
    """Compute the target aware datetimes anchored to the same week as source_start.
    Input: source_start - aware datetime of the source schedule;
           day_name - target day name (e.g. 'Lunes');
           start_time, end_time - target time objects
    Output: tuple (target_start_dt, target_end_dt) as aware datetimes
    """
    source_local = timezone.localtime(source_start)
    monday_date = source_local.date() - timedelta(days=source_local.weekday())
    target_date = monday_date + timedelta(days=DAY_NAME_TO_WEEKDAY[day_name])
    current_tz = timezone.get_current_timezone()
    target_start = timezone.make_aware(
        datetime.combine(target_date, start_time),
        current_tz,
    )
    target_end = timezone.make_aware(
        datetime.combine(target_date, end_time),
        current_tz,
    )
    return target_start, target_end


def times_overlap(*, left_start, left_end, right_start, right_end):
    """Check whether two time intervals overlap strictly.
    Input: left_start, left_end, right_start, right_end - aware datetimes
    Output: True if the intervals overlap, False otherwise
    """
    return left_start < right_end and right_start < left_end


def normalize_clock(value):
    """Strip seconds, microseconds and timezone info from a time value.
    Input: value - time object
    Output: time object with second=0, microsecond=0, tzinfo=None
    """
    return value.replace(second=0, microsecond=0, tzinfo=None)


def is_stage_window_allowed(*, schedule, start_dt, end_dt):
    """Check whether a target slot falls within the allowed windows for the session stage.
    Input: schedule - Schedule instance with group and subject;
           start_dt, end_dt - target aware datetimes
    Output: True if the slot is a valid stage window on a weekday, False otherwise
    """
    stage_code = session_stage_code(
        session={"group": schedule.group, "subject": schedule.subject}
    )
    allowed_windows = STAGE_SLOT_WINDOWS.get(stage_code, [])

    local_start = timezone.localtime(start_dt)
    local_end = timezone.localtime(end_dt)
    if local_start.date() != local_end.date() or local_start.weekday() > 4:
        return False

    candidate_window = (
        normalize_clock(local_start.time()),
        normalize_clock(local_end.time()),
    )
    normalized_allowed = {
        (normalize_clock(left), normalize_clock(right))
        for left, right, _ in allowed_windows
    }
    return candidate_window in normalized_allowed


_SLOT_KEY_DAY_TO_ES = {
    "MON": "lunes",
    "TUE": "martes",
    "WED": "miércoles",
    "THU": "jueves",
    "FRI": "viernes",
}


def _format_slot_key_es(slot_key):
    day_code, time = slot_key.split("_", 1)
    day_es = _SLOT_KEY_DAY_TO_ES.get(day_code, day_code)
    return f"{day_es} a las {time}"


def validate_target_preferences(*, schedule, start_dt):
    """Validate that neither the subject nor the teacher is UNAVAILABLE at the target slot.
    Input: schedule - Schedule instance with subject and teacher;
           start_dt - target aware datetime
    Output: None if preferences allow the slot, or an error message string otherwise
    """
    slot_key = slot_preference_key_from_datetime(slot=start_dt)
    if slot_key is None:
        return None

    session_ctx = {"subject": schedule.subject, "teacher": schedule.teacher}
    subject_state = session_preference_state(
        session=session_ctx,
        slot_preference_key=slot_key,
    )
    if subject_state == SubjectTimePreferenceState.UNAVAILABLE:
        return f"La asignatura '{schedule.subject.name}' no está disponible el {_format_slot_key_es(slot_key)}."

    teacher_state = teacher_preference_state(
        session=session_ctx,
        slot_preference_key=slot_key,
    )
    if teacher_state == TeacherTimePreferenceState.UNAVAILABLE:
        return f"El profesor '{schedule.teacher.name}' no está disponible el {_format_slot_key_es(slot_key)}."
    return None


def build_hypothetical_times(*, scope_schedules, assignments):
    """Build a hypothetical time map merging current times with proposed assignments.
    Input: scope_schedules - list of Schedule instances; assignments - dict {id: (start, end)}
    Output: dict {schedule_id: (start_dt, end_dt)} with assignments overriding current times
    """
    hypothetical = {
        schedule.id: (schedule.start_time, schedule.end_time)
        for schedule in scope_schedules
    }
    hypothetical.update(assignments)
    return hypothetical


def validate_resource_overlaps_for_changes(
    *,
    scope_schedules,
    hypothetical_times,
    changed_ids,
):
    """Check that no teacher, group or classroom has overlapping sessions after the proposed change.
    Input: scope_schedules - list of Schedule instances;
           hypothetical_times - dict {id: (start, end)} from build_hypothetical_times;
           changed_ids - set of schedule ids whose times changed
    Output: None if no conflicts, or Response with HTTP 400 describing the first conflict
    """
    schedule_by_id = {schedule.id: schedule for schedule in scope_schedules}
    for changed_id in changed_ids:
        current_schedule = schedule_by_id[changed_id]
        current_start, current_end = hypothetical_times[changed_id]
        for other_schedule in scope_schedules:
            if other_schedule.id == changed_id:
                continue

            other_start, other_end = hypothetical_times[other_schedule.id]
            if not times_overlap(
                left_start=current_start,
                left_end=current_end,
                right_start=other_start,
                right_end=other_end,
            ):
                continue

            if (
                current_schedule.teacher_id is not None
                and current_schedule.teacher_id == other_schedule.teacher_id
            ):
                return Response(
                    {
                        "detail": (
                            f"El profesor '{current_schedule.teacher.name}' "
                            "ya tiene otra sesión en ese hueco horario."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if (
                current_schedule.group_id is not None
                and current_schedule.group_id == other_schedule.group_id
            ):
                return Response(
                    {
                        "detail": (
                            f"El curso '{current_schedule.group.name}' "
                            "ya tiene otra sesión en ese hueco horario."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            if (
                current_schedule.classroom_id is not None
                and current_schedule.classroom_id == other_schedule.classroom_id
            ):
                return Response(
                    {
                        "detail": (
                            f"El aula '{current_schedule.classroom.name}' "
                            "ya está ocupada en ese hueco horario."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

    return None


def validate_group_daily_limits(
    *,
    scope_schedules,
    hypothetical_times,
    changed_group_ids,
):
    """Check that no group exceeds its stage-based daily session limit after the change.
    Input: scope_schedules - list of Schedule instances;
           hypothetical_times - dict {id: (start, end)};
           changed_group_ids - set of group ids affected by the change
    Output: None if within limits, or Response with HTTP 400 on violation
    """
    group_by_id = {}
    day_count_by_group = {}

    for schedule in scope_schedules:
        if schedule.group_id not in changed_group_ids:
            continue
        group_by_id[schedule.group_id] = schedule.group
        schedule_start, _ = hypothetical_times[schedule.id]
        schedule_day = timezone.localtime(schedule_start).date()
        key = (schedule.group_id, schedule_day)
        day_count_by_group[key] = day_count_by_group.get(key, 0) + 1

    for (group_id, _), count in day_count_by_group.items():
        group = group_by_id.get(group_id)
        if group is None:
            continue
        if count > group_daily_limit(group):
            return Response(
                {
                    "detail": (
                        f"Group '{group.name}' exceeds daily slot limit for "
                        "its stage."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
    return None


def window_index_by_stage(group, slot_windows=None):
    """Build a mapping from (start_time, end_time) window to its position in the stage's window list.
    Input: group - Group model instance with a 'stage' attribute;
           slot_windows - optional dict {stage_code: [(start, end, is_recess), ...]}; falls back
                          to STAGE_SLOT_WINDOWS when None
    Output: tuple (dict {(time, time): int}, frozenset of recess indices)
    """
    stage_code = session_stage_code(session={"group": group, "subject": None})
    windows = slot_windows if slot_windows is not None else STAGE_SLOT_WINDOWS
    allowed_windows = windows.get(stage_code, [])
    w_index = {}
    recess_indices = set()
    for index, (left, right, is_recess) in enumerate(allowed_windows):
        w_index[(normalize_clock(left), normalize_clock(right))] = index
        if is_recess:
            recess_indices.add(index)
    return w_index, frozenset(recess_indices)


def collect_group_day_window_indices(
    *,
    group_schedules,
    hypothetical_times,
    window_to_index,
):
    """Map each group's sessions per day to their window position indices.
    Input: group_schedules - list of Schedule instances for one group;
           hypothetical_times - dict {id: (start, end)};
           window_to_index - dict from window_index_by_stage
    Output: dict {date: [window_idx, ...]} or None if any session falls outside known windows
    """
    by_day = {}
    for schedule in group_schedules:
        start_dt, end_dt = hypothetical_times[schedule.id]
        day_key = timezone.localtime(start_dt).date()
        by_day.setdefault(day_key, []).append((start_dt, end_dt))

    by_day_indices = {}
    for day_key, day_items in by_day.items():
        occupied_indices = []
        for start_dt, end_dt in day_items:
            local_start = timezone.localtime(start_dt)
            local_end = timezone.localtime(end_dt)
            window_key = (
                normalize_clock(local_start.time()),
                normalize_clock(local_end.time()),
            )
            index = window_to_index.get(window_key)
            if index is None:
                return None
            occupied_indices.append(index)
        if occupied_indices:
            by_day_indices[day_key] = occupied_indices
    return by_day_indices


def has_intraday_gap(occupied_indices, recess_indices=frozenset()):
    """Return True if there is a gap between the first and last occupied window indices.
    Input: occupied_indices - list of integer window position indices for a single day;
           recess_indices - frozenset of indices that represent recess breaks (never occupied)
    Output: True if any non-recess index in the range [min, max] is missing, False otherwise
    """
    first_idx = min(occupied_indices)
    last_idx = max(occupied_indices)
    occupied_set = set(occupied_indices)
    return any(
        index not in occupied_set
        for index in range(first_idx, last_idx + 1)
        if index not in recess_indices
    )


def group_schedules_by_id(*, scope_schedules, changed_group_ids):
    """Group schedule instances by group_id, restricted to changed groups.
    Input: scope_schedules - list of Schedule instances;
           changed_group_ids - set of group ids to include
    Output: dict {group_id: [Schedule, ...]}
    """
    grouped = {}
    for schedule in scope_schedules:
        if schedule.group_id in changed_group_ids:
            grouped.setdefault(schedule.group_id, []).append(schedule)
    return grouped


def validate_group_intraday_gaps(
    *,
    scope_schedules,
    hypothetical_times,
    changed_group_ids,
    slot_windows=None,
):
    """Check that no group would have intraday gaps in its schedule after the proposed change.
    Input: scope_schedules - list of Schedule instances;
           hypothetical_times - dict {id: (start, end)};
           changed_group_ids - set of group ids affected by the change;
           slot_windows - optional team-specific stage windows; falls back to STAGE_SLOT_WINDOWS
    Output: None if no gaps detected, or Response with HTTP 400 on violation
    """
    schedules_by_group = group_schedules_by_id(
        scope_schedules=scope_schedules,
        changed_group_ids=changed_group_ids,
    )

    for group_schedules in schedules_by_group.values():
        if not group_schedules:
            continue

        reference_group = group_schedules[0].group
        w_index, recess_indices = window_index_by_stage(reference_group, slot_windows)
        if not w_index:
            continue

        by_day_indices = collect_group_day_window_indices(
            group_schedules=group_schedules,
            hypothetical_times=hypothetical_times,
            window_to_index=w_index,
        )
        if by_day_indices is None:
            continue

        for occupied_indices in by_day_indices.values():
            if has_intraday_gap(occupied_indices, recess_indices):
                return Response(
                    {
                        "detail": (
                            f"El grupo '{reference_group.name}' tendría huecos en el horario con ese cambio."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

    return None


def validate_minimal_move_constraints(
    *,
    scope_schedules,
    assignments,
    changed_ids,
    slot_windows=None,
):
    """Run all lightweight move validations (stage window, preferences, overlaps, limits, gaps).
    Input: scope_schedules - list of Schedule instances in scope;
           assignments - dict {id: (start_dt, end_dt)} of proposed changes;
           changed_ids - set of schedule ids being moved/swapped;
           slot_windows - optional team-specific stage windows; falls back to STAGE_SLOT_WINDOWS
    Output: None if all validations pass, or Response with HTTP 400 on the first failure
    """
    hypothetical_times = build_hypothetical_times(
        scope_schedules=scope_schedules,
        assignments=assignments,
    )
    schedule_by_id = {schedule.id: schedule for schedule in scope_schedules}

    for changed_id in changed_ids:
        schedule = schedule_by_id[changed_id]
        start_dt, end_dt = hypothetical_times[changed_id]

        if end_dt <= start_dt:
            return Response(
                {"detail": "Target slot must end after it starts."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not is_stage_window_allowed(
            schedule=schedule,
            start_dt=start_dt,
            end_dt=end_dt,
        ):
            return Response(
                {
                    "detail": (
                        "El hueco de destino no está permitido para la etapa del curso "
                        f"'{schedule.group.stage}'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        preference_error = validate_target_preferences(
            schedule=schedule,
            start_dt=start_dt,
        )
        if preference_error is not None:
            return Response(
                {"detail": preference_error},
                status=status.HTTP_400_BAD_REQUEST,
            )

    overlap_error = validate_resource_overlaps_for_changes(
        scope_schedules=scope_schedules,
        hypothetical_times=hypothetical_times,
        changed_ids=changed_ids,
    )
    if overlap_error is not None:
        return overlap_error

    changed_group_ids = {
        schedule_by_id[schedule_id].group_id
        for schedule_id in changed_ids
        if schedule_by_id[schedule_id].group_id is not None
    }

    daily_limit_error = validate_group_daily_limits(
        scope_schedules=scope_schedules,
        hypothetical_times=hypothetical_times,
        changed_group_ids=changed_group_ids,
    )
    if daily_limit_error is not None:
        return daily_limit_error

    gap_error = validate_group_intraday_gaps(
        scope_schedules=scope_schedules,
        hypothetical_times=hypothetical_times,
        changed_group_ids=changed_group_ids,
        slot_windows=slot_windows,
    )
    if gap_error is not None:
        return gap_error

    return None


def build_move_assignments(
    *,
    source_schedule,
    target_schedule,
    target_start_dt,
    target_end_dt,
):
    """Build the assignments dict and changed_ids set for a move or swap operation.
    Input: source_schedule - Schedule to move; target_schedule - Schedule to swap with, or None;
           target_start_dt, target_end_dt - target slot datetimes
    Output: tuple (assignments, changed_ids, original_source_times, original_target_times)
    """
    original_source_times = (source_schedule.start_time, source_schedule.end_time)
    assignments = {source_schedule.id: (target_start_dt, target_end_dt)}
    changed_ids = {source_schedule.id}
    original_target_times = None

    if target_schedule is not None:
        original_target_times = (
            target_schedule.start_time,
            target_schedule.end_time,
        )
        assignments[target_schedule.id] = original_source_times
        changed_ids.add(target_schedule.id)

    return assignments, changed_ids, original_source_times, original_target_times


def build_affected_slot_descriptors(
    *,
    original_source_times,
    target_start_dt,
    target_end_dt,
    original_target_times,
):
    """Build the list of unique affected slot descriptors for the move response.
    Input: original_source_times - (start, end) tuple of the source before the move;
           target_start_dt, target_end_dt - target slot datetimes;
           original_target_times - (start, end) of the swap target, or None
    Output: list of unique slot descriptor dicts (day, start, end)
    """
    affected_slots = [
        slot_descriptor_from_datetimes(
            original_source_times[0],
            original_source_times[1],
        ),
        slot_descriptor_from_datetimes(target_start_dt, target_end_dt),
    ]
    if original_target_times is not None:
        affected_slots.append(
            slot_descriptor_from_datetimes(
                original_target_times[0],
                original_target_times[1],
            )
        )

    unique_affected_slots = []
    seen_slots = set()
    for slot in affected_slots:
        key = (slot["day"], slot["start"], slot["end"])
        if key in seen_slots:
            continue
        seen_slots.add(key)
        unique_affected_slots.append(slot)
    return unique_affected_slots


def is_no_changes_move(
    *,
    mode,
    source_schedule,
    target_schedule,
    target_start_dt,
    target_end_dt,
):
    """Return True if the proposed move/swap results in no actual data change.
    Input: mode - 'move' or 'swap'; source_schedule - source Schedule;
           target_schedule - swap target or None; target_start_dt, target_end_dt - target times
    Output: True if the operation would be a no-op, False otherwise
    """
    if target_schedule is not None and target_schedule.id == source_schedule.id:
        return True

    return (
        mode == "move"
        and source_schedule.start_time == target_start_dt
        and source_schedule.end_time == target_end_dt
    )
