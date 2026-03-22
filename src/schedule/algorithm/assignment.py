try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - depends on local Python version
    cp_model = None

from schedule.algorithm.constraints import (
    add_group_daily_capacity_constraints,
    add_group_no_intraday_gap_constraints,
    add_resource_non_overlap_constraints,
    add_subject_time_hard_constraints,
    add_teacher_time_hard_constraints,
    apply_soft_constraints,
)
from schedule.algorithm.errors import ScheduleGenerationError


def solve_session_assignment(
    *,
    sessions,
    slots,
    classrooms,
    random_seed=None,
    fixed_assignments=None,
    previous_assignment_by_session=None,
):
    if cp_model is None:  # pragma: no cover
        raise ScheduleGenerationError(
            "OR-Tools (cp_model) is required for schedule generation and is not available. "
            "Please install ortools: pip install ortools"
        )

    compatible_classrooms_by_session = _build_compatible_classroom_index(
        sessions=sessions,
        classrooms=classrooms,
    )

    return _cp_sat_session_assignment(
        sessions=sessions,
        slots=slots,
        compatible_classrooms_by_session=compatible_classrooms_by_session,
        random_seed=random_seed,
        fixed_assignments=fixed_assignments,
        previous_assignment_by_session=previous_assignment_by_session,
    )


def _cp_sat_session_assignment(
    *,
    sessions,
    slots,
    compatible_classrooms_by_session,
    random_seed,
    fixed_assignments,
    previous_assignment_by_session,
):
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

    # Apply fixed assignments (manual change constraints)
    if fixed_assignments:
        for session_idx, slot_idx in fixed_assignments.items():
            if session_idx < 0 or session_idx >= session_count:
                raise ScheduleGenerationError(f"Invalid session index: {session_idx}")
            if slot_idx < 0 or slot_idx >= slot_count:
                raise ScheduleGenerationError(f"Invalid slot index: {slot_idx}")
            model.Add(x[(session_idx, slot_idx)] == 1)
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
    add_group_no_intraday_gap_constraints(
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

    timeout_seconds = _cp_sat_timeout_seconds(
        session_count=session_count,
        slot_count=slot_count,
    )
    feasible_timeout = _phase_feasible_timeout(total_timeout=timeout_seconds)
    optimization_timeout = max(1.0, timeout_seconds - feasible_timeout)

    # Phase 1: find any feasible assignment with hard constraints only.
    feasible_solver = _build_solver(
        timeout_seconds=feasible_timeout,
        random_seed=random_seed,
        session_count=session_count,
        slot_count=slot_count,
        stop_after_first_solution=True,
    )
    feasible_status = feasible_solver.Solve(model)

    if feasible_status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ScheduleGenerationError(
            f"Could not generate a feasible schedule with current basic constraints. "
            f"(Solver status: {_solver_status_name(feasible_status)}, "
            f"timeout: {feasible_timeout}s, sessions: {session_count}, slots: {slot_count})"
        )

    # Phase 2: optimize soft constraints, starting from feasible solution.
    stability_terms = _build_schedule_stability_terms(
        x=x,
        y=y,
        previous_assignment_by_session=previous_assignment_by_session,
    )
    apply_soft_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
        extra_objective_terms=stability_terms,
    )
    _add_solution_hints(
        model=model,
        solver=feasible_solver,
        x=x,
        y=y,
    )

    optimization_solver = _build_solver(
        timeout_seconds=optimization_timeout,
        random_seed=random_seed,
        session_count=session_count,
        slot_count=slot_count,
        stop_after_first_solution=False,
    )
    optimization_status = optimization_solver.Solve(model)

    if optimization_status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return _extract_slot_and_classroom_assignment(
            solver=optimization_solver,
            x=x,
            y=y,
            compatible_classrooms_by_session=compatible_classrooms_by_session,
            session_count=session_count,
            slot_count=slot_count,
        )

    # Fallback: keep feasible phase solution if optimization phase times out/fails.
    return _extract_slot_and_classroom_assignment(
        solver=feasible_solver,
        x=x,
        y=y,
        compatible_classrooms_by_session=compatible_classrooms_by_session,
        session_count=session_count,
        slot_count=slot_count,
    )


def _build_solver(
    *,
    timeout_seconds,
    random_seed,
    session_count,
    slot_count,
    stop_after_first_solution,
):
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = timeout_seconds
    solver.parameters.log_search_progress = False
    if random_seed is not None:
        solver.parameters.random_seed = int(random_seed)
    if hasattr(solver.parameters, "randomize_search"):
        solver.parameters.randomize_search = True
    if session_count >= 40 or slot_count >= 25:
        solver.parameters.num_workers = 8
    if stop_after_first_solution and hasattr(
        solver.parameters, "stop_after_first_solution"
    ):
        solver.parameters.stop_after_first_solution = True
    return solver


def _add_solution_hints(*, model, solver, x, y):
    for variable in x.values():
        model.AddHint(variable, solver.Value(variable))
    for variable in y.values():
        model.AddHint(variable, solver.Value(variable))


def _phase_feasible_timeout(*, total_timeout):
    # Keep most of the budget for feasibility, but reserve some for soft optimization.
    if total_timeout >= 120.0:
        return total_timeout - 30.0
    if total_timeout >= 60.0:
        return total_timeout - 15.0
    return max(5.0, min(total_timeout * 0.75, total_timeout - 1.0))


def _cp_sat_timeout_seconds(*, session_count, slot_count):
    """Calculate timeout based on subproblem size."""
    if session_count >= 300 or slot_count >= 45:
        return 600.0
    if session_count >= 150 or slot_count >= 40:
        return 300.0
    if session_count >= 80 or slot_count >= 35:
        return 180.0
    if session_count >= 40 or slot_count >= 25:
        return 120.0
    if session_count >= 20 or slot_count >= 15:
        return 60.0
    return 30.0


def _solver_status_name(status):
    """Return human-readable solver status name."""
    status_map = {
        cp_model.UNKNOWN: "UNKNOWN",
        cp_model.MODEL_INVALID: "MODEL_INVALID",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.OPTIMAL: "OPTIMAL",
    }
    return status_map.get(status, f"UNKNOWN_STATUS_{status}")


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


def _build_schedule_stability_terms(*, x, y, previous_assignment_by_session):
    """
    Build soft terms that reward keeping sessions in their original slot/classroom.

    Higher reward on slot stability minimises timetable perturbation after a manual
    change; classroom stability acts as a secondary tie-breaker.
    """
    if not previous_assignment_by_session:
        return []

    slot_stability_weight = 100
    classroom_stability_weight = 20
    weighted_terms = []

    for s_idx, previous in previous_assignment_by_session.items():
        slot_idx = previous.get("slot_index")
        classroom_id = previous.get("classroom_id")

        if slot_idx is not None and (s_idx, slot_idx) in x:
            weighted_terms.append(slot_stability_weight * x[(s_idx, slot_idx)])

        if (
            slot_idx is not None
            and classroom_id is not None
            and (s_idx, slot_idx, classroom_id) in y
        ):
            weighted_terms.append(
                classroom_stability_weight * y[(s_idx, slot_idx, classroom_id)]
            )

    return weighted_terms


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
