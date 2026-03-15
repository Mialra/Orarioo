try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - depends on local Python version
    cp_model = None

from schedule.algorithm.constraints import (
    add_exactly_one_slot_constraints,
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


def solve_session_assignment(*, sessions, slots):
    if cp_model is None:
        return _greedy_session_assignment(sessions=sessions, slots=slots)
    return _cp_sat_session_assignment(sessions=sessions, slots=slots)


def _cp_sat_session_assignment(*, sessions, slots):
    model = cp_model.CpModel()
    session_count = len(sessions)
    slot_count = len(slots)

    x = _build_decision_variables(
        model=model,
        session_count=session_count,
        slot_count=slot_count,
    )
    add_exactly_one_slot_constraints(
        model=model,
        x=x,
        session_count=session_count,
        slot_count=slot_count,
    )
    add_resource_non_overlap_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slot_count=slot_count,
        resource_key="teacher_id",
    )
    add_resource_non_overlap_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slot_count=slot_count,
        resource_key="group_id",
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

    return _extract_slot_assignment(
        solver=solver,
        x=x,
        session_count=session_count,
        slot_count=slot_count,
    )


def _build_decision_variables(*, model, session_count, slot_count):
    x = {}
    for s_idx in range(session_count):
        for p_idx in range(slot_count):
            x[(s_idx, p_idx)] = model.NewBoolVar(f"x_s{s_idx}_p{p_idx}")
    return x


def _extract_slot_assignment(*, solver, x, session_count, slot_count):
    slot_by_session = []

    for s_idx in range(session_count):
        selected = None
        for p_idx in range(slot_count):
            if solver.Value(x[(s_idx, p_idx)]) == 1:
                selected = p_idx
                break
        if selected is None:
            raise ScheduleGenerationError("Solver returned an incomplete assignment.")
        slot_by_session.append(selected)

    return slot_by_session


def _greedy_session_assignment(*, sessions, slots):
    teacher_busy_slots = {}
    group_busy_slots = {}
    group_daily_load = {}
    subject_day_load = {}
    day_index_by_slot = build_slot_day_index(slots=slots)
    slot_preference_by_idx = build_slot_preference_index(slots=slots)
    slot_by_session = []

    for session in sessions:
        teacher_id = session["teacher_id"]
        teacher_busy_slots.setdefault(teacher_id, set())

        group = session.get("group")
        group_id = group.id if group else None
        if group_id:
            group_busy_slots.setdefault(group_id, set())
            group_daily_load.setdefault(group_id, {})
            daily_limit = group_daily_limit(group)

        subject = session.get("subject")
        subj_id = subject.id if subject else None
        if subj_id:
            subject_day_load.setdefault(subj_id, {})

        # Prefer slots on days not yet used by this subject (F-28 soft spread).
        sorted_slots = sorted(
            range(len(slots)),
            key=lambda p: (
                0
                if (
                    subj_id is None
                    or subject_day_load[subj_id].get(day_index_by_slot[p], 0) == 0
                )
                else 1
            ),
        )

        selected_slot = None
        for p_idx in sorted_slots:
            if not _is_greedy_slot_available(
                session=session,
                slot_idx=p_idx,
                teacher_id=teacher_id,
                group_id=group_id,
                daily_limit=daily_limit if group_id else None,
                teacher_busy_slots=teacher_busy_slots,
                group_busy_slots=group_busy_slots,
                group_daily_load=group_daily_load,
                day_index_by_slot=day_index_by_slot,
                slot_preference_by_idx=slot_preference_by_idx,
            ):
                continue
            selected_slot = p_idx
            break

        if selected_slot is None:
            raise ScheduleGenerationError(
                "Could not generate a feasible schedule with current basic constraints."
            )

        slot_by_session.append(selected_slot)
        teacher_busy_slots[teacher_id].add(selected_slot)
        if subj_id:
            selected_day = day_index_by_slot[selected_slot]
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

    return slot_by_session


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
