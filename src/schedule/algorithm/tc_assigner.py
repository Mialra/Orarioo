"""Greedy assigner for TC (Trabajo de Centro) duty hours.

Runs after postprocessing and before bulk_create. Does not interact with CP-SAT.
Reads the unsaved Schedule list to detect conflicts and generates TCSession objects.
"""

from dataclasses import dataclass, field

from schedule.algorithm.slots import slot_instance_key
from schedule.models import TCSession
from teacher.models import TeacherTimePreferenceState

# Cada minuto de déficit de horas exactas aporta esta cantidad de prioridad.
# Subirlo hace que los profesores con carga exacta se llenen antes que cualquier otro.
EXACT_HOURS_DEFICIT_PRIORITY = 60


@dataclass
class TCAssignmentResult:
    tc_sessions: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    # warning format: {"day": int, "start_time": str, "end_time": str,
    #                  "assigned": int, "required": int}


def assign_tc_sessions(
    *,
    teachers,
    existing_schedules,
    weekly_slots,
    teachers_on_duty,
    team,
) -> TCAssignmentResult:
    """Assign TC duty hours to available teachers for every non-recess slot of the week.

    Prioritizes teachers with dead gaps (class before AND after the slot that day).
    Input: teachers - list of Teacher instances for the team;
           existing_schedules - list of unsaved Schedule instances (pre-bulk_create);
           weekly_slots - slot dicts from build_weekly_slots(), keys 'start'/'end'/'is_recess';
           teachers_on_duty - target number of teachers per slot;
           team - CollaborationTeam instance
    Output: TCAssignmentResult with tc_sessions (unsaved) and warnings
    """
    if teachers_on_duty <= 0:
        return TCAssignmentResult()

    busy = _compute_busy_intervals(existing_schedules)
    unavailable = _compute_unavailable_slots(teachers, weekly_slots)
    class_slots_by_teacher_day = _compute_class_slots_by_teacher_day(existing_schedules)
    schedule_minutes = _compute_schedule_minutes_by_teacher(existing_schedules)
    unique_slots = _build_unique_tc_slots(weekly_slots)

    teacher_list = list(teachers)
    tc_sessions = []
    warnings = []
    tc_minutes_assigned = {}  # teacher_id -> TC minutes accumulated this run

    for slot in unique_slots:
        day = slot["day"]
        start_t = slot["start_time"]
        end_t = slot["end_time"]
        slot_minutes = (end_t.hour * 60 + end_t.minute) - (
            start_t.hour * 60 + start_t.minute
        )
        unavail_key = (day, start_t)

        candidates = []
        for teacher in teacher_list:
            tid = teacher.id
            if _overlaps_any(day, start_t, end_t, busy.get(tid, [])):
                continue
            if unavail_key in unavailable.get(tid, set()):
                continue
            max_mins = teacher.max_weekly_hours * 60 + teacher.max_weekly_minutes
            current_mins = schedule_minutes.get(tid, 0) + tc_minutes_assigned.get(
                tid, 0
            )
            if current_mins + slot_minutes > max_mins:
                continue
            is_gap = _is_dead_gap(
                teacher_id=tid,
                day=day,
                start_time=start_t,
                class_slots_by_teacher_day=class_slots_by_teacher_day,
            )
            exact_deficit = _compute_exact_hours_deficit(
                teacher=teacher,
                schedule_minutes=schedule_minutes,
                tc_minutes_assigned=tc_minutes_assigned,
            )
            candidates.append((teacher, is_gap, exact_deficit))

        # Exact-hours deficit teachers first (highest deficit first), then dead-gap, then rest
        candidates.sort(key=lambda c: (-c[2], not c[1]))

        assigned = [t for t, _, _ in candidates[:teachers_on_duty]]

        if len(assigned) < teachers_on_duty:
            warnings.append(
                {
                    "day": day,
                    "start_time": start_t.strftime("%H:%M:%S"),
                    "end_time": slot["end_time"].strftime("%H:%M:%S"),
                    "assigned": len(assigned),
                    "required": teachers_on_duty,
                }
            )

        for teacher in assigned:
            tc_minutes_assigned[teacher.id] = (
                tc_minutes_assigned.get(teacher.id, 0) + slot_minutes
            )
            tc_sessions.append(
                TCSession(
                    teacher=teacher,
                    day=day,
                    start_time=start_t,
                    end_time=slot["end_time"],
                    team=team,
                )
            )

    return TCAssignmentResult(tc_sessions=tc_sessions, warnings=warnings)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _build_unique_tc_slots(weekly_slots):
    """Return deduplicated 60-minute slots by (weekday, start.time()), excluding recess.

    Only keeps slots that are exactly 60 minutes so that recess slots (30 min) from
    any stage are uniformly discarded, regardless of which stage is processed first.
    """
    seen = set()
    result = []
    for slot in weekly_slots:
        if slot.get("is_recess"):
            continue
        day = slot["start"].weekday()
        start_t = slot["start"].time()
        end_t = slot["end"].time()
        duration = (end_t.hour * 60 + end_t.minute) - (
            start_t.hour * 60 + start_t.minute
        )
        if duration != 60:
            continue
        dedup_key = (day, start_t)
        if dedup_key not in seen:
            seen.add(dedup_key)
            result.append({"day": day, "start_time": start_t, "end_time": end_t})
    return result


def _compute_schedule_minutes_by_teacher(existing_schedules):
    """Return dict teacher_id -> total minutes of scheduled classes."""
    result = {}
    for schedule in existing_schedules:
        tid = schedule.teacher_id
        delta = int((schedule.end_time - schedule.start_time).total_seconds()) // 60
        result[tid] = result.get(tid, 0) + delta
    return result


def _compute_busy_intervals(existing_schedules):
    """Return dict teacher_id -> list of (weekday, start_time, end_time) covering class periods."""
    busy = {}
    for schedule in existing_schedules:
        tid = schedule.teacher_id
        busy.setdefault(tid, []).append(
            (
                schedule.start_time.weekday(),
                schedule.start_time.time(),
                schedule.end_time.time(),
            )
        )
    return busy


def _overlaps_any(tc_day, tc_start, tc_end, intervals):
    """Return True if [tc_start, tc_end) overlaps any interval on tc_day."""
    for day, s, e in intervals:
        if day == tc_day and tc_start < e and s < tc_end:
            return True
    return False


def _compute_unavailable_slots(teachers, weekly_slots):
    """Return dict teacher_id -> set of (weekday, time) where teacher is UNAVAILABLE in any stage."""
    unavailable = {}
    for teacher in teachers:
        prefs = teacher.time_preferences or {}
        slots_set = set()
        for slot in weekly_slots:
            if (
                prefs.get(slot_instance_key(slot=slot))
                == TeacherTimePreferenceState.UNAVAILABLE
            ):
                slots_set.add((slot["start"].weekday(), slot["start"].time()))
        if slots_set:
            unavailable[teacher.id] = slots_set
    return unavailable


def _compute_class_slots_by_teacher_day(existing_schedules):
    """Return dict (teacher_id, weekday) -> sorted list of start times (time objects)."""
    result = {}
    for schedule in existing_schedules:
        key = (schedule.teacher_id, schedule.start_time.weekday())
        result.setdefault(key, []).append(schedule.start_time.time())
    for key in result:
        result[key].sort()
    return result


def _compute_exact_hours_deficit(*, teacher, schedule_minutes, tc_minutes_assigned):
    """Return remaining minutes to fill for exact-hours teachers, 0 otherwise.

    Used to sort TC candidates: teachers below their exact-hours target get
    priority proportional to their deficit so they are filled first.
    Input: teacher - Teacher instance; schedule_minutes, tc_minutes_assigned -
           dicts {teacher_id: minutes} accumulated so far
    Output: non-negative integer (minutes still needed), or 0
    """
    if not getattr(teacher, "weekly_hours_exact", False):
        return 0
    target = teacher.max_weekly_hours * 60 + teacher.max_weekly_minutes
    current = schedule_minutes.get(teacher.id, 0) + tc_minutes_assigned.get(
        teacher.id, 0
    )
    return max(0, target - current)


def _is_dead_gap(*, teacher_id, day, start_time, class_slots_by_teacher_day):
    """Return True if the teacher has a class both before and after start_time on that day."""
    class_times = class_slots_by_teacher_day.get((teacher_id, day), [])
    if not class_times:
        return False
    return any(ct < start_time for ct in class_times) and any(
        ct > start_time for ct in class_times
    )
