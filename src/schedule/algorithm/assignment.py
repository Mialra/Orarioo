"""CP-SAT session-to-slot assignment solver.

Exposes solve_session_assignment as the single entry point.  All internal
functions build decision variables, add constraints and extract the solution.
"""

try:
    from ortools.sat.python import cp_model
except ModuleNotFoundError:  # pragma: no cover - depends on local Python version
    cp_model = None

from schedule.algorithm.constraints import (
    add_group_daily_capacity_constraints,
    add_group_no_intraday_gap_constraints,
    add_stage_slot_hard_constraints,
    add_subject_time_hard_constraints,
    add_tc_slot_capacity_constraints,
    add_teacher_time_hard_constraints,
    apply_soft_constraints,
)
from schedule.algorithm.errors import ScheduleGenerationError
from schedule.algorithm.slots import build_real_time_intervals


def solve_session_assignment(
    *,
    sessions,
    slots,
    classrooms,
    random_seed=None,
    fixed_assignments=None,
    previous_assignment_by_session=None,
    generation_options=None,
):
    """Assign each session to a slot and classroom using a two-phase CP-SAT solve.

    Phase 1 finds any feasible assignment under hard constraints.
    Phase 2 optimises soft constraints starting from the feasible hint.

    Input: sessions - list of session dicts; slots - list of slot dicts;
           classrooms - list of Classroom instances;
           random_seed - optional integer for reproducibility;
           fixed_assignments - dict {session_idx: slot_idx} for locked assignments;
           previous_assignment_by_session - dict {session_idx: {slot_index, classroom_id}}
               used to build stability objective terms;
           generation_options - dict with generation parameters
    Output: tuple (slot_by_session, classroom_by_session) —
            slot_by_session[i] is the assigned slot index for session i,
            classroom_by_session[i] is the assigned Classroom instance
    """
    if cp_model is None:  # pragma: no cover
        raise ScheduleGenerationError(
            "OR-Tools (cp_model) is required for schedule generation and is not available. "
            "Please install ortools: pip install ortools",
            code="SCHEDULE_SOLVER_UNAVAILABLE",
            suggestions=[
                "Install the 'ortools' package in the backend environment.",
            ],
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
        generation_options=generation_options,
    )


def _cp_sat_session_assignment(
    *,
    sessions,
    slots,
    compatible_classrooms_by_session,
    random_seed,
    fixed_assignments,
    previous_assignment_by_session,
    generation_options,
):
    """Run the full two-phase CP-SAT solve and return the assignment.
    Input: sessions, slots - standard algorithm inputs;
           compatible_classrooms_by_session - index from _build_compatible_classroom_index;
           random_seed, fixed_assignments, previous_assignment_by_session, generation_options
               - forwarded from solve_session_assignment
    Output: tuple (slot_by_session, classroom_by_session)
    """
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

    # Apply fixed assignments (manual change constraints).
    if fixed_assignments:
        for session_idx, slot_idx in fixed_assignments.items():
            if session_idx < 0 or session_idx >= session_count:
                raise ScheduleGenerationError(f"Invalid session index: {session_idx}")
            if slot_idx < 0 or slot_idx >= slot_count:
                raise ScheduleGenerationError(f"Invalid slot index: {slot_idx}")
            model.Add(x[(session_idx, slot_idx)] == 1)

    add_stage_slot_hard_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
    )
    add_tc_slot_capacity_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
        generation_options=generation_options,
    )

    _add_resource_interval_non_overlap_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
        resource_key="teacher_id",
    )
    _add_resource_interval_non_overlap_constraints(
        model=model,
        x=x,
        sessions=sessions,
        slots=slots,
        resource_key="group_id",
    )

    _add_classroom_non_overlap_constraints(
        model=model,
        y=y,
        slots=slots,
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
            f"timeout: {feasible_timeout}s, sessions: {session_count}, slots: {slot_count})",
            context={
                "solver_status": _solver_status_name(feasible_status),
                "timeout_seconds": feasible_timeout,
                "session_count": session_count,
                "slot_count": slot_count,
            },
            suggestions=[
                "Review teacher and subject unavailable time preferences.",
                "Check whether any teacher or group exceeds its weekly capacity.",
                "Add more compatible classrooms if specialized rooms are required.",
            ],
        )

    # Phase 2: optimise soft constraints, starting from the feasible solution.
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

    # Fallback: keep the feasible phase solution if optimisation times out/fails.
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
    """Create and configure a CP-SAT CpSolver instance.
    Input: timeout_seconds - maximum wall-clock time; random_seed - optional int;
           session_count, slot_count - problem dimensions used to set parallelism;
           stop_after_first_solution - True for the feasibility phase
    Output: configured CpSolver instance
    """
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
    """Seed the model with the values from a previous solver run as warm-start hints.
    Input: model - CP-SAT CpModel; solver - solved CpSolver instance; x, y - decision variables
    Output: None; side-effect: calls model.AddHint for all variables
    """
    for variable in x.values():
        model.AddHint(variable, solver.Value(variable))
    for variable in y.values():
        model.AddHint(variable, solver.Value(variable))


def _phase_feasible_timeout(*, total_timeout):
    """Compute the time budget for the feasibility phase given the total timeout.
    Input: total_timeout - total allowed seconds as a float
    Output: float seconds allocated to the feasibility phase
    """
    if total_timeout >= 120.0:
        return total_timeout - 30.0
    if total_timeout >= 60.0:
        return total_timeout - 15.0
    return max(5.0, min(total_timeout * 0.75, total_timeout - 1.0))


def _cp_sat_timeout_seconds(*, session_count, slot_count):
    """Calculate the total solver timeout based on problem size.
    Input: session_count - number of sessions; slot_count - number of slots
    Output: float total timeout in seconds
    """
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
    """Return a human-readable name for a CP-SAT solver status code.
    Input: status - integer status code from cp_model
    Output: string status name (e.g. 'FEASIBLE', 'INFEASIBLE')
    """
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
    """Create binary y[s, p, c] variables: 1 iff session s is in slot p with classroom c.
    Input: model - CP-SAT CpModel; compatible_classrooms_by_session - compatibility index;
           slot_count - total number of slots
    Output: dict {(session_idx, slot_idx, classroom_id): BoolVar}
    """
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
    """Create binary x[s, p] variables as the projection of y over classrooms.
    Input: model - CP-SAT CpModel; y - classroom-slot decision variables;
           compatible_classrooms_by_session - compatibility index; slot_count - total slots
    Output: dict {(session_idx, slot_idx): BoolVar}
    """
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
    """Constrain each session to exactly one (slot, classroom) pair.
    Input: model - CP-SAT CpModel; y - classroom-slot decision variables;
           compatible_classrooms_by_session - compatibility index; slot_count - total slots
    Output: None; side-effect: adds sum == 1 constraints to model
    """
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


def _add_classroom_non_overlap_constraints(*, model, y, slots, classrooms):
    """Prevent the same classroom from being used in two overlapping slots.
    Input: model - CP-SAT CpModel; y - classroom-slot decision variables;
           slots - list of slot dicts; classrooms - compatible_classrooms_by_session index
    Output: None; side-effect: adds at-most-1 constraints per classroom per time interval
    """
    real_time_intervals = build_real_time_intervals(slots=slots)
    vars_by_classroom_and_slot = {}

    for (_, slot_idx, classroom_id), var in y.items():
        vars_by_classroom_and_slot.setdefault((classroom_id, slot_idx), []).append(var)

    classroom_ids = {classroom_id for classroom_id, _ in vars_by_classroom_and_slot}
    for classroom_id in classroom_ids:
        for interval in real_time_intervals:
            interval_vars = []
            for slot_idx in interval["slot_indices"]:
                interval_vars.extend(
                    vars_by_classroom_and_slot.get((classroom_id, slot_idx), [])
                )
            if interval_vars:
                model.Add(sum(interval_vars) <= 1)


def _add_resource_interval_non_overlap_constraints(
    *, model, x, sessions, slots, resource_key
):
    """Prevent the same teacher or group from occupying two overlapping slots.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           sessions - list of session dicts; slots - list of slot dicts;
           resource_key - 'teacher_id' or 'group_id'
    Output: None; side-effect: adds at-most-1 constraints per resource per time interval
    """
    resource_to_sessions = _index_sessions_by_resource(
        sessions=sessions,
        resource_key=resource_key,
    )
    real_time_intervals = build_real_time_intervals(slots=slots)

    for resource_sessions in resource_to_sessions.values():
        _add_resource_interval_capacity_constraints(
            model=model,
            x=x,
            resource_sessions=resource_sessions,
            real_time_intervals=real_time_intervals,
        )


def _index_sessions_by_resource(*, sessions, resource_key):
    """Build an index of resource_id → list of session indices.
    Input: sessions - list of session dicts; resource_key - 'teacher_id' or 'group_id'
    Output: dict {resource_id: [session_idx, ...]}
    """
    resource_to_sessions = {}
    for idx, session in enumerate(sessions):
        resource_id = _session_resource_id(session=session, resource_key=resource_key)
        if resource_id is None:
            continue
        resource_to_sessions.setdefault(resource_id, []).append(idx)
    return resource_to_sessions


def _session_resource_id(*, session, resource_key):
    """Extract the resource id from a session dict for the given resource key.
    Input: session - session dict; resource_key - 'group_id' or 'teacher_id'
    Output: resource id, or None if absent
    """
    if resource_key == "group_id":
        group = session.get("group")
        return getattr(group, "id", None)
    return session.get(resource_key)


def _add_resource_interval_capacity_constraints(
    *, model, x, resource_sessions, real_time_intervals
):
    """Add at-most-1 constraints for a resource across each real-time interval.
    Input: model - CP-SAT CpModel; x - slot decision variables;
           resource_sessions - list of session indices for this resource;
           real_time_intervals - list of interval dicts from build_real_time_intervals
    Output: None; side-effect: adds constraints to model
    """
    for interval in real_time_intervals:
        interval_terms = [
            x[(session_idx, slot_idx)]
            for session_idx in resource_sessions
            for slot_idx in interval["slot_indices"]
        ]
        if interval_terms:
            model.Add(sum(interval_terms) <= 1)


def _extract_slot_and_classroom_assignment(
    *,
    solver,
    x,
    y,
    compatible_classrooms_by_session,
    session_count,
    slot_count,
):
    """Read the solver's variable values and build the result lists.
    Input: solver - solved CpSolver instance; x, y - decision variables;
           compatible_classrooms_by_session - compatibility index;
           session_count, slot_count - problem dimensions
    Output: tuple (slot_by_session, classroom_by_session);
            raises ScheduleGenerationError if any session has no assignment
    """
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
    """Build the index of compatible classrooms for each session.
    Input: sessions - list of session dicts; classrooms - list of Classroom instances
    Output: dict {session_idx: [Classroom, ...]} with at least one entry per session;
            raises ScheduleGenerationError if a session has no compatible classroom
    """
    compatible_classrooms_by_session = {}
    for session_index, session in enumerate(sessions):
        allowed_classroom_ids = session.get("allowed_classroom_ids")
        compatible_classrooms = [
            classroom
            for classroom in classrooms
            if _is_classroom_compatible(
                session=session,
                classroom=classroom,
            )
        ]
        # If user configured allowed classrooms and any of them are shared,
        # keep only shared options to prefer specialised shared rooms.
        if allowed_classroom_ids:
            shared_allowed = [
                classroom
                for classroom in compatible_classrooms
                if getattr(classroom, "is_shared", False)
            ]
            if shared_allowed:
                compatible_classrooms = shared_allowed

        if not allowed_classroom_ids:
            default_classroom = _find_group_default_classroom(
                session=session,
                classrooms=classrooms,
            )
            if default_classroom is not None:
                compatible_classrooms = [default_classroom]
        if not compatible_classrooms:
            raise ScheduleGenerationError(
                _classroom_compatibility_error(session=session),
                code="NO_COMPATIBLE_CLASSROOM",
                context={
                    "subject": getattr(session.get("subject"), "name", ""),
                    "group": getattr(session.get("group"), "name", ""),
                    "allowed_classroom_ids": sorted(allowed_classroom_ids or []),
                },
                suggestions=[
                    "Assign at least one compatible classroom to the subject.",
                    "Create a shared classroom that can host the subject.",
                ],
            )
        compatible_classrooms_by_session[session_index] = compatible_classrooms
    return compatible_classrooms_by_session


def _build_schedule_stability_terms(*, x, y, previous_assignment_by_session):
    """Build soft terms that reward keeping sessions in their original slot and classroom.

    Higher slot-stability weight minimises timetable perturbation after a manual
    change; classroom stability acts as a secondary tie-breaker.
    Input: x, y - decision variables; previous_assignment_by_session - dict
           {session_idx: {slot_index, classroom_id}} or None
    Output: list of weighted CP-SAT expressions; empty list if no previous assignment given
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
    """Return True if a classroom is in the session's allowed_classroom_ids (or no restriction set).
    Input: session - session dict; classroom - Classroom instance
    Output: bool
    """
    allowed_ids = session.get("allowed_classroom_ids")
    if not allowed_ids:
        return True
    return getattr(classroom, "id", None) in allowed_ids


def _find_group_default_classroom(*, session, classrooms):
    """Return the classroom named 'Aula <group_name>' if it exists, else None.
    Input: session - session dict with optional 'group' key;
           classrooms - list of Classroom instances
    Output: matching Classroom instance, or None
    """
    group = session.get("group")
    group_name = getattr(group, "name", "").strip()
    if not group_name:
        return None

    expected_name = f"Aula {group_name}".casefold()
    for classroom in classrooms:
        classroom_name = getattr(classroom, "name", "").strip().casefold()
        if classroom_name == expected_name:
            return classroom
    return None


def _classroom_compatibility_error(*, session):
    """Build the error message for when no classroom is compatible with a session.
    Input: session - session dict
    Output: error message string
    """
    subject = session.get("subject")
    subject_name = getattr(subject, "name", "Unknown subject")
    return (
        "Could not assign a classroom to at least one generated session. "
        "No available classroom matches subject '{subject_name}'."
    ).format(subject_name=subject_name)
