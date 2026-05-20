"""Hard constraints for the CP-SAT schedule generation model.

Provides capacity validation (pre-solver) and model-level constraints that
must be satisfied for a schedule to be considered feasible.
"""

from common.stages import EducationalStage, canonical_group_stage
from schedule.algorithm.errors import ScheduleCapacityError, ScheduleGenerationError
from schedule.algorithm.slots import (
    build_slot_day_index,
    build_slot_preference_index,
    build_stage_allowed_slot_index,
    session_stage_code,
    slot_time_bounds,
)
from subject.models import SubjectTimePreferenceState
from teacher.models import TeacherTimePreferenceState

PRESCHOOL_AND_PRIMARY_STAGES = {
    EducationalStage.PRESCHOOL,
    EducationalStage.PRIMARY,
}


def group_weekly_limit(group):
    """Return the maximum number of weekly sessions allowed for a group.
    Input: group - Group model instance with a 'stage' attribute
    Output: integer weekly session limit (25 for preschool/primary, 30 for secondary)
    """
    if canonical_group_stage(group.stage) in PRESCHOOL_AND_PRIMARY_STAGES:
        return 25
    return 30


def group_daily_limit(group):
    """Return the maximum number of daily sessions allowed for a group.
    Input: group - Group model instance with a 'stage' attribute
    Output: integer daily session limit (5 for preschool/primary, 6 for secondary)
    """
    if canonical_group_stage(group.stage) in PRESCHOOL_AND_PRIMARY_STAGES:
        return 5
    return 6


def validate_group_and_teacher_capacity(*, sessions, slots):
    """Validate that groups and teachers do not exceed their capacity before solving.
    Input: sessions - list of session dicts;
           slots - list of slot dicts from build_weekly_slots
    Output: None; raises ScheduleGenerationError or ScheduleCapacityError on violation
    """
    sessions_by_group, sessions_by_teacher = _build_capacity_state(sessions=sessions)
    _validate_group_slot_capacity(
        sessions_by_group=sessions_by_group,
        slot_count=len(slots),
    )
    _validate_group_weekly_capacity(sessions_by_group=sessions_by_group)
    _validate_teacher_weekly_capacity(sessions_by_teacher=sessions_by_teacher)


def _build_capacity_state(*, sessions):
    """Build per-group and per-teacher capacity accumulators from a session list.
    Input: sessions - list of session dicts
    Output: tuple (sessions_by_group, sessions_by_teacher) — dicts keyed by id
    """
    sessions_by_group = {}
    sessions_by_teacher = {}

    for session in sessions:
        _accumulate_group_capacity(session=session, sessions_by_group=sessions_by_group)
        _accumulate_teacher_capacity(
            session=session,
            sessions_by_teacher=sessions_by_teacher,
        )

    return sessions_by_group, sessions_by_teacher


def _accumulate_group_capacity(*, session, sessions_by_group):
    """Increment the assigned-hours counter for the group of a session.
    Input: session - session dict; sessions_by_group - mutable capacity dict
    Output: None; side-effect: updates sessions_by_group in place
    """
    group = session.get("group")
    group_key = getattr(group, "id", None)
    if group_key is None:
        return

    group_state = sessions_by_group.setdefault(
        group_key,
        {
            "name": group.name,
            "weekly_limit": group_weekly_limit(group),
            "assigned_hours": 0,
        },
    )
    group_state["assigned_hours"] += 1


def _accumulate_teacher_capacity(*, session, sessions_by_teacher):
    """Increment the assigned-hours counter for the teacher of a session.
    Input: session - session dict; sessions_by_teacher - mutable capacity dict
    Output: None; side-effect: updates sessions_by_teacher in place
    """
    teacher = session.get("teacher")
    if teacher is None:
        return

    teacher_state = sessions_by_teacher.setdefault(
        teacher.id,
        {
            "name": teacher.name,
            "max_weekly_hours": teacher.max_weekly_hours
            + teacher.max_weekly_minutes / 60.0,
            "assigned_hours": 0,
        },
    )
    teacher_state["assigned_hours"] += 1


def _validate_group_slot_capacity(*, sessions_by_group, slot_count):
    """Raise if any group has more sessions than available slots.
    Input: sessions_by_group - capacity dict; slot_count - total available slots
    Output: None; raises ScheduleGenerationError if capacity is exceeded
    """
    if any(
        group_state["assigned_hours"] > slot_count
        for group_state in sessions_by_group.values()
    ):
        raise ScheduleGenerationError(
            "Not enough available slots to place all sessions for at least one group.",
            code="GROUP_SLOT_CAPACITY_EXCEEDED",
            suggestions=[
                "Reduce weekly hours for one or more groups.",
                "Review unavailable time preferences that may be removing too many slots.",
            ],
        )


def _validate_group_weekly_capacity(*, sessions_by_group):
    """Raise if any group exceeds its weekly session limit.
    Input: sessions_by_group - capacity dict from _build_capacity_state
    Output: None; raises ScheduleCapacityError for the first offending group
    """
    for group_state in sessions_by_group.values():
        if group_state["assigned_hours"] > group_state["weekly_limit"]:
            raise ScheduleCapacityError(
                resource_type="group",
                resource_name=group_state["name"],
                assigned=group_state["assigned_hours"],
                capacity=group_state["weekly_limit"],
                suggestions=[
                    "Reduce the weekly hours assigned to this group.",
                    "Split the load across additional groups or subjects if possible.",
                ],
            )


def _validate_teacher_weekly_capacity(*, sessions_by_teacher):
    """Raise if any teacher exceeds their maximum weekly hours.
    Input: sessions_by_teacher - capacity dict from _build_capacity_state
    Output: None; raises ScheduleCapacityError for the first offending teacher
    """
    for teacher_state in sessions_by_teacher.values():
        if teacher_state["assigned_hours"] > teacher_state["max_weekly_hours"]:
            raise ScheduleCapacityError(
                resource_type="teacher",
                resource_name=teacher_state["name"],
                assigned=_format_hours(teacher_state["assigned_hours"]),
                capacity=teacher_state["max_weekly_hours"],
                suggestions=[
                    "Increase the teacher's maximum weekly hours.",
                    "Reassign part of the workload to another teacher.",
                ],
            )


def _format_hours(value):
    """Format a numeric hours value as a compact string without trailing zeros.
    Input: value - numeric hours (int or float)
    Output: string representation (e.g. '3', '2.5', '1.25')
    """
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def add_exactly_one_slot_constraints(*, model, x, session_count, slot_count):
    """Add constraints ensuring each session is assigned to exactly one slot.

    No-op in the current implementation — slot uniqueness is enforced in
    assignment.py via the y-variable formulation. Kept for API compatibility.
    Input: model - CP-SAT CpModel; x - slot decision variables; session_count, slot_count - sizes
    Output: None; side-effect: may add constraints to model
    """
    for s_idx in range(session_count):
        model.Add(sum(x[(s_idx, p_idx)] for p_idx in range(slot_count)) == 1)


def _session_resource_id(*, session, resource_key):
    """Extract the resource identifier from a session for a given resource key.
    Input: session - session dict; resource_key - 'group_id' or 'teacher_id'
    Output: the resource id, or None if absent
    """
    if resource_key == "group_id":
        group = session.get("group")
        return getattr(group, "id", None)
    return session.get(resource_key)


def add_resource_non_overlap_constraints(
    *, model, x, sessions, slot_count, resource_key
):
    """No-op stub kept for API compatibility.

    Non-overlap is enforced via interval constraints in assignment.py where
    slot time bounds are available.
    Input: model, x, sessions, slot_count, resource_key - standard constraint arguments
    Output: None
    """
    del slot_count
    resource_to_sessions = {}

    for idx, session in enumerate(sessions):
        resource_id = _session_resource_id(session=session, resource_key=resource_key)
        if resource_id is None:
            continue
        resource_to_sessions.setdefault(resource_id, []).append(idx)

    for resource_sessions in resource_to_sessions.values():
        if not resource_sessions:
            continue


def add_recess_slot_hard_constraints(*, model, x, sessions, slots):
    """Forbid any session from being placed in recess slots.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts
    Output: None; side-effect: adds x[s,p]==0 for every (session, recess_slot) pair
    """
    for p_idx, slot in enumerate(slots):
        if slot.get("is_recess"):
            for s_idx in range(len(sessions)):
                if (s_idx, p_idx) in x:
                    model.Add(x[(s_idx, p_idx)] == 0)


def add_stage_slot_hard_constraints(*, model, x, sessions, slots):
    """Forbid each session from being placed in slots outside its stage's allowed windows.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts
    Output: None; side-effect: adds x[s,p]==0 constraints for disallowed (session, slot) pairs
    """
    allowed_slots_by_stage = build_stage_allowed_slot_index(slots=slots)

    for s_idx, session in enumerate(sessions):
        stage_code = session_stage_code(session=session)
        allowed_slots = allowed_slots_by_stage.get(stage_code, set())
        for p_idx in range(len(slots)):
            if p_idx not in allowed_slots:
                if (s_idx, p_idx) in x:
                    model.Add(x[(s_idx, p_idx)] == 0)


def add_group_daily_capacity_constraints(*, model, x, sessions, slots):
    """Enforce that no group exceeds its stage-based daily session limit.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts
    Output: None; side-effect: adds daily sum constraints per group per day
    """
    day_index_by_slot = build_slot_day_index(slots=slots)
    day_slots_by_index = {}
    for slot_idx, day_idx in day_index_by_slot.items():
        day_slots_by_index.setdefault(day_idx, []).append(slot_idx)
    group_to_sessions = {}

    for s_idx, session in enumerate(sessions):
        group = session.get("group")
        if group is None:
            continue
        group_to_sessions.setdefault(group.id, {"group": group, "sessions": []})[
            "sessions"
        ].append(s_idx)

    for group_state in group_to_sessions.values():
        group = group_state["group"]
        resource_sessions = group_state["sessions"]
        daily_limit = group_daily_limit(group)

        for day_slots in day_slots_by_index.values():
            model.Add(
                sum(
                    x[(s_idx, p_idx)]
                    for s_idx in resource_sessions
                    for p_idx in day_slots
                    if (s_idx, p_idx) in x
                )
                <= daily_limit
            )


def add_group_no_intraday_gap_constraints(*, model, x, sessions, slots):
    """Forbid intra-day gaps inside each group's timetable block (F-30).
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts
    Output: None; side-effect: adds triplet BoolOr constraints to model
    """
    slots_by_day = _build_slots_by_day(slots=slots)
    group_to_sessions = _build_group_session_index(sessions=sessions)
    allowed_slots_by_stage = build_stage_allowed_slot_index(slots=slots)

    for group_id, group_sessions in group_to_sessions.items():
        group_stage = session_stage_code(session=sessions[group_sessions[0]])
        stage_allowed_slots = allowed_slots_by_stage.get(group_stage, set())
        for day_idx, day_slot_list in slots_by_day.items():
            filtered_day_slots = [
                slot_idx
                for slot_idx in day_slot_list
                if slot_idx in stage_allowed_slots
                and not slots[slot_idx].get("is_recess")
            ]
            if len(filtered_day_slots) < 3:
                continue
            occupancy_by_slot = _build_group_day_occupancy_vars(
                model=model,
                x=x,
                group_id=group_id,
                group_sessions=group_sessions,
                day_idx=day_idx,
                day_slot_list=filtered_day_slots,
            )
            _add_no_gap_triplets(
                model=model,
                occupancy_by_slot=occupancy_by_slot,
                day_slot_list=filtered_day_slots,
            )


def _build_slots_by_day(*, slots):
    """Group slot indices by day index, sorted by start time.
    Input: slots - list of slot dicts
    Output: dict {day_idx: [slot_idx, ...]} sorted by slot start time within each day
    """
    slot_day_index = build_slot_day_index(slots=slots)
    slots_by_day = {}
    for slot_idx, day_idx in slot_day_index.items():
        slots_by_day.setdefault(day_idx, []).append(slot_idx)
    for day_idx in slots_by_day:
        slots_by_day[day_idx].sort(key=lambda idx: slot_time_bounds(slot=slots[idx])[0])
    return slots_by_day


def _build_group_session_index(*, sessions):
    """Build an index of group_id → list of session indices for that group.
    Input: sessions - list of session dicts
    Output: dict {group_id: [session_idx, ...]}
    """
    group_to_sessions = {}
    for s_idx, session in enumerate(sessions):
        group = session.get("group")
        group_id = getattr(group, "id", None)
        if group_id is not None:
            group_to_sessions.setdefault(group_id, []).append(s_idx)
    return group_to_sessions


def _build_group_day_occupancy_vars(
    *, model, x, group_id, group_sessions, day_idx, day_slot_list
):
    """Create BoolVar occupancy indicators for each slot in a group's day.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           group_id, group_sessions, day_idx - group/day identifiers;
           day_slot_list - ordered list of slot indices for this day
    Output: dict {slot_idx: BoolVar} where each var is 1 iff the group occupies that slot
    """
    occupancy_by_slot = {}
    for slot_idx in day_slot_list:
        occupied = model.NewBoolVar(f"g{group_id}_d{day_idx}_p{slot_idx}_occ")
        model.Add(
            sum(
                x[(s_idx, slot_idx)]
                for s_idx in group_sessions
                if (s_idx, slot_idx) in x
            )
            == occupied
        )
        occupancy_by_slot[slot_idx] = occupied
    return occupancy_by_slot


def _add_no_gap_triplets(*, model, occupancy_by_slot, day_slot_list):
    """Add BoolOr triplet constraints to forbid isolated gaps between occupied slots.
    Input: model - CP-SAT CpModel;
           occupancy_by_slot - dict {slot_idx: BoolVar};
           day_slot_list - ordered slot indices for the day
    Output: None; side-effect: adds constraints to model
    """
    for left_pos, left_slot in enumerate(day_slot_list[:-2]):
        for middle_pos in range(left_pos + 1, len(day_slot_list) - 1):
            middle_slot = day_slot_list[middle_pos]
            for right_slot in day_slot_list[middle_pos + 1 :]:
                model.AddBoolOr(
                    [
                        occupancy_by_slot[left_slot].Not(),
                        occupancy_by_slot[middle_slot],
                        occupancy_by_slot[right_slot].Not(),
                    ]
                )


def _preference_state_for_entity(*, entity, slot_preference_key, state_enum, default):
    """Look up a time-preference state for an entity at a given slot key.
    Input: entity - model instance with optional 'time_preferences' dict;
           slot_preference_key - preference key string (e.g. 'MON_09:00');
           state_enum - enum class with a 'values' attribute;
           default - value to return when no preference is set
    Output: the preference state value, or default if not found
    """
    if entity is None:
        return default

    preferences = getattr(entity, "time_preferences", None) or {}
    state = preferences.get(slot_preference_key)
    if state in state_enum.values:
        return state
    return default


def session_preference_state(*, session, slot_preference_key):
    """Return the subject's time-preference state for a given slot key.
    Input: session - session dict with optional 'subject' key;
           slot_preference_key - preference key string (e.g. 'MON_09:00')
    Output: SubjectTimePreferenceState value; AVAILABLE if not set
    """
    subject = session.get("subject")
    return _preference_state_for_entity(
        entity=subject,
        slot_preference_key=slot_preference_key,
        state_enum=SubjectTimePreferenceState,
        default=SubjectTimePreferenceState.AVAILABLE,
    )


def teacher_preference_state(*, session, slot_preference_key):
    """Return the teacher's time-preference state for a given slot key.
    Input: session - session dict with optional 'teacher' key;
           slot_preference_key - preference key string (e.g. 'MON_09:00')
    Output: TeacherTimePreferenceState value; AVAILABLE if not set
    """
    teacher = session.get("teacher")
    return _preference_state_for_entity(
        entity=teacher,
        slot_preference_key=slot_preference_key,
        state_enum=TeacherTimePreferenceState,
        default=TeacherTimePreferenceState.AVAILABLE,
    )


def add_subject_time_hard_constraints(*, model, x, sessions, slots):
    """Add hard constraints that prevent sessions from being placed at UNAVAILABLE subject slots.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts
    Output: None; side-effect: adds x[s,p]==0 constraints to model
    """
    _add_unavailable_time_hard_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
        state_resolver=session_preference_state,
        unavailable_state=SubjectTimePreferenceState.UNAVAILABLE,
    )


def add_teacher_time_hard_constraints(*, model, x, sessions, slots):
    """Add hard constraints that prevent sessions from being placed at UNAVAILABLE teacher slots.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts
    Output: None; side-effect: adds x[s,p]==0 constraints to model
    """
    _add_unavailable_time_hard_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
        state_resolver=teacher_preference_state,
        unavailable_state=TeacherTimePreferenceState.UNAVAILABLE,
    )


def _add_unavailable_time_hard_constraints(
    *, model, x, sessions, slots, state_resolver, unavailable_state
):
    """Add x[s,p]==0 for every (session, slot) pair where the entity is UNAVAILABLE.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts;
           state_resolver - callable(session, slot_preference_key) → preference state;
           unavailable_state - the state value that triggers x[s,p]==0
    Output: None; side-effect: adds constraints to model
    """
    slot_preference_by_idx = build_slot_preference_index(slots=slots)

    for s_idx, session in enumerate(sessions):
        for p_idx, slot_key in slot_preference_by_idx.items():
            if (s_idx, p_idx) not in x:
                continue
            state = state_resolver(
                session=session,
                slot_preference_key=slot_key,
            )
            if state == unavailable_state:
                model.Add(x[(s_idx, p_idx)] == 0)
