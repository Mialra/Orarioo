"""Pure-dict and SimpleNamespace factories for algorithm unit tests.

No database access. All algorithm functions work with plain dicts and duck-typed
objects, so SimpleNamespace is sufficient and cheaper than Mock or ORM instances.
Base date is pinned to a known Monday so slot-index arithmetic is deterministic
regardless of when the test suite runs.
"""

from datetime import date as _date
from datetime import datetime, time, timedelta
from types import SimpleNamespace

from django.utils import timezone

BASE_MONDAY = _date(2024, 1, 8)  # known Monday
DAY_CODES = {0: "MON", 1: "TUE", 2: "WED", 3: "THU", 4: "FRI"}


# ---------------------------------------------------------------------------
# Slot factories
# ---------------------------------------------------------------------------


def make_slot(
    *,
    day_offset=0,
    hour=9,
    minute=0,
    duration_minutes=60,
    stage="primary",
    is_recess=False,
):
    """Return a slot dict matching the shape produced by build_weekly_slots.

    day_offset=0 → BASE_MONDAY, 1 → Tuesday, etc.
    stage uses lowercase group-stage codes to match the algorithm's expectation.
    """
    d = BASE_MONDAY + timedelta(days=day_offset)
    start = timezone.make_aware(datetime.combine(d, time(hour, minute)))
    end = start + timedelta(minutes=duration_minutes)
    return {
        "start": start,
        "end": end,
        "stage": stage,
        "day_code": DAY_CODES[d.weekday()],
        "is_recess": is_recess,
    }


def make_week_slots(*, stage="primary", hours_per_day=None, include_recess=False):
    """Return 5 days × len(hours_per_day) non-recess slots, optionally with recess.

    Default hours [9, 10, 11, 13] gives 20 slots covering a PRIMARY-like day.
    """
    if hours_per_day is None:
        hours_per_day = [9, 10, 11, 13]
    slots = []
    for day in range(5):
        for hour in hours_per_day:
            slots.append(make_slot(day_offset=day, hour=hour, stage=stage))
        if include_recess:
            slots.append(
                make_slot(
                    day_offset=day,
                    hour=11,
                    minute=30,
                    duration_minutes=30,
                    stage=stage,
                    is_recess=True,
                )
            )
    return slots


# ---------------------------------------------------------------------------
# Entity stubs (duck-typed, no ORM)
# ---------------------------------------------------------------------------


def make_teacher_stub(
    *,
    id=1,
    name="Teacher A",
    max_weekly_hours=20,
    max_weekly_minutes=0,
    weekly_hours_exact=False,
    time_preferences=None,
):
    """Return a SimpleNamespace mimicking a Teacher model instance."""
    return SimpleNamespace(
        id=id,
        name=name,
        max_weekly_hours=max_weekly_hours,
        max_weekly_minutes=max_weekly_minutes,
        weekly_hours_exact=weekly_hours_exact,
        time_preferences=time_preferences or {},
    )


def make_group_stub(*, id=1, name="1A", stage="primary"):
    """Return a SimpleNamespace mimicking a Group model instance.

    stage must be a GroupEducationalStage value (lowercase) so that
    canonical_group_stage() maps it correctly.
    """
    return SimpleNamespace(id=id, name=name, stage=stage)


def make_subject_stub(
    *,
    id=1,
    name="Math",
    teacher_id=1,
    group_id=1,
    time_preferences=None,
):
    """Return a SimpleNamespace mimicking a Subject model instance."""
    return SimpleNamespace(
        id=id,
        name=name,
        teacher_id=teacher_id,
        group_id=group_id,
        time_preferences=time_preferences or {},
    )


def make_classroom_stub(*, id=1, name="Aula 1A", team_id=1):
    """Return a SimpleNamespace mimicking a Classroom model instance."""
    return SimpleNamespace(id=id, name=name, team_id=team_id)


# ---------------------------------------------------------------------------
# Session dict factory
# ---------------------------------------------------------------------------


def make_session(
    *,
    teacher_id=1,
    teacher=None,
    group=None,
    subject=None,
    allowed_classroom_ids=None,
):
    """Return a session dict in the shape consumed by all algorithm functions.

    If teacher/group/subject are omitted, default stubs are created so callers
    only have to specify what their test cares about.
    """
    if teacher is None:
        teacher = make_teacher_stub(id=teacher_id)
    if group is None:
        group = make_group_stub()
    if subject is None:
        subject = make_subject_stub()
    return {
        "teacher_id": teacher.id,
        "teacher": teacher,
        "group": group,
        "subject": subject,
        "allowed_classroom_ids": allowed_classroom_ids,
    }
