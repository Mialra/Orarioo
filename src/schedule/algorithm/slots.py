"""Weekly timetable slot utilities for the schedule generation algorithm.

Defines the allowed time windows per educational stage and the functions
to build, index and compare slots within the CP-SAT model.
"""

from datetime import datetime, time, timedelta

from django.utils import timezone

from common.stages import EducationalStage, canonical_educational_stage

DAY_CODE_BY_WEEKDAY = {
    0: "MON",
    1: "TUE",
    2: "WED",
    3: "THU",
    4: "FRI",
}

STAGE_PRESCHOOL = EducationalStage.PRESCHOOL
STAGE_PRIMARY = EducationalStage.PRIMARY
STAGE_SECONDARY = EducationalStage.SECONDARY
STAGE_ALEVELS = EducationalStage.ALEVELS
BASE_SESSION_DURATION_MINUTES = 60

# Default time windows per stage. Each tuple is (start, end, is_recess).
STAGE_SLOT_WINDOWS = {
    # Infantil: 9:00-14:00 with breaks 10:30-11:00 and 13:30-14:00.
    STAGE_PRESCHOOL: [
        (time(hour=9, minute=0), time(hour=10, minute=0), False),
        (time(hour=10, minute=0), time(hour=10, minute=30), False),
        (time(hour=10, minute=30), time(hour=11, minute=0), True),
        (time(hour=11, minute=0), time(hour=12, minute=0), False),
        (time(hour=12, minute=0), time(hour=13, minute=0), False),
        (time(hour=13, minute=0), time(hour=13, minute=30), False),
        (time(hour=13, minute=30), time(hour=14, minute=0), True),
    ],
    # Primaria: 9:00-14:00 with break 11:30-12:00.
    STAGE_PRIMARY: [
        (time(hour=9, minute=0), time(hour=10, minute=0), False),
        (time(hour=10, minute=0), time(hour=11, minute=0), False),
        (time(hour=11, minute=0), time(hour=11, minute=30), False),
        (time(hour=11, minute=30), time(hour=12, minute=0), True),
        (time(hour=12, minute=0), time(hour=13, minute=0), False),
        (time(hour=13, minute=0), time(hour=14, minute=0), False),
    ],
    # ESO: 8:00-14:30 with break 11:00-11:30.
    STAGE_SECONDARY: [
        (time(hour=8, minute=0), time(hour=9, minute=0), False),
        (time(hour=9, minute=0), time(hour=10, minute=0), False),
        (time(hour=10, minute=0), time(hour=11, minute=0), False),
        (time(hour=11, minute=0), time(hour=11, minute=30), True),
        (time(hour=11, minute=30), time(hour=12, minute=30), False),
        (time(hour=12, minute=30), time(hour=13, minute=30), False),
        (time(hour=13, minute=30), time(hour=14, minute=30), False),
    ],
    # Bachillerato: same defaults as ESO.
    STAGE_ALEVELS: [
        (time(hour=8, minute=0), time(hour=9, minute=0), False),
        (time(hour=9, minute=0), time(hour=10, minute=0), False),
        (time(hour=10, minute=0), time(hour=11, minute=0), False),
        (time(hour=11, minute=0), time(hour=11, minute=30), True),
        (time(hour=11, minute=30), time(hour=12, minute=30), False),
        (time(hour=12, minute=30), time(hour=13, minute=30), False),
        (time(hour=13, minute=30), time(hour=14, minute=30), False),
    ],
}


def _slot_start(slot):
    """Extract the start instant from a slot, whether dict or datetime.
    Input: slot - dict with key 'start', or a datetime directly
    Output: start datetime of the slot
    """
    return slot["start"] if isinstance(slot, dict) else slot


def _slot_end(slot):
    """Extract the end instant from a slot, whether dict or datetime.
    Input: slot - dict with key 'end', or a datetime (in which case 1 hour is added)
    Output: end datetime of the slot
    """
    if isinstance(slot, dict):
        return slot["end"]
    return slot + timedelta(hours=1)


def _slot_stage(slot):
    """Extract the educational stage code from a slot dict, or None if not applicable.
    Input: slot - dict with optional key 'stage', or any other value
    Output: stage code string, or None
    """
    if isinstance(slot, dict):
        return slot.get("stage")
    return None


def _normalize_stage_code(*, group_stage=None, subject_stage=None):
    """Map a group or subject stage to the algorithm's internal stage code.
    Input: group_stage - EducationalStage value from the group, or None;
           subject_stage - EducationalStage value from the subject, or None
    Output: one of STAGE_PRESCHOOL, STAGE_PRIMARY, STAGE_SECONDARY;
            STAGE_PRIMARY as fallback when neither matches
    """
    return canonical_educational_stage(
        group_stage=group_stage,
        subject_stage=subject_stage,
        default=STAGE_PRIMARY,
    )


def session_stage_code(*, session):
    """Determine the educational stage code for a session from its group or subject.
    Input: session - dict with optional keys 'group' and 'subject'
    Output: stage code (STAGE_PRESCHOOL, STAGE_PRIMARY or STAGE_SECONDARY)
    """
    group = session.get("group")
    subject = session.get("subject")
    return _normalize_stage_code(
        group_stage=getattr(group, "stage", None),
        subject_stage=getattr(subject, "stage", None),
    )


def build_weekly_slots(*, stage_slot_windows=None):
    """Build timetable slots for the next working week (Monday to Friday).
    Input: stage_slot_windows - optional dict {stage_code: [(start, end, is_recess), ...]};
           defaults to STAGE_SLOT_WINDOWS when None
    Output: list of dicts with keys 'start', 'end', 'stage', 'day_code', 'is_recess'
    """
    windows = stage_slot_windows if stage_slot_windows is not None else STAGE_SLOT_WINDOWS

    now = timezone.localtime()
    days_until_next_monday = (7 - now.weekday()) % 7
    if days_until_next_monday == 0:
        days_until_next_monday = 7

    start_day = now.date() + timedelta(days=days_until_next_monday)
    day_cursor = start_day
    slots = []

    for _ in range(5):
        day_code = DAY_CODE_BY_WEEKDAY.get(day_cursor.weekday())
        for stage_code, stage_windows in windows.items():
            for entry in stage_windows:
                start_t, end_t, is_recess = entry
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
                        "is_recess": is_recess,
                    }
                )
        day_cursor += timedelta(days=1)

    return slots


def build_slot_day_index(*, slots):
    """Build an index mapping each slot index to its day index within the generated week.
    Input: slots - list of slots produced by build_weekly_slots
    Output: dict {slot_idx: day_idx} where day_idx is the zero-based position of the day sorted by date
    """
    day_index_by_slot = {}
    ordered_days = sorted({_slot_start(slot).date() for slot in slots})

    for day_idx, day in enumerate(ordered_days):
        for slot_idx, slot in enumerate(slots):
            if _slot_start(slot).date() == day:
                day_index_by_slot[slot_idx] = day_idx

    return day_index_by_slot


def slot_preference_key_from_datetime(*, slot):
    """Build a stable time-preference key for a slot datetime.
    Input: slot - slot dict or datetime; must fall on a Monday-Friday
    Output: string in format 'DDD_HH:MM' (e.g. 'MON_09:00'), or None for weekend days
    """
    slot_dt = _slot_start(slot)
    day_code = DAY_CODE_BY_WEEKDAY.get(slot_dt.weekday())
    if day_code is None:
        return None
    return f"{day_code}_{slot_dt:%H:%M}"


def slot_instance_key(*, slot):
    """Generate a unique, stable key identifying a slot by stage, day and times.
    Input: slot - dict with keys 'start', 'end' and optionally 'stage'
    Output: string in format 'STAGE_DAY_HH:MM_HH:MM' (e.g. 'PRIMARY_MON_09:00_10:00')
    """
    slot_start = _slot_start(slot)
    slot_end = _slot_end(slot)
    stage = _slot_stage(slot) or "GENERIC"
    day_code = DAY_CODE_BY_WEEKDAY.get(slot_start.weekday(), "UNK")
    return f"{stage}_{day_code}_{slot_start:%H:%M}_{slot_end:%H:%M}"


def build_slot_instance_index(*, slots):
    """Build an index of slot_idx → slot_instance_key for all slots.
    Input: slots - list of slots
    Output: dict {slot_idx: slot_instance_key}
    """
    return {
        slot_idx: slot_instance_key(slot=slot) for slot_idx, slot in enumerate(slots)
    }


def build_stage_allowed_slot_index(*, slots):
    """Build an index of stage → set of allowed slot indices for that stage.
    Input: slots - list of slots with a 'stage' key
    Output: dict {STAGE_CODE: set(slot_idx)} with entries for all three stages
    """
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


def build_real_time_intervals(*, slots, slot_indices=None):
    """Split each day into atomic real-time intervals and map overlapping slots.

    Enables detection of overlaps between slots of different duration on the same day.
    Input: slots - full list of slots;
           slot_indices - subset of indices to consider, or None for all
    Output: list of dicts with keys 'day_idx', 'start', 'end', 'slot_indices'
    """
    day_index_by_slot = build_slot_day_index(slots=slots)
    relevant_slot_indices = (
        list(range(len(slots))) if slot_indices is None else list(slot_indices)
    )
    slot_indices_by_day = {}

    for slot_idx in relevant_slot_indices:
        day_idx = day_index_by_slot.get(slot_idx)
        if day_idx is None:
            continue
        slot_indices_by_day.setdefault(day_idx, []).append(slot_idx)

    intervals = []
    for day_idx, day_slot_indices in slot_indices_by_day.items():
        boundaries = set()
        for slot_idx in day_slot_indices:
            start_time, end_time = slot_time_bounds(slot=slots[slot_idx])
            boundaries.add(start_time)
            boundaries.add(end_time)

        ordered_boundaries = sorted(boundaries)
        for start_time, end_time in zip(ordered_boundaries, ordered_boundaries[1:]):
            interval_slot = {"start": start_time, "end": end_time}
            overlapping_slot_indices = [
                slot_idx
                for slot_idx in day_slot_indices
                if slot_overlaps(
                    left_slot=slots[slot_idx],
                    right_slot=interval_slot,
                )
            ]
            if not overlapping_slot_indices:
                continue
            intervals.append(
                {
                    "day_idx": day_idx,
                    "start": start_time,
                    "end": end_time,
                    "slot_indices": overlapping_slot_indices,
                }
            )

    return intervals


def slot_overlaps(*, left_slot, right_slot):
    """Check whether two slots overlap in time (strict overlap).
    Input: left_slot - left slot (dict or datetime); right_slot - right slot
    Output: True if the intervals overlap, False otherwise
    """
    left_start = _slot_start(left_slot)
    left_end = _slot_end(left_slot)
    right_start = _slot_start(right_slot)
    right_end = _slot_end(right_slot)
    return left_start < right_end and right_start < left_end


def slot_time_bounds(*, slot):
    """Return the (start, end) tuple for a slot.
    Input: slot - slot dict or datetime
    Output: tuple (datetime_start, datetime_end)
    """
    return _slot_start(slot), _slot_end(slot)


def build_slot_preference_index(*, slots):
    """Build an index of slot_idx → time-preference key (e.g. 'MON_09:00').
    Input: slots - list of slots
    Output: dict {slot_idx: preference_key} excluding weekend slots and recess slots
    """
    preference_index = {}
    for slot_idx, slot in enumerate(slots):
        if isinstance(slot, dict) and slot.get("is_recess"):
            continue
        key = slot_preference_key_from_datetime(slot=slot)
        if key is not None:
            preference_index[slot_idx] = key
    return preference_index


def _parse_hhmm(value):
    """Parse a 'HH:MM' string to a time object.
    Input: value - string in 'HH:MM' format
    Output: datetime.time instance
    """
    h, m = value.split(":")
    return time(int(h), int(m))


def build_windows_from_stage_config(cfg):
    """Generate (start_t, end_t, is_recess) tuples from a stage config dict.

    Slots are produced independently within each break-separated segment so that
    break boundaries never create partial orphan slots.  For example, a secondary
    day from 08:00 to 14:30 with a break at 11:00-11:30 yields three full-hour
    slots before the break (08:00-11:00) and three after (11:30-14:30).

    Also accepts the legacy single-break keys break_start / break_end for backward compat.

    Input: cfg - dict with keys start_time, end_time, session_duration (int, minutes),
                 and optional breaks (list of {start: HH:MM, end: HH:MM})
    Output: list of (time, time, bool) tuples; bool is True for the recess slot
    """
    from datetime import date as _date

    base = _date.today()
    start_t = _parse_hhmm(cfg["start_time"])
    end_t = _parse_hhmm(cfg["end_time"])
    dur = timedelta(minutes=BASE_SESSION_DURATION_MINUTES)

    # Normalise breaks: support both new list format and legacy single-break keys
    raw_breaks = cfg.get("breaks") or []
    if not raw_breaks and cfg.get("break_start") and cfg.get("break_end"):
        raw_breaks = [{"start": cfg["break_start"], "end": cfg["break_end"]}]

    parsed_breaks = []
    for b in raw_breaks:
        bs_t = _parse_hhmm(b["start"])
        be_t = _parse_hhmm(b["end"])
        parsed_breaks.append(
            (datetime.combine(base, bs_t), datetime.combine(base, be_t))
        )
    parsed_breaks.sort(key=lambda x: x[0])

    start_dt = datetime.combine(base, start_t)
    end_dt = datetime.combine(base, end_t)

    # Alternate session segments and recess segments, computing slots within each
    # session segment independently so break boundaries never create partial slots.
    segment_start = start_dt
    result = []
    for bs_dt, be_dt in parsed_breaks:
        seg_end = bs_dt
        cursor = segment_start
        while cursor < seg_end:
            slot_end = min(cursor + dur, seg_end)
            result.append((cursor.time(), slot_end.time(), False))
            cursor = slot_end
        result.append((bs_dt.time(), be_dt.time(), True))
        segment_start = be_dt

    cursor = segment_start
    while cursor < end_dt:
        slot_end = min(cursor + dur, end_dt)
        result.append((cursor.time(), slot_end.time(), False))
        cursor = slot_end

    return result


def parse_schedule_config_to_slot_windows(schedule_config):
    """Convert a team's schedule_config JSON to the STAGE_SLOT_WINDOWS format.

    Input: schedule_config - dict {stage_code: {start_time, end_time, ...}}
           as stored in CollaborationTeam.schedule_config
    Output: dict {stage_code: [(start_t, end_t, is_recess), ...]} or None when empty
    """
    if not schedule_config:
        return None
    return {
        stage: build_windows_from_stage_config(cfg)
        for stage, cfg in schedule_config.items()
    }
