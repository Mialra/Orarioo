try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - depends on local Python version
    cp_model = None

from schedule.algorithm.constraints import (
    add_group_daily_capacity_constraints,
    add_resource_non_overlap_constraints,
    add_subject_time_hard_constraints,
    add_teacher_time_hard_constraints,
    apply_soft_constraints,
    group_daily_limit,
    session_preference_state,
    teacher_preference_state,
)
from schedule.algorithm.errors import ScheduleGenerationError
from schedule.algorithm.slots import build_slot_day_index, build_slot_preference_index
from subject.models import SubjectTimePreferenceState
from teacher.models import TeacherTimePreferenceState


def solve_session_assignment(*, sessions, slots, classrooms):
    compatible_classrooms_by_session = _build_compatible_classroom_index(
        sessions=sessions,
        classrooms=classrooms,
    )
    if cp_model is None:
        return _greedy_session_assignment(
            sessions=sessions,
            slots=slots,
            compatible_classrooms_by_session=compatible_classrooms_by_session,
        )
    return _cp_sat_session_assignment(
        sessions=sessions,
        slots=slots,
        compatible_classrooms_by_session=compatible_classrooms_by_session,
    )


def _cp_sat_session_assignment(*, sessions, slots, compatible_classrooms_by_session):
    model = cp_model.CpModel()
    session_count = len(sessions)
    slot_count = len(slots)

    y = _build_classroom_slot_decision_variables(
        model=model,
        compatible_classrooms_by_session=compatible_classrooms_by_session,
        slot_count=slot_count,
    )
    x = _build_slot_projection_variables(
        model=model,
        y=y,
        compatible_classrooms_by_session=compatible_classrooms_by_session,
        slot_count=slot_count,
    )
    _add_exactly_one_slot_and_classroom_constraints(
        model=model,
        y=y,
        compatible_classrooms_by_session=compatible_classrooms_by_session,
        slot_count=slot_count,
    )
    add_resource_non_overlap_constraints(
        model=model,
        x=x,
        slot_count=slot_count,
        sessions=sessions,
        resource_key="teacher_id",
    )
    add_resource_non_overlap_constraints(
        model=model,
        x=x,
        slot_count=slot_count,
        sessions=sessions,
        resource_key="group_id",
    )
    _add_classroom_non_overlap_constraints(
        model=model,
        y=y,
        slot_count=slot_count,
        classrooms=compatible_classrooms_by_session,
    )
    add_group_daily_capacity_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
    )
    add_subject_time_hard_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
    )
    add_teacher_time_hard_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
    )

    apply_soft_constraints(model=model, x=x, sessions=sessions, slots=slots)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ScheduleGenerationError(
            "Could not generate a feasible schedule with current basic constraints."
        )

    return _extract_slot_and_classroom_assignment(
        solver=solver,
        x=x,
        y=y,
        compatible_classrooms_by_session=compatible_classrooms_by_session,
        session_count=session_count,
        slot_count=slot_count,
    )


def _build_classroom_slot_decision_variables(
    *, model, compatible_classrooms_by_session, slot_count
):
    y = {}
    for s_idx, classrooms in compatible_classrooms_by_session.items():
        for p_idx in range(slot_count):
            for classroom in classrooms:
                y[(s_idx, p_idx, classroom.id)] = model.NewBoolVar(
                    f"y_s{s_idx}_p{p_idx}_c{classroom.id}"
                )
    return y


def _build_slot_projection_variables(
    *, model, y, compatible_classrooms_by_session, slot_count
):
    x = {}
    for s_idx, classrooms in compatible_classrooms_by_session.items():
        classroom_ids = [classroom.id for classroom in classrooms]
        for p_idx in range(slot_count):
            x[(s_idx, p_idx)] = model.NewBoolVar(f"x_s{s_idx}_p{p_idx}")
            model.Add(
                sum(y[(s_idx, p_idx, classroom_id)] for classroom_id in classroom_ids)
                == x[(s_idx, p_idx)]
            )
    return x


def _add_exactly_one_slot_and_classroom_constraints(
    *, model, y, compatible_classrooms_by_session, slot_count
):
    for s_idx, classrooms in compatible_classrooms_by_session.items():
        classroom_ids = [classroom.id for classroom in classrooms]
        model.Add(
            sum(
                y[(s_idx, p_idx, classroom_id)]
                for p_idx in range(slot_count)
                for classroom_id in classroom_ids
            )
            == 1
        )


def _add_classroom_non_overlap_constraints(*, model, y, slot_count, classrooms):
    classroom_ids = {
        classroom.id
        for compatible_classrooms in classrooms.values()
        for classroom in compatible_classrooms
    }
    for classroom_id in classroom_ids:
        for p_idx in range(slot_count):
            model.Add(
                sum(
                    var
                    for (s_idx, var_p_idx, var_classroom_id), var in y.items()
                    if var_p_idx == p_idx and var_classroom_id == classroom_id
                )
                <= 1
            )


def _extract_slot_and_classroom_assignment(
    *,
    solver,
    x,
    y,
    compatible_classrooms_by_session,
    session_count,
    slot_count,
):
    slot_by_session = []
    classroom_by_session = []

    for s_idx in range(session_count):
        selected = None
        selected_classroom = None
        for p_idx in range(slot_count):
            if solver.Value(x[(s_idx, p_idx)]) == 1:
                selected = p_idx
                for classroom in compatible_classrooms_by_session[s_idx]:
                    if solver.Value(y[(s_idx, p_idx, classroom.id)]) == 1:
                        selected_classroom = classroom
                        break
                break
        if selected is None or selected_classroom is None:
            raise ScheduleGenerationError("Solver returned an incomplete assignment.")
        slot_by_session.append(selected)
        classroom_by_session.append(selected_classroom)

    return slot_by_session, classroom_by_session


def _greedy_session_assignment(*, sessions, slots, compatible_classrooms_by_session):
    teacher_busy_slots = {}
    teacher_day_slots = {}  # {teacher_id: {day_idx: set of slot positions within day}}
    classroom_busy_slots = {}
    group_busy_slots = {}
    group_daily_load = {}
    subject_day_load = {}
    day_index_by_slot = build_slot_day_index(slots=slots)
    slot_preference_by_idx = build_slot_preference_index(slots=slots)

    # Build slot_day_order: slot_idx → position (0-based) within its day.
    slots_by_day_ordered = {}
    for slot_idx, day_idx in day_index_by_slot.items():
        slots_by_day_ordered.setdefault(day_idx, []).append(slot_idx)
    slot_day_order = {}
    for day_slot_list in slots_by_day_ordered.values():
        for pos, slot_idx in enumerate(sorted(day_slot_list)):
            slot_day_order[slot_idx] = pos

    slot_by_session = []
    classroom_by_session = []

    for session_index, session in enumerate(sessions):
        teacher_id, group_id, daily_limit, subj_id = _prepare_greedy_session_state(
            session=session,
            session_index=session_index,
            compatible_classrooms_by_session=compatible_classrooms_by_session,
            teacher_busy_slots=teacher_busy_slots,
            teacher_day_slots=teacher_day_slots,
            classroom_busy_slots=classroom_busy_slots,
            group_busy_slots=group_busy_slots,
            group_daily_load=group_daily_load,
            subject_day_load=subject_day_load,
        )

        sorted_slots = _ordered_greedy_slots(
            slot_count=len(slots),
            subj_id=subj_id,
            subject_day_load=subject_day_load,
            day_index_by_slot=day_index_by_slot,
            teacher_id=teacher_id,
            teacher_day_slots=teacher_day_slots,
            slot_day_order=slot_day_order,
        )

        selected_slot = None
        selected_classroom = None
        for p_idx in sorted_slots:
            available_classroom = _pick_greedy_compatible_classroom(
                session=session,
                session_index=session_index,
                slot_idx=p_idx,
                compatible_classrooms_by_session=compatible_classrooms_by_session,
                classroom_busy_slots=classroom_busy_slots,
                teacher_id=teacher_id,
                group_id=group_id,
                daily_limit=daily_limit if group_id else None,
                teacher_busy_slots=teacher_busy_slots,
                group_busy_slots=group_busy_slots,
                group_daily_load=group_daily_load,
                day_index_by_slot=day_index_by_slot,
                slot_preference_by_idx=slot_preference_by_idx,
            )
            if available_classroom is None:
                continue
            selected_slot = p_idx
            selected_classroom = available_classroom
            break

        if selected_slot is None or selected_classroom is None:
            raise ScheduleGenerationError(
                "Could not generate a feasible schedule with current basic constraints."
            )

        slot_by_session.append(selected_slot)
        classroom_by_session.append(selected_classroom)
        _update_greedy_tracking(
            selected_slot=selected_slot,
            selected_classroom_id=selected_classroom.id,
            teacher_id=teacher_id,
            subj_id=subj_id,
            group_id=group_id,
            teacher_busy_slots=teacher_busy_slots,
            teacher_day_slots=teacher_day_slots,
            classroom_busy_slots=classroom_busy_slots,
            subject_day_load=subject_day_load,
            group_busy_slots=group_busy_slots,
            group_daily_load=group_daily_load,
            day_index_by_slot=day_index_by_slot,
            slot_day_order=slot_day_order,
        )

    return slot_by_session, classroom_by_session


def _prepare_greedy_session_state(
    *,
    session,
    session_index,
    compatible_classrooms_by_session,
    teacher_busy_slots,
    teacher_day_slots,
    classroom_busy_slots,
    group_busy_slots,
    group_daily_load,
    subject_day_load,
):
    teacher_id = session["teacher_id"]
    teacher_busy_slots.setdefault(teacher_id, set())
    teacher_day_slots.setdefault(teacher_id, {})
    for classroom in compatible_classrooms_by_session[session_index]:
        classroom_busy_slots.setdefault(classroom.id, set())

    group = session.get("group")
    group_id = group.id if group else None
    daily_limit = None
    if group_id:
        group_busy_slots.setdefault(group_id, set())
        group_daily_load.setdefault(group_id, {})
        daily_limit = group_daily_limit(group)

    subject = session.get("subject")
    subj_id = subject.id if subject else None
    if subj_id:
        subject_day_load.setdefault(subj_id, {})

    return teacher_id, group_id, daily_limit, subj_id


def _ordered_greedy_slots(
    *,
    slot_count,
    subj_id,
    subject_day_load,
    day_index_by_slot,
    teacher_id,
    teacher_day_slots,
    slot_day_order,
):
    return sorted(
        range(slot_count),
        key=lambda p: (
            (
                0
                if (
                    subj_id is None
                    or subject_day_load[subj_id].get(day_index_by_slot[p], 0) == 0
                )
                else 1
            ),
            _teacher_gap_score(
                slot_idx=p,
                teacher_id=teacher_id,
                teacher_day_slots=teacher_day_slots,
                day_index_by_slot=day_index_by_slot,
                slot_day_order=slot_day_order,
            ),
        ),
    )


def _update_greedy_tracking(
    *,
    selected_slot,
    selected_classroom_id,
    teacher_id,
    subj_id,
    group_id,
    teacher_busy_slots,
    teacher_day_slots,
    classroom_busy_slots,
    subject_day_load,
    group_busy_slots,
    group_daily_load,
    day_index_by_slot,
    slot_day_order,
):
    teacher_busy_slots[teacher_id].add(selected_slot)
    classroom_busy_slots[selected_classroom_id].add(selected_slot)
    selected_day = day_index_by_slot[selected_slot]
    teacher_day_slots[teacher_id].setdefault(selected_day, set()).add(
        slot_day_order[selected_slot]
    )
    if subj_id:
        subject_day_load[subj_id][selected_day] = (
            subject_day_load[subj_id].get(selected_day, 0) + 1
        )
    if group_id:
        _mark_group_greedy_assignment(
            selected_slot=selected_slot,
            group_id=group_id,
            group_busy_slots=group_busy_slots,
            group_daily_load=group_daily_load,
            day_index_by_slot=day_index_by_slot,
        )


def _is_greedy_slot_available(
    *,
    session,
    slot_idx,
    teacher_id,
    group_id,
    daily_limit,
    teacher_busy_slots,
    group_busy_slots,
    group_daily_load,
    day_index_by_slot,
    slot_preference_by_idx,
):
    slot_key = slot_preference_by_idx.get(slot_idx)
    if slot_key is not None:
        teacher_slot_state = teacher_preference_state(
            session=session,
            slot_preference_key=slot_key,
        )
        if teacher_slot_state == TeacherTimePreferenceState.UNAVAILABLE:
            return False

        slot_state = session_preference_state(
            session=session,
            slot_preference_key=slot_key,
        )
        if slot_state == SubjectTimePreferenceState.UNAVAILABLE:
            return False

    if slot_idx in teacher_busy_slots[teacher_id]:
        return False

    if not group_id:
        return True

    if slot_idx in group_busy_slots[group_id]:
        return False

    day_idx = day_index_by_slot[slot_idx]
    assigned_today = group_daily_load[group_id].get(day_idx, 0)
    if daily_limit is not None and assigned_today >= daily_limit:
        return False

    return True


def _pick_greedy_compatible_classroom(
    *,
    session,
    session_index,
    slot_idx,
    compatible_classrooms_by_session,
    classroom_busy_slots,
    teacher_id,
    group_id,
    daily_limit,
    teacher_busy_slots,
    group_busy_slots,
    group_daily_load,
    day_index_by_slot,
    slot_preference_by_idx,
):
    if not _is_greedy_slot_available(
        session=session,
        slot_idx=slot_idx,
        teacher_id=teacher_id,
        group_id=group_id,
        daily_limit=daily_limit,
        teacher_busy_slots=teacher_busy_slots,
        group_busy_slots=group_busy_slots,
        group_daily_load=group_daily_load,
        day_index_by_slot=day_index_by_slot,
        slot_preference_by_idx=slot_preference_by_idx,
    ):
        return None

    for classroom in compatible_classrooms_by_session[session_index]:
        if slot_idx not in classroom_busy_slots[classroom.id]:
            return classroom
    return None


def _mark_group_greedy_assignment(
    *,
    selected_slot,
    group_id,
    group_busy_slots,
    group_daily_load,
    day_index_by_slot,
):
    group_busy_slots[group_id].add(selected_slot)
    selected_day = day_index_by_slot[selected_slot]
    group_daily_load[group_id][selected_day] = (
        group_daily_load[group_id].get(selected_day, 0) + 1
    )


def _teacher_gap_score(
    *,
    slot_idx,
    teacher_id,
    teacher_day_slots,
    day_index_by_slot,
    slot_day_order,
):
    """
    Return the number of intra-day gaps that would exist if this slot were
    added to the teacher's already-assigned slots on the same day (F-29).

    A gap is any day-position between the earliest and latest assigned
    positions that has no session. Zero means no fragmentation.
    """
    day_idx = day_index_by_slot[slot_idx]
    existing_positions = teacher_day_slots.get(teacher_id, {}).get(day_idx, set())
    if not existing_positions:
        return 0
    new_pos = slot_day_order[slot_idx]
    all_positions = sorted(existing_positions | {new_pos})
    span = all_positions[-1] - all_positions[0]
    return span - (len(all_positions) - 1)


def _build_compatible_classroom_index(*, sessions, classrooms):
    compatible_classrooms_by_session = {}
    for session_index, session in enumerate(sessions):
        compatible_classrooms = [
            classroom
            for classroom in classrooms
            if _is_classroom_compatible(
                session=session,
                classroom=classroom,
            )
        ]
        if not compatible_classrooms:
            raise ScheduleGenerationError(
                _classroom_compatibility_error(session=session)
            )
        compatible_classrooms_by_session[session_index] = compatible_classrooms
    return compatible_classrooms_by_session


def _is_classroom_compatible(*, session, classroom):
    subject = session.get("subject")
    required_type = (
        (getattr(subject, "required_classroom_type", "") or "").strip().casefold()
    )
    if not required_type:
        return True
    classroom_type = (getattr(classroom, "classroom_type", "") or "").strip().casefold()
    return classroom_type == required_type


def _classroom_compatibility_error(*, session):
    subject = session.get("subject")
    required_type = getattr(subject, "required_classroom_type", "") if subject else ""
    if required_type:
        return (
            "Could not assign a compatible classroom for subject '{name}' "
            "with required classroom type '{required_type}'."
        ).format(
            name=getattr(subject, "name", "Unknown subject"),
            required_type=required_type,
        )
    return "Could not assign a classroom to at least one generated session."
