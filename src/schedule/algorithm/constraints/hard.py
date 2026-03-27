from group.models import EducationalStage
from schedule.algorithm.errors import ScheduleGenerationError
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
RECESS_MINUTES_PER_DAY_BY_STAGE = {
    EducationalStage.PRESCHOOL: 60,
    EducationalStage.PRIMARY: 30,
}
STAGE_OPTION_FIELD = {
    EducationalStage.PRESCHOOL: "recess_supervisors_preschool",
    EducationalStage.PRIMARY: "recess_supervisors_primary",
}


def group_weekly_limit(group):
    if group.stage in PRESCHOOL_AND_PRIMARY_STAGES:
        return 25
    return 30


def group_daily_limit(group):
    if group.stage in PRESCHOOL_AND_PRIMARY_STAGES:
        return 5
    return 6


def validate_group_and_teacher_capacity(*, sessions, slots, generation_options=None):
    sessions_by_group, sessions_by_teacher = _build_capacity_state(sessions=sessions)
    _apply_recess_supervision_capacity(
        sessions=sessions,
        sessions_by_teacher=sessions_by_teacher,
        generation_options=generation_options or {},
    )

    _validate_group_slot_capacity(
        sessions_by_group=sessions_by_group,
        slot_count=len(slots),
    )
    _validate_group_weekly_capacity(sessions_by_group=sessions_by_group)
    _validate_teacher_weekly_capacity(sessions_by_teacher=sessions_by_teacher)


def _apply_recess_supervision_capacity(*, sessions, sessions_by_teacher, generation_options):
    teachers_by_stage = {
        EducationalStage.PRESCHOOL: set(),
        EducationalStage.PRIMARY: set(),
    }

    for session in sessions:
        teacher = session.get("teacher")
        group = session.get("group")
        if teacher is None or group is None:
            continue
        if group.stage in teachers_by_stage:
            teachers_by_stage[group.stage].add(teacher.id)

    for stage, teacher_ids in teachers_by_stage.items():
        required_supervisors = int(generation_options.get(STAGE_OPTION_FIELD[stage], 0) or 0)
        if required_supervisors <= 0:
            continue
        if not teacher_ids:
            raise ScheduleGenerationError(
                (
                    "Cannot assign recess supervision for stage '{stage}'. "
                    "No teachers available in that stage."
                ).format(stage=stage)
            )

        daily_minutes = RECESS_MINUTES_PER_DAY_BY_STAGE[stage]
        weekly_extra_hours = (daily_minutes / 60.0) * 5 * required_supervisors
        per_teacher_extra_hours = weekly_extra_hours / len(teacher_ids)

        for teacher_id in teacher_ids:
            teacher_state = sessions_by_teacher.get(teacher_id)
            if teacher_state is not None:
                teacher_state["assigned_hours"] += per_teacher_extra_hours


def _build_capacity_state(*, sessions):
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
    teacher = session.get("teacher")
    if teacher is None:
        return

    teacher_state = sessions_by_teacher.setdefault(
        teacher.id,
        {
            "name": teacher.name,
            "max_weekly_hours": teacher.max_weekly_hours,
            "assigned_hours": 0,
        },
    )
    teacher_state["assigned_hours"] += 1


def _validate_group_slot_capacity(*, sessions_by_group, slot_count):
    if any(
        group_state["assigned_hours"] > slot_count
        for group_state in sessions_by_group.values()
    ):
        raise ScheduleGenerationError(
            "Not enough available slots to place all sessions for at least one group."
        )


def _validate_group_weekly_capacity(*, sessions_by_group):
    for group_state in sessions_by_group.values():
        if group_state["assigned_hours"] > group_state["weekly_limit"]:
            raise ScheduleGenerationError(
                (
                    "Group '{name}' exceeds weekly capacity for its stage: "
                    "assigned {assigned} > max {max_hours}."
                ).format(
                    name=group_state["name"],
                    assigned=group_state["assigned_hours"],
                    max_hours=group_state["weekly_limit"],
                )
            )


def _validate_teacher_weekly_capacity(*, sessions_by_teacher):
    for teacher_state in sessions_by_teacher.values():
        if teacher_state["assigned_hours"] > teacher_state["max_weekly_hours"]:
            raise ScheduleGenerationError(
                (
                    "Teacher '{name}' exceeds max weekly hours: "
                    "assigned {assigned} > max {max_hours}."
                ).format(
                    name=teacher_state["name"],
                    assigned=_format_hours(teacher_state["assigned_hours"]),
                    max_hours=teacher_state["max_weekly_hours"],
                )
            )


def _format_hours(value):
    rounded = round(float(value), 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.2f}".rstrip("0").rstrip(".")


def add_exactly_one_slot_constraints(*, model, x, session_count, slot_count):
    for s_idx in range(session_count):
        model.Add(sum(x[(s_idx, p_idx)] for p_idx in range(slot_count)) == 1)


def _session_resource_id(*, session, resource_key):
    if resource_key == "group_id":
        group = session.get("group")
        return getattr(group, "id", None)
    return session.get(resource_key)


def add_resource_non_overlap_constraints(
    *, model, x, sessions, slot_count, resource_key
):
    del slot_count
    resource_to_sessions = {}

    for idx, session in enumerate(sessions):
        resource_id = _session_resource_id(session=session, resource_key=resource_key)
        if resource_id is None:
            continue
        resource_to_sessions.setdefault(resource_id, []).append(idx)

    # Non-overlap is enforced with explicit pair constraints in assignment.py,
    # where slot intervals are available. Keep this function as no-op for API
    # compatibility.
    for resource_sessions in resource_to_sessions.values():
        if not resource_sessions:
            continue


def add_stage_slot_hard_constraints(*, model, x, sessions, slots):
    allowed_slots_by_stage = build_stage_allowed_slot_index(slots=slots)

    for s_idx, session in enumerate(sessions):
        stage_code = session_stage_code(session=session)
        allowed_slots = allowed_slots_by_stage.get(stage_code, set())
        for p_idx in range(len(slots)):
            if p_idx not in allowed_slots:
                model.Add(x[(s_idx, p_idx)] == 0)


def add_group_daily_capacity_constraints(*, model, x, sessions, slots):
    day_index_by_slot = build_slot_day_index(slots=slots)
    day_indices = set(day_index_by_slot.values())
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

        for day_idx in day_indices:
            day_slots = [
                p_idx
                for p_idx, p_day_idx in day_index_by_slot.items()
                if p_day_idx == day_idx
            ]
            model.Add(
                sum(
                    x[(s_idx, p_idx)]
                    for s_idx in resource_sessions
                    for p_idx in day_slots
                )
                <= daily_limit
            )


def add_group_no_intraday_gap_constraints(*, model, x, sessions, slots):
    """Forbid intra-day gaps inside each group's timetable block (F-30)."""
    slots_by_day = _build_slots_by_day(slots=slots)
    group_to_sessions = _build_group_session_index(sessions=sessions)

    for group_id, group_sessions in group_to_sessions.items():
        group_stage = session_stage_code(session=sessions[group_sessions[0]])
        stage_allowed_slots = build_stage_allowed_slot_index(slots=slots).get(
            group_stage, set()
        )
        for day_idx, day_slot_list in slots_by_day.items():
            filtered_day_slots = [
                slot_idx
                for slot_idx in day_slot_list
                if slot_idx in stage_allowed_slots
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
    slot_day_index = build_slot_day_index(slots=slots)
    slots_by_day = {}
    for slot_idx, day_idx in slot_day_index.items():
        slots_by_day.setdefault(day_idx, []).append(slot_idx)
    for day_idx in slots_by_day:
        slots_by_day[day_idx].sort(key=lambda idx: slot_time_bounds(slot=slots[idx])[0])
    return slots_by_day


def _build_group_session_index(*, sessions):
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
    occupancy_by_slot = {}
    for slot_idx in day_slot_list:
        occupied = model.NewBoolVar(f"g{group_id}_d{day_idx}_p{slot_idx}_occ")
        model.Add(sum(x[(s_idx, slot_idx)] for s_idx in group_sessions) == occupied)
        occupancy_by_slot[slot_idx] = occupied
    return occupancy_by_slot


def _add_no_gap_triplets(*, model, occupancy_by_slot, day_slot_list):
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
    if entity is None:
        return default

    preferences = getattr(entity, "time_preferences", None) or {}
    state = preferences.get(slot_preference_key)
    if state in state_enum.values:
        return state
    return default


def session_preference_state(*, session, slot_preference_key):
    subject = session.get("subject")
    return _preference_state_for_entity(
        entity=subject,
        slot_preference_key=slot_preference_key,
        state_enum=SubjectTimePreferenceState,
        default=SubjectTimePreferenceState.AVAILABLE,
    )


def teacher_preference_state(*, session, slot_preference_key):
    teacher = session.get("teacher")
    return _preference_state_for_entity(
        entity=teacher,
        slot_preference_key=slot_preference_key,
        state_enum=TeacherTimePreferenceState,
        default=TeacherTimePreferenceState.AVAILABLE,
    )


def add_subject_time_hard_constraints(*, model, x, sessions, slots):
    _add_unavailable_time_hard_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
        state_resolver=session_preference_state,
        unavailable_state=SubjectTimePreferenceState.UNAVAILABLE,
    )


def add_teacher_time_hard_constraints(*, model, x, sessions, slots):
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
    slot_preference_by_idx = build_slot_preference_index(slots=slots)

    for s_idx, session in enumerate(sessions):
        for p_idx, slot_key in slot_preference_by_idx.items():
            state = state_resolver(
                session=session,
                slot_preference_key=slot_key,
            )
            if state == unavailable_state:
                model.Add(x[(s_idx, p_idx)] == 0)
