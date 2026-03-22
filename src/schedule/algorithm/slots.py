from datetime import datetime, time, timedelta

from django.utils import timezone

from group.models import EducationalStage as GroupEducationalStage
from subject.models import EducationalStage as SubjectEducationalStage

DAY_CODE_BY_WEEKDAY = {
    0: "MON",
    1: "TUE",
    2: "WED",
    3: "THU",
    4: "FRI",
}

STAGE_PRESCHOOL = "PRESCHOOL"
STAGE_PRIMARY = "PRIMARY"
STAGE_SECONDARY = "SECONDARY"

STAGE_SLOT_WINDOWS = {
    # Infantil: 9:00-14:00 with breaks 10:30-11:00 and 13:30-14:00.
    # We model 5 daily instructional periods.
    STAGE_PRESCHOOL: [
        (time(hour=9, minute=0), time(hour=10, minute=0)),
        (time(hour=10, minute=0), time(hour=10, minute=30)),
        (time(hour=11, minute=0), time(hour=12, minute=0)),
        (time(hour=12, minute=0), time(hour=13, minute=0)),
        (time(hour=13, minute=0), time(hour=13, minute=30)),
    ],
    # Primaria: 9:00-14:00 with break 11:30-12:00.
    STAGE_PRIMARY: [
        (time(hour=9, minute=0), time(hour=10, minute=0)),
        (time(hour=10, minute=0), time(hour=11, minute=0)),
        (time(hour=11, minute=0), time(hour=11, minute=30)),
        (time(hour=12, minute=0), time(hour=13, minute=0)),
        (time(hour=13, minute=0), time(hour=14, minute=0)),
    ],
    # ESO: 8:00-14:30 with break 11:00-11:30.
    STAGE_SECONDARY: [
        (time(hour=8, minute=0), time(hour=9, minute=0)),
        (time(hour=9, minute=0), time(hour=10, minute=0)),
        (time(hour=10, minute=0), time(hour=11, minute=0)),
        (time(hour=11, minute=30), time(hour=12, minute=30)),
        (time(hour=12, minute=30), time(hour=13, minute=30)),
        (time(hour=13, minute=30), time(hour=14, minute=30)),
    ],
}


def _slot_start(slot):
    return slot["start"] if isinstance(slot, dict) else slot


def _slot_end(slot):
    if isinstance(slot, dict):
        return slot["end"]
    return slot + timedelta(hours=1)


def _slot_stage(slot):
    if isinstance(slot, dict):
        return slot.get("stage")
    return None


def _normalize_stage_code(*, group_stage=None, subject_stage=None):
    if group_stage == GroupEducationalStage.PRESCHOOL:
        return STAGE_PRESCHOOL
    if group_stage == GroupEducationalStage.PRIMARY:
        return STAGE_PRIMARY
    if group_stage == GroupEducationalStage.SECONDARY:
        return STAGE_SECONDARY

    if subject_stage == SubjectEducationalStage.PRESCHOOL:
        return STAGE_PRESCHOOL
    if subject_stage == SubjectEducationalStage.PRIMARY:
        return STAGE_PRIMARY
    if subject_stage == SubjectEducationalStage.SECONDARY:
        return STAGE_SECONDARY

    return STAGE_PRIMARY


def session_stage_code(*, session):
    group = session.get("group")
    subject = session.get("subject")
    return _normalize_stage_code(
        group_stage=getattr(group, "stage", None),
        subject_stage=getattr(subject, "stage", None),
    )


def build_weekly_slots():
    """Build one Monday-Friday timetable with stage-specific windows and breaks."""
    now = timezone.localtime()
    days_until_next_monday = (7 - now.weekday()) % 7
    if days_until_next_monday == 0:
        days_until_next_monday = 7

    start_day = now.date() + timedelta(days=days_until_next_monday)
    day_cursor = start_day
    slots = []

    for _ in range(5):
        day_code = DAY_CODE_BY_WEEKDAY.get(day_cursor.weekday())
        for stage_code, windows in STAGE_SLOT_WINDOWS.items():
            for start_t, end_t in windows:
                start_dt = timezone.make_aware(
                    datetime.combine(day_cursor, start_t),
                    timezone.get_current_timezone(),
                )
                end_dt = timezone.make_aware(
                    datetime.combine(day_cursor, end_t),
                    timezone.get_current_timezone(),
                )
                slots.append(
                    {
                        "start": start_dt,
                        "end": end_dt,
                        "stage": stage_code,
                        "day_code": day_code,
                    }
                )
        day_cursor += timedelta(days=1)

    return slots


def build_slot_day_index(*, slots):
    """Map each slot index to its day index in the generated week."""
    day_index_by_slot = {}
    ordered_days = sorted({_slot_start(slot).date() for slot in slots})

    for day_idx, day in enumerate(ordered_days):
        for slot_idx, slot in enumerate(slots):
            if _slot_start(slot).date() == day:
                day_index_by_slot[slot_idx] = day_idx

    return day_index_by_slot


def slot_preference_key_from_datetime(*, slot):
    """Build a stable preference key for one datetime slot."""
    slot_dt = _slot_start(slot)
    day_code = DAY_CODE_BY_WEEKDAY.get(slot_dt.weekday())
    if day_code is None:
        return None
    return f"{day_code}_{slot_dt:%H:%M}"


def slot_instance_key(*, slot):
    slot_start = _slot_start(slot)
    slot_end = _slot_end(slot)
    stage = _slot_stage(slot) or "GENERIC"
    day_code = DAY_CODE_BY_WEEKDAY.get(slot_start.weekday(), "UNK")
    return f"{stage}_{day_code}_{slot_start:%H:%M}_{slot_end:%H:%M}"


def build_slot_instance_index(*, slots):
    return {
        slot_idx: slot_instance_key(slot=slot) for slot_idx, slot in enumerate(slots)
    }


def build_stage_allowed_slot_index(*, slots):
    allowed = {
        STAGE_PRESCHOOL: set(),
        STAGE_PRIMARY: set(),
        STAGE_SECONDARY: set(),
    }
    for slot_idx, slot in enumerate(slots):
        stage = _slot_stage(slot)
        if stage in allowed:
            allowed[stage].add(slot_idx)
    return allowed


def slot_overlaps(*, left_slot, right_slot):
    left_start = _slot_start(left_slot)
    left_end = _slot_end(left_slot)
    right_start = _slot_start(right_slot)
    right_end = _slot_end(right_slot)
    return left_start < right_end and right_start < left_end


def slot_time_bounds(*, slot):
    return _slot_start(slot), _slot_end(slot)


def build_slot_preference_index(*, slots):
    """Map each slot index to its preference key (e.g. MON_08:30)."""
    preference_index = {}
    for slot_idx, slot in enumerate(slots):
        key = slot_preference_key_from_datetime(slot=slot)
        if key is not None:
            preference_index[slot_idx] = key
    return preference_index
