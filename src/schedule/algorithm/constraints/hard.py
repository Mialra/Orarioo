from group.models import EducationalStage
from schedule.algorithm.errors import ScheduleGenerationError
from schedule.algorithm.slots import build_slot_day_index, build_slot_preference_index
from subject.models import SubjectTimePreferenceState
from teacher.models import TeacherTimePreferenceState


def group_weekly_limit(group):
    if group.stage in (EducationalStage.PRESCHOOL, EducationalStage.PRIMARY):
        return 25
    return 30


def group_daily_limit(group):
    if group.stage in (EducationalStage.PRESCHOOL, EducationalStage.PRIMARY):
        return 5
    return 6


def validate_group_and_teacher_capacity(*, sessions, slots):
    sessions_by_group, sessions_by_teacher = _build_capacity_state(sessions=sessions)

    _validate_group_slot_capacity(
        sessions_by_group=sessions_by_group,
        slot_count=len(slots),
    )
    _validate_group_weekly_capacity(sessions_by_group=sessions_by_group)
    _validate_teacher_weekly_capacity(sessions_by_teacher=sessions_by_teacher)


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
                    assigned=teacher_state["assigned_hours"],
                    max_hours=teacher_state["max_weekly_hours"],
                )
            )


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
    resource_to_sessions = {}

    for idx, session in enumerate(sessions):
        resource_id = _session_resource_id(session=session, resource_key=resource_key)
        if resource_id is None:
            continue
        resource_to_sessions.setdefault(resource_id, []).append(idx)

    for resource_sessions in resource_to_sessions.values():
        for p_idx in range(slot_count):
            model.Add(sum(x[(s_idx, p_idx)] for s_idx in resource_sessions) <= 1)


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


def session_preference_state(*, session, slot_preference_key):
    subject = session.get("subject")
    if subject is None:
        return SubjectTimePreferenceState.AVAILABLE

    preferences = getattr(subject, "time_preferences", None) or {}
    state = preferences.get(slot_preference_key)
    if state in SubjectTimePreferenceState.values:
        return state
    return SubjectTimePreferenceState.AVAILABLE


def teacher_preference_state(*, session, slot_preference_key):
    teacher = session.get("teacher")
    if teacher is None:
        return TeacherTimePreferenceState.AVAILABLE

    preferences = getattr(teacher, "time_preferences", None) or {}
    state = preferences.get(slot_preference_key)
    if state in TeacherTimePreferenceState.values:
        return state
    return TeacherTimePreferenceState.AVAILABLE


def add_subject_time_hard_constraints(*, model, x, sessions, slots):
    slot_preference_by_idx = build_slot_preference_index(slots=slots)

    for s_idx, session in enumerate(sessions):
        for p_idx, slot_key in slot_preference_by_idx.items():
            state = session_preference_state(
                session=session,
                slot_preference_key=slot_key,
            )
            if state == SubjectTimePreferenceState.UNAVAILABLE:
                model.Add(x[(s_idx, p_idx)] == 0)


def add_teacher_time_hard_constraints(*, model, x, sessions, slots):
    slot_preference_by_idx = build_slot_preference_index(slots=slots)

    for s_idx, session in enumerate(sessions):
        for p_idx, slot_key in slot_preference_by_idx.items():
            state = teacher_preference_state(
                session=session,
                slot_preference_key=slot_key,
            )
            if state == TeacherTimePreferenceState.UNAVAILABLE:
                model.Add(x[(s_idx, p_idx)] == 0)
