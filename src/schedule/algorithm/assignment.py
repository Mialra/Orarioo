try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - depends on local Python version
    cp_model = None

from schedule.algorithm.constraints import (
    add_exactly_one_slot_constraints,
    add_group_daily_capacity_constraints,
    add_resource_non_overlap_constraints,
    apply_soft_constraints,
    group_daily_limit,
)
from schedule.algorithm.errors import ScheduleGenerationError
from schedule.algorithm.slots import build_slot_day_index


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
    day_index_by_slot = build_slot_day_index(slots=slots)
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

        selected_slot = None
        for p_idx in range(len(slots)):
            if p_idx in teacher_busy_slots[teacher_id]:
                continue
            if group_id and p_idx in group_busy_slots[group_id]:
                continue
            if group_id:
                day_idx = day_index_by_slot[p_idx]
                assigned_today = group_daily_load[group_id].get(day_idx, 0)
                if assigned_today >= daily_limit:
                    continue
            selected_slot = p_idx
            break

        if selected_slot is None:
            raise ScheduleGenerationError(
                "Could not generate a feasible schedule with current basic constraints."
            )

        slot_by_session.append(selected_slot)
        teacher_busy_slots[teacher_id].add(selected_slot)
        if group_id:
            group_busy_slots[group_id].add(selected_slot)
            selected_day = day_index_by_slot[selected_slot]
            group_daily_load[group_id][selected_day] = (
                group_daily_load[group_id].get(selected_day, 0) + 1
            )

    return slot_by_session
